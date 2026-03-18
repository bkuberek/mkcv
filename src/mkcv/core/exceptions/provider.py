"""Provider-related errors for AI API calls."""

from mkcv.core.exceptions.base import MkcvError


class ProviderError(MkcvError):
    """Error communicating with an AI provider."""

    def __init__(self, message: str, *, provider: str = "") -> None:
        self.provider = provider
        super().__init__(message, exit_code=4)
