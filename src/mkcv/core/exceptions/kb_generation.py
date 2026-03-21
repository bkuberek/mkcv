"""Knowledge base generation errors."""

from mkcv.core.exceptions.base import MkcvError


class KBGenerationError(MkcvError):
    """Error during knowledge base generation or update."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=9)


class DocumentReadError(MkcvError):
    """Failed to read or parse a source document."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=9)
