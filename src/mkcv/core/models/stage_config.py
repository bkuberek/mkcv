"""Per-stage LLM configuration model."""

from pydantic import BaseModel, Field


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage's LLM call."""

    provider: str = Field(description="LLM provider name (e.g., 'anthropic')")
    model: str = Field(
        description="Model identifier (e.g., 'claude-sonnet-4-20250514')"
    )
    temperature: float = Field(
        ge=0.0,
        le=2.0,
        description="Sampling temperature for this stage",
    )
