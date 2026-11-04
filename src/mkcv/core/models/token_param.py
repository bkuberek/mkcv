"""Names of the output-limit request parameter on OpenAI-style APIs."""

from enum import StrEnum


class TokenParam(StrEnum):
    """Which request field carries the output token limit."""

    MAX_TOKENS = "max_tokens"
    MAX_COMPLETION_TOKENS = "max_completion_tokens"
