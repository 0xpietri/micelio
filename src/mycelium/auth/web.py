"""Sign-in pages, the session check and security headers."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from collections.abc import Awaitable, Callable
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from mycelium.auth.passwords import verify_password
from mycelium.auth.settings import AuthSettings, is_loopback
from mycelium.auth.store import AuthStore
from mycelium.auth.totp import matching_step
from mycelium.config import Config
from mycelium.i18n import Translate

SESSION_COOKIE = "mycelium_session"
CSRF_COOKIE = "mycelium_csrf"

# Paths anyone may reach. Everything else needs a session while sign-in is on.
OPEN_PATHS = frozenset({"/login", "/healthz", "/favicon.ico"})
OPEN_PREFIXES = ("/static/",)

CSP = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)

Clock = Callable[[], float]
Handler = Callable[[Request], Awaitable[Response]]


def safe_next(target: str | None) -> str:
    """Only same-site paths: never ``//host`` or ``https://host``, never a backslash."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    return target


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _secure_cookie(request: Request) -> bool:
    """Secure everywhere except plain-HTTP localhost, where some browsers drop it."""
    host = request.url.hostname or ""
    return request.url.scheme == "https" or not is_loopback(host)


def install_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next: Handler) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


class SignIn:
    """Everything about being signed in, wired into one app."""

    def __init__(
        self,
        config: Config,
        settings: AuthSettings,
        store: AuthStore | None,
        templates: Jinja2Templates,
        t: Translate,
        clock: Clock = time.time,
    ) -> None:
        self.config = config
        self.settings = settings
        self.store = store
        self.templates = templates
        self.t = t
        self.clock = clock

    @property
    def _store(self) -> AuthStore:
        if self.store is None:
            raise RuntimeError("sign-in is off; there is no session store")
        return self.store

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def is_signed_in(self, request: Request) -> bool:
        if not self.enabled:
            return True
        token = request.cookies.get(SESSION_COOKIE)
        return bool(token) and self._store.session_valid(token or "", self.clock())

    def csrf_token(self, value: str) -> str:
        key = self.settings.session_key.encode("utf-8")
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def logout_token(self, request: Request) -> str:
        return self.csrf_token("logout:" + request.cookies.get(SESSION_COOKIE, ""))

    def install(self, app: FastAPI) -> None:
        app.include_router(self._router())
        if not self.enabled:
            return

        @app.middleware("http")
        async def require_session(request: Request, call_next: Handler) -> Response:
            path = request.url.path
            request.state.signed_in = self.is_signed_in(request)
            if request.state.signed_in or path in OPEN_PATHS or path.startswith(OPEN_PREFIXES):
                return await call_next(request)
            if request.method in ("GET", "HEAD"):
                target = path + (f"?{request.url.query}" if request.url.query else "")
                return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)
            return Response(status_code=401)

    # -- routes -------------------------------------------------------------------

    def _render_login(
        self, request: Request, *, next_path: str, error: str = "", status: int = 200
    ) -> Response:
        nonce = secrets.token_urlsafe(16)
        response = self.templates.TemplateResponse(
            request,
            "login.html",
            {"next": next_path, "csrf": self.csrf_token("login:" + nonce), "error": error},
            status_code=status,
        )
        response.set_cookie(
            CSRF_COOKIE,
            nonce,
            httponly=True,
            samesite="strict",
            secure=_secure_cookie(request),
            max_age=3600,
            path="/login",
        )
        return response

    def _locked_minutes(self, address: str, now: float) -> int:
        window = self.config.auth.lockout_minutes * 60
        if self._store.failures_since(address, now - window) >= self.config.auth.max_failures:
            return self.config.auth.lockout_minutes
        return 0

    def _router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/login", include_in_schema=False)
        def login_form(request: Request, next: str = "/") -> Response:
            next_path = safe_next(next)
            if not self.enabled or self.is_signed_in(request):
                return RedirectResponse(next_path, status_code=303)
            return self._render_login(request, next_path=next_path)

        @router.post("/login", include_in_schema=False)
        def login(
            request: Request,
            password: str = Form(""),
            code: str = Form(""),
            csrf: str = Form(""),
            next: str = Form("/"),
        ) -> Response:
            next_path = safe_next(next)
            if not self.enabled:
                return RedirectResponse(next_path, status_code=303)
            now = self.clock()
            address = _client(request)

            minutes = self._locked_minutes(address, now)
            if minutes:
                return self._render_login(
                    request,
                    next_path=next_path,
                    error=self.t("login.locked", minutes=minutes),
                    status=429,
                )

            nonce = request.cookies.get(CSRF_COOKIE, "")
            if not nonce or not hmac.compare_digest(csrf, self.csrf_token("login:" + nonce)):
                return self._render_login(
                    request,
                    next_path=next_path,
                    error=self.t("login.expired"),
                    status=400,
                )

            password_ok = verify_password(self.settings.password_hash, password)
            step = matching_step(self.settings.totp_secret, code, now)
            if password_ok and step is not None and self._store.claim_totp_step(step):
                self._store.clear_failures(address)
                hours = self.config.auth.session_hours
                token = self._store.create_session(now, hours * 3600)
                response = RedirectResponse(next_path, status_code=303)
                response.set_cookie(
                    SESSION_COOKIE,
                    token,
                    httponly=True,
                    samesite="strict",
                    secure=_secure_cookie(request),
                    max_age=math.ceil(hours * 3600),
                    path="/",
                )
                response.delete_cookie(CSRF_COOKIE, path="/login")
                return response

            self._store.record_failure(address, now)
            return self._render_login(
                request,
                next_path=next_path,
                error=self.t("login.failed"),
                status=401,
            )

        @router.post("/logout", include_in_schema=False)
        def logout(request: Request, csrf: str = Form("")) -> Response:
            response = RedirectResponse("/login" if self.enabled else "/", status_code=303)
            if not self.enabled:
                return response
            if not hmac.compare_digest(csrf, self.logout_token(request)):
                return Response(status_code=400)
            token = request.cookies.get(SESSION_COOKIE)
            if token:
                self._store.delete_session(token)
            response.delete_cookie(SESSION_COOKIE, path="/")
            return response

        return router
