"""Pipeline stage execution metadata."""

from pydantic import BaseModel


class StageMetadata(BaseModel):
    """Metadata about a single pipeline stage execution."""

    stage_number: int
    stage_name: str
    provider: str
    model: str
    temperature: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_seconds: float
    retries: int = 0
