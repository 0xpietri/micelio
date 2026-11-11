"""Static files that a browser always checks again, by their content.

The wheel and the image give every file the same old modification time, so browsers that
cached ``micelio.css`` from one build would keep it for months by heuristic and serve it
with the next build's pages. Here every answer says ``no-cache`` (check before use) and
its ETag is a hash of the bytes, so a changed file is fetched and an unchanged one is a
quick 304.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import FileResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PathLike = str | os.PathLike[str]


class FreshStaticFiles(StaticFiles):
    """``StaticFiles`` with content ETags and ``Cache-Control: no-cache``."""

    def __init__(self, *, directory: Path) -> None:
        super().__init__(directory=directory)
        self._tags: dict[tuple[str, int, int], str] = {}

    def _etag(self, path: PathLike, stat: os.stat_result) -> str:
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        tag = self._tags.get(key)
        if tag is None:
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:32]
            tag = self._tags[key] = f'"{digest}"'
        return tag

    def file_response(
        self,
        full_path: PathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        headers = {"etag": self._etag(full_path, stat_result), "cache-control": "no-cache"}
        response = FileResponse(
            full_path, status_code=status_code, stat_result=stat_result, headers=headers
        )
        # The build's file times say nothing about the content: leave them out.
        del response.headers["last-modified"]
        if self.is_not_modified(response.headers, Headers(scope=scope)):
            return NotModifiedResponse(response.headers)
        return response


STATIC_COOKIE = "micelio_static"


def fingerprint(directory: Path) -> str:
    """A short hash of every file under ``directory``: changes with any static file."""
    digest = hashlib.sha256()
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


class ClearStaleCache:
    """Make a browser drop what it cached from an older build, once per build.

    Builds before 0.1.1 sent static files with no caching headers and an old date, so
    browsers may keep them for months without asking again. The first page a browser
    gets from a new build says ``Clear-Site-Data: "cache"`` and sets a cookie with the
    build's fingerprint; later pages say nothing until the static files change again.
    Pure ASGI, so it only touches the response headers of HTML pages.
    """

    def __init__(self, app: ASGIApp, build: str) -> None:
        self.app = app
        self.build = build
        self.cookie = f"{STATIC_COOKIE}={build}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "GET":
            await self.app(scope, receive, send)
            return
        cookies = Headers(scope=scope).get("cookie", "")
        if self.cookie in (part.strip() for part in cookies.split(";")):
            await self.app(scope, receive, send)
            return

        async def tell(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if headers.get("content-type", "").startswith("text/html"):
                    headers.append("clear-site-data", '"cache"')
                    headers.append(
                        "set-cookie",
                        f"{self.cookie}; Max-Age=31536000; Path=/; SameSite=Lax; HttpOnly",
                    )
            await send(message)

        await self.app(scope, receive, tell)
