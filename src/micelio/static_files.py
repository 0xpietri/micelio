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

from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import Scope

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
