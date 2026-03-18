"""Job description requirement model."""

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """A single requirement extracted from a job description."""

    skill: str
    importance: Literal["must_have", "strong_prefer", "nice_to_have"]
    years_implied: int | None = None
    context: str = Field(description="How this skill is used in the role")
