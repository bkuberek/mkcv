"""Cover letter generation error."""

from mkcv.core.exceptions.base import MkcvError


class CoverLetterError(MkcvError):
    """Cover letter generation or rendering failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=8)
