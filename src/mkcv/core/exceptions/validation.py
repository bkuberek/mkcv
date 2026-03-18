"""Validation error for AI output schema validation."""

from mkcv.core.exceptions.base import MkcvError


class ValidationError(MkcvError):
    """AI output failed Pydantic schema validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=5)
