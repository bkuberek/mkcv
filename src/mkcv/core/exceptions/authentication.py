"""Authentication error for AI provider API keys."""

from mkcv.core.exceptions.provider import ProviderError


class AuthenticationError(ProviderError):
    """Invalid or missing API key for an AI provider."""
