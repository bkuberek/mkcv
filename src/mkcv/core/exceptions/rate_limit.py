"""Rate limit error for AI provider throttling."""

from mkcv.core.exceptions.provider import ProviderError


class RateLimitError(ProviderError):
    """AI provider rate limit exceeded. Retry with backoff."""
