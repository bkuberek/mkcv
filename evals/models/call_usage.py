"""The tokens one model call used: one line of ``usage.jsonl``."""

from pydantic import BaseModel, Field


class CallUsage(BaseModel):
    """Who made a call, on which model, how it was sent, and its tokens.

    ``input_tokens`` counts every prompt token, including those read from or
    written to the provider's prompt cache, which ``cache_read_tokens`` and
    ``cache_write_tokens`` count again on their own.
    """

    scope: str | None = Field(description="The job that made the call")
    provider: str
    model: str
    batched: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
