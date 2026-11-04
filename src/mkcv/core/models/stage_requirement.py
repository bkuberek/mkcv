"""What a stage needs from a model."""

from pydantic import BaseModel, ConfigDict, Field

from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.stage_key import StageKey


class StageRequirement(BaseModel):
    """Configuration location, default sampling, and model needs of one stage."""

    model_config = ConfigDict(frozen=True)

    stage: StageKey
    config_path: str = Field(
        description="Dotted path of the stage's configuration section"
    )
    default_temperature: float = Field(
        description="Temperature used when the configuration sets none"
    )
    min_tier: ModelTier = Field(
        description="Lowest model tier mkcv recommends for this stage"
    )
    est_input_tokens: int = Field(
        description="Rough input tokens per run, for cost estimates"
    )
    est_output_tokens: int = Field(
        description="Rough output tokens per run, including thinking"
    )
    label: str = Field(description="Short human-readable stage name")
