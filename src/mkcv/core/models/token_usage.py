"""Token usage tracking model."""

from pydantic import BaseModel


class TokenUsage(BaseModel):
    """Token counts from a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
