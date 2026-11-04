"""One grader's verdict on one output."""

from typing import Any

from pydantic import BaseModel, Field

from evals.models.judge_score import JudgeScore


class Grade(BaseModel):
    """A named score between 0 and 1, whether it passed, and the evidence.

    A judged grade is scored by every judge of the panel: ``score`` is their
    mean, ``independent_score`` the mean without the judge of the evaluated
    model's own provider (None when no other judge scored it), and
    ``judge_scores`` keeps each judge's verdict. Other grades leave those empty.
    """

    name: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    independent_score: float | None = Field(default=None, ge=0.0, le=1.0)
    judge_scores: list[JudgeScore] = Field(default_factory=list)
