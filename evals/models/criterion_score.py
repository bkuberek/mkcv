"""The judge's score for one rubric criterion."""

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """A 1 to 5 score for one criterion, with the reason for it."""

    name: str = Field(description="The criterion's name, as the rubric spells it")
    score: int = Field(ge=1, le=5, description="1 poor, 3 acceptable, 5 excellent")
    rationale: str = Field(description="One or two sentences justifying the score")
