"""Configuration error for invalid or incomplete mkcv settings."""

from mkcv.core.exceptions.base import MkcvError


class ConfigurationError(MkcvError):
    """Invalid or incomplete mkcv configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)
