"""Everything a run concluded: ``summary.json``."""

from pydantic import BaseModel, Field

from evals.models.recommendation import Recommendation
from evals.models.screening_decision import ScreeningDecision
from evals.models.stage_summary import StageSummary
from evals.models.suggested_profile import SuggestedProfile
from mkcv.core.models.stage_key import StageKey


class RunSummary(BaseModel):
    """Per-model summaries, recommendations, and suggested profiles of a run."""

    run_id: str
    primary_metrics: dict[StageKey, str] = Field(
        description="The grade that ranks models at each stage"
    )
    stages: list[StageSummary] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    suggested_profiles: list[SuggestedProfile] = Field(default_factory=list)
    screening: list[ScreeningDecision] = Field(
        default_factory=list,
        description="The screening round's decisions, when the run had one",
    )
    not_evaluated: dict[StageKey, str] = Field(
        default_factory=dict, description="Stages the run has no result for, and why"
    )
