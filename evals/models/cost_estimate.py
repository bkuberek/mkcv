"""The estimated cost of a matrix run."""

from pydantic import BaseModel, Field


class CostEstimate(BaseModel):
    """Per-model and per-judge cost, a per-provider breakdown, and the total.

    A cost is None when the model has no price in the catalog. Every judge
    of the panel makes ``judge_calls`` calls. A judge that cannot run (no
    credentials) makes no calls and costs nothing; ``skipped_judges`` says
    why, when the run would have needed it.
    """

    runs_per_model: int
    model_costs: dict[str, float | None]
    judges: list[str] = Field(
        default_factory=list, description="'provider/model' of the judges that run"
    )
    judge_calls: int = Field(description="Calls each judge of the panel makes")
    judge_call_counts: dict[str, int] = Field(
        default_factory=dict, description="Calls per judge, by 'provider/model'"
    )
    judge_costs: dict[str, float | None] = Field(default_factory=dict)
    judge_cost_usd: float | None
    provider_costs: dict[str, float | None] = Field(
        default_factory=dict,
        description="Evaluated models plus judges, summed per provider",
    )
    total_usd: float | None
    is_partial: bool
    skipped_judges: dict[str, str] = Field(default_factory=dict)
