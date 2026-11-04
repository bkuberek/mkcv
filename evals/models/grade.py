"""One grader's verdict on one output."""

from typing import Any

from pydantic import BaseModel, Field


class Grade(BaseModel):
    """A named score between 0 and 1, whether it passed, and the evidence."""

    name: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)
