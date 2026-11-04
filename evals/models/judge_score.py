"""One panel judge's verdict on one output."""

from typing import Any

from pydantic import BaseModel, Field


class JudgeScore(BaseModel):
    """The score one judge gave, whether it judged its own provider's model.

    ``details`` holds that judge's evidence (criteria, unsupported bullets,
    findings) or the error that stopped it.
    """

    judge: str = Field(description="'provider/model' of the judge")
    provider: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None = None
    self_judged: bool = Field(
        description="The judge comes from the evaluated model's own provider"
    )
    details: dict[str, Any] = Field(default_factory=dict)
