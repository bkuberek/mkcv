"""How a matrix run is executed."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evals.stages import EVALUATED_STAGES
from mkcv.core.models.stage_key import StageKey


class RunSettings(BaseModel):
    """Repeats, concurrency, and which stages and cases a run covers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repeats: int = Field(default=1, ge=1)
    concurrency: int = Field(default=2, ge=1)
    stages: list[StageKey] = Field(
        default_factory=lambda: list(EVALUATED_STAGES), min_length=1
    )
    cases: list[str] = Field(default_factory=lambda: ["*"], min_length=1)
    preset: str = "standard"

    @field_validator("stages")
    @classmethod
    def _only_evaluated_stages(cls, stages: list[StageKey]) -> list[StageKey]:
        invalid = [stage.value for stage in stages if stage not in EVALUATED_STAGES]
        if invalid:
            raise ValueError(f"not stages the harness evaluates: {', '.join(invalid)}")
        return stages
