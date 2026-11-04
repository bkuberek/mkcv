"""The estimated cost of a matrix run."""

from pydantic import BaseModel


class CostEstimate(BaseModel):
    """Per-model cost, judge cost, and the total, in USD.

    A cost is None when the model has no price in the catalog. When the judge
    cannot run, ``judge_skipped`` says why and it makes no calls and costs
    nothing.
    """

    runs_per_model: int
    model_costs: dict[str, float | None]
    judge: str
    judge_calls: int
    judge_cost_usd: float | None
    total_usd: float | None
    is_partial: bool
    judge_skipped: str | None = None
