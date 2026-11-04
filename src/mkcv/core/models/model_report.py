"""The models a run will use, with warnings and a cost estimate."""

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.stage_advice import StageAdvice
from mkcv.core.models.stage_key import PIPELINE_STAGES


def summarize_costs(costs: Iterable[float | None]) -> tuple[float | None, bool]:
    """Sum the known stage costs.

    Returns:
        ``(total, is_partial)``: the total is None when no cost is known, and
        ``is_partial`` is True when some costs are unknown while others are known.
    """
    values = list(costs)
    known = [cost for cost in values if cost is not None]
    if not known:
        return None, False
    return sum(known), len(known) < len(values)


class ModelReport(BaseModel):
    """Per-stage advice plus every warning, for ``generate`` and ``mkcv models``."""

    model_config = ConfigDict(frozen=True)

    profile_name: str | None
    profile_evidence: Literal["provisional", "eval"] | None
    profile_source: Literal["cli", "config", "default", "preset"]
    preset_name: str
    stages: list[StageAdvice]
    warnings: list[ModelWarning]
    estimated_total_usd: float | None
    estimate_is_partial: bool

    def resume_run_estimate(self) -> tuple[float | None, bool]:
        """Return the estimated cost of one resume run and whether it is partial.

        Only the five resume pipeline stages count; cover letter, KB, and
        validate stages are separate runs.
        """
        return summarize_costs(
            advice.estimated_cost_usd
            for advice in self.stages
            if advice.assignment.stage in PIPELINE_STAGES
        )
