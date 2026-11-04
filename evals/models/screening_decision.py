"""Whether a model goes on to the finals of one stage, and why."""

from pydantic import BaseModel

from mkcv.core.models.stage_key import StageKey


class ScreeningDecision(BaseModel):
    """The screening round's verdict on one model at one stage."""

    stage: StageKey
    provider: str
    model: str
    score: float | None
    kept: bool
    reason: str

    @property
    def label(self) -> str:
        """``provider/model``."""
        return f"{self.provider}/{self.model}"
