"""mkcv — AI-powered resume generator."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mkcv")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
