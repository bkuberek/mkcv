"""Rendering error for PDF generation."""

from mkcv.core.exceptions.base import MkcvError


class RenderError(MkcvError):
    """PDF rendering failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=6)
