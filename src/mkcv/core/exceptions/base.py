"""Base exception for all mkcv errors."""


class MkcvError(Exception):
    """Base exception for all mkcv errors.

    All mkcv exceptions inherit from this class, allowing callers
    to catch any mkcv-specific error with a single except clause.
    """

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        self.exit_code = exit_code
        super().__init__(message)
