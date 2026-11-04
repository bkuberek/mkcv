"""How one model did on one stage across a run: one entry of ``summary.json``."""

from pydantic import BaseModel, Field

from mkcv.core.models.stage_key import StageKey


class StageSummary(BaseModel):
    """Counts, grade means, cost, latency, and tokens for a (stage, model).

    ``n`` counts runs that were attempted (``ok`` plus ``error``; skipped runs
    are not counted). Means, cost, latency, and token medians cover ``ok``
    runs only and are None when there were none.
    """

    stage: StageKey
    provider: str
    model: str
    n: int
    ok_rate: float = Field(ge=0.0, le=1.0)
    mean: dict[str, float] = Field(
        default_factory=dict, description="Mean score per grade name"
    )
    primary_score: float | None = Field(
        default=None, description="Mean of the stage's primary quality metric"
    )
    cost_mean_usd: float | None = None
    latency_p50_s: float | None = None
    latency_p90_s: float | None = None
    median_input_tokens: float | None = None
    median_output_tokens: float | None = None
    fabrication_rate: dict[str, float] = Field(
        default_factory=dict,
        description="Per faithfulness grade, the share of runs with a fabricated claim",
    )
    eligible: bool = Field(
        description="Completed, valid, and faithful enough to be recommended"
    )
    gate_failures: list[str] = Field(
        default_factory=list, description="The hard gates the model missed"
    )
    self_judged: bool = Field(
        description="A judge from the model's own provider scored it"
    )
    low_sample: bool = Field(description="Fewer than 6 runs")
