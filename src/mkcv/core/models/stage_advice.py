"""What mkcv knows and recommends about the model assigned to one stage."""

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.stage_assignment import StageAssignment


class StageAdvice(BaseModel):
    """A stage assignment with its recommendation, tier check, and cost."""

    model_config = ConfigDict(frozen=True)

    assignment: StageAssignment
    recommended_model: str | None
    recommended_provider: str | None
    tier: ModelTier | None
    min_tier: ModelTier
    known: bool
    estimated_cost_usd: float | None
    warnings: list[ModelWarning]
