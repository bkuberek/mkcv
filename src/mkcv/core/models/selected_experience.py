"""Selected experience entry for a job application."""

from pydantic import BaseModel, Field


class SelectedExperience(BaseModel):
    """A single experience entry selected from the knowledge base."""

    company: str
    role: str
    period: str
    relevance_score: int = Field(ge=0, le=100)
    match_reasons: list[str]
    suggested_bullets: list[str] = Field(
        description="KB bullets to include for this role"
    )
    bullets_to_drop: list[str] = Field(
        description="KB bullets that aren't relevant to this JD"
    )
    reframe_suggestion: str = Field(
        description="How to angle this experience for the target role"
    )
