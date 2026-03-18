"""Mission statement model for resume header."""

from pydantic import BaseModel, Field


class MissionStatement(BaseModel):
    """A tailored mission statement for the top of a resume."""

    text: str = Field(max_length=200)
    rationale: str = Field(
        description="Why this mission statement works for this application"
    )
