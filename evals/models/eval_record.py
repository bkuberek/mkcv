"""The outcome of running one stage for one case on one model."""

from typing import Literal

from pydantic import BaseModel, Field

from evals.models.grade import Grade
from mkcv.core.models.stage_key import StageKey


class EvalRecord(BaseModel):
    """One line of ``results.jsonl``."""

    run_id: str
    case_id: str
    stage: StageKey
    provider: str
    model: str
    repeat: int = Field(ge=0)
    status: Literal["ok", "error", "skipped"]
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    grades: list[Grade] = Field(default_factory=list)
    judge: str | None = None
