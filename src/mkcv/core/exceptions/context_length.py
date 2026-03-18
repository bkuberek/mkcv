"""Context length error for AI provider token limits."""

from mkcv.core.exceptions.provider import ProviderError


class ContextLengthError(ProviderError):
    """Input exceeds the AI model's context window."""
