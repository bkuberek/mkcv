"""Job description read error."""

from mkcv.core.exceptions.base import MkcvError


class JDReadError(MkcvError):
    """Failed to read a job description from the given source."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=2)
