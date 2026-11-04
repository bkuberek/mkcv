"""What the caller asked for when resolving stage models."""

from pydantic import BaseModel, ConfigDict, Field


class ResolutionRequest(BaseModel):
    """Command-line and preset inputs to stage resolution."""

    model_config = ConfigDict(frozen=True)

    preset_name: str = Field(
        default="default", description="Preset or legacy profile name"
    )
    model_profile: str | None = Field(
        default=None, description="--model-profile: one profile for every stage"
    )
    provider_override: str | None = Field(
        default=None, description="--provider: one provider for every stage"
    )
    model_override: str | None = Field(
        default=None, description="--model, for the knowledge base stage only"
    )
