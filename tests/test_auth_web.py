from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mycelium.app import create_app
from mycelium.auth.passwords import hash_password
from mycelium.auth.settings import AuthSetupError
from mycelium.auth.totp import code_at, generate_secret, step_for
from mycelium.auth.web import safe_next

from .conftest import EXAMPLE_VAULT, config_for

PASSWORD = "a long enough passphrase"
SECRET = generate_secret()
HASH = hash_password(PASSWORD)
ENV = {
    "MYCELIUM_PASSWORD_HASH": HASH,
    "MYCELIUM_TOTP_SECRET": SECRET,
    "MYCELIUM_SESSION_KEY": "s" * 48,
}
START = 1_800_000_000.0


@dataclass
class Site:
    client: TestClient
    now: list[float] = field(default_factory=lambda: [START])

    def code(self, offset: int = 0) -> str:
        return code_at(SECRET, step_for(self.now[0]) + offset)

    def advance(self, seconds: float) -> None:
        self.now[0] += seconds

    def form(self, path: str = "/login") -> dict[str, str]:
        page = self.client.get(path)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)
        nxt = re.search(r'name="next" value="([^"]*)"', page.text)
        assert csrf, page.text
        return {"csrf": csrf.group(1), "next": nxt.group(1) if nxt else "/"}

    def sign_in(
        self, password: str = PASSWORD, code: str | None = None, **extra: str
    ) -> httpx.Response:
        data = {**self.form(), "password": password, "code": code or self.code(), **extra}
        return self.client.post("/login", data=data, follow_redirects=False)


SiteFactory = Callable[..., Site]


@pytest.fixture
def make_site(tmp_path: Path) -> Iterator[SiteFactory]:
    with ExitStack() as stack:

        def factory(base_url: str = "https://mycelium.example") -> Site:
            now = [START]
            config = config_for(EXAMPLE_VAULT, data=tmp_path / "data")
            app = create_app(config, environ=ENV, clock=lambda: now[0])
            client = stack.enter_context(TestClient(app, base_url=base_url))
            return Site(client, now)

        yield factory


@pytest.fixture
def site(make_site: SiteFactory) -> Site:
    return make_site()


def test_pages_redirect_to_login(site: Site) -> None:
    response = site.client.get("/?tab=all", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F%3Ftab%3Dall"


def test_open_paths_need_no_session(site: Site) -> None:
    assert site.client.get("/healthz").status_code == 200
    assert site.client.get("/static/css/mycelium.css").status_code == 200
    assert site.client.get("/login").status_code == 200


def test_other_methods_get_401(site: Site) -> None:
    assert site.client.post("/", follow_redirects=False).status_code == 401


def test_full_sign_in_and_out(site: Site) -> None:
    response = site.sign_in()
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "mycelium_session=" in cookie
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=43200"):
        assert flag.lower() in cookie.lower()

    home = site.client.get("/")
    assert home.status_code == 200
    assert 'id="headline"' in home.text
    assert "Sign out" in home.text

    csrf = re.search(r'name="csrf" value="([^"]+)"', home.text)
    assert csrf
    out = site.client.post("/logout", data={"csrf": csrf.group(1)}, follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/login"
    assert site.client.get("/", follow_redirects=False).status_code == 303


def test_signed_out_cookie_no_longer_works(site: Site) -> None:
    site.sign_in()
    token = site.client.cookies.get("mycelium_session")
    assert token
    home = site.client.get("/")
    csrf = re.search(r'name="csrf" value="([^"]+)"', home.text)
    assert csrf
    site.client.post("/logout", data={"csrf": csrf.group(1)})
    site.client.cookies.set("mycelium_session", token, domain="mycelium.example")
    assert site.client.get("/", follow_redirects=False).status_code == 303


def test_logout_needs_its_token(site: Site) -> None:
    site.sign_in()
    assert site.client.post("/logout", data={"csrf": "nope"}).status_code == 400
    assert site.client.get("/").status_code == 200


def test_next_is_kept_and_sanitized(site: Site) -> None:
    page = site.client.get("/login?next=%2F%3Fa%3D1")
    assert 'value="/?a=1"' in page.text
    response = site.sign_in(next="//evil.example/")
    assert response.headers["location"] == "/"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/notes/x", "/notes/x"),
        ("//evil.example", "/"),
        ("https://evil.example", "/"),
        ("/\\evil.example", "/"),
        ("notes", "/"),
    ],
)
def test_safe_next(target: str | None, expected: str) -> None:
    assert safe_next(target) == expected


def test_wrong_password_or_code(site: Site) -> None:
    bad_password = site.sign_in(password="not the password at all")
    assert bad_password.status_code == 401
    assert "did not work" in bad_password.text
    bad_code = site.sign_in(code=site.code(offset=3))
    assert bad_code.status_code == 401
    assert "mycelium_session" not in site.client.cookies


def test_code_with_one_step_of_drift_works(site: Site) -> None:
    assert site.sign_in(code=site.code(offset=-1)).status_code == 303


def test_a_used_code_is_refused(site: Site) -> None:
    code = site.code()
    assert site.sign_in(code=code).status_code == 303
    site.client.cookies.clear()
    assert site.sign_in(code=code).status_code == 401
    site.advance(30)
    assert site.sign_in().status_code == 303


def test_missing_or_forged_csrf(site: Site) -> None:
    data = {"password": PASSWORD, "code": site.code(), "csrf": "forged", "next": "/"}
    site.client.get("/login")
    assert site.client.post("/login", data=data).status_code == 400
    site.client.cookies.clear()
    form = site.form()
    site.client.cookies.clear()
    data["csrf"] = form["csrf"]
    assert site.client.post("/login", data=data).status_code == 400


def test_lockout_after_five_failures(site: Site) -> None:
    for _ in range(5):
        assert site.sign_in(password="wrong password here").status_code == 401
    locked = site.sign_in()
    assert locked.status_code == 429
    assert "15 minutes" in locked.text
    site.advance(15 * 60 + 1)
    assert site.sign_in().status_code == 303


def test_success_clears_failures(site: Site) -> None:
    for _ in range(4):
        site.sign_in(password="wrong password here")
    assert site.sign_in().status_code == 303
    site.client.cookies.clear()
    site.advance(30)
    for _ in range(4):
        site.sign_in(password="wrong password here")
    site.advance(30)
    assert site.sign_in().status_code == 303


def test_session_expires_after_twelve_hours(site: Site) -> None:
    site.sign_in()
    site.advance(12 * 3600 - 1)
    assert site.client.get("/", follow_redirects=False).status_code == 200
    site.advance(2)
    assert site.client.get("/", follow_redirects=False).status_code == 303


def test_login_page_when_signed_in_redirects(site: Site) -> None:
    site.sign_in()
    response = site.client.get("/login?next=/x", follow_redirects=False)
    assert response.headers["location"] == "/x"


def test_cookie_is_not_secure_on_plain_http_localhost(make_site: SiteFactory) -> None:
    site = make_site("http://127.0.0.1:8765")
    response = site.sign_in()
    assert response.status_code == 303
    assert "secure" not in response.headers["set-cookie"].lower()


def test_cookie_is_secure_on_http_elsewhere(make_site: SiteFactory) -> None:
    site = make_site("http://mycelium.example")
    page = site.client.get("/login")
    assert "secure" in page.headers["set-cookie"].lower()


def test_mode_none_has_no_sign_in(tmp_path: Path) -> None:
    config = config_for(EXAMPLE_VAULT, data=tmp_path / "data", auth="none")
    client = TestClient(create_app(config, environ={}))
    assert client.get("/").status_code == 200
    assert client.get("/login", follow_redirects=False).headers["location"] == "/"
    login = client.post("/login", data={"next": "/x"}, follow_redirects=False)
    assert login.headers["location"] == "/x"
    assert client.post("/logout", follow_redirects=False).headers["location"] == "/"
    assert not (tmp_path / "data").exists()


def test_sign_in_on_without_secrets_refuses(tmp_path: Path) -> None:
    with pytest.raises(AuthSetupError):
        create_app(config_for(EXAMPLE_VAULT, data=tmp_path / "data"), environ={})
