"""Micelio: your Markdown notes as a living network of ideas."""

from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION = "micelio"

try:
    __version__ = version(DISTRIBUTION)
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0"

__all__ = ["DISTRIBUTION", "__version__"]
