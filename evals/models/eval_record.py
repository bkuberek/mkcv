"""The outcome of running one stage for one case on one model."""

from typing import Literal

from pydantic import BaseModel, Field

from evals.models.grade import Grade
from evals.models.round import Round
from mkcv.core.models.stage_key import StageKey


class EvalRecord(BaseModel):
    """One line of ``results.jsonl``."""

    run_id: str
    round: Round | None = Field(
        default=None, description="The tournament round, or None for a single round"
    )
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
    judge: str | None = Field(
        default=None, description="The judges that scored the record, comma-separated"
    )
    judges: list[str] = Field(
        default_factory=list, description="'provider/model' of each judge that scored"
    )
