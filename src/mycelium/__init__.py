"""Mycelium: your Markdown notes as a living network of ideas."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mycelium")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
