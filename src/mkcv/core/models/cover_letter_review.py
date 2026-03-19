"""Cover letter quality review model."""

from pydantic import BaseModel, Field


class CoverLetterReview(BaseModel):
    """Quality review of a generated cover letter (Stage 2 output)."""

    overall_score: int = Field(ge=0, le=100)
    tone_assessment: str = Field(
        description="Is the tone appropriate for the company/role?"
    )
    specificity_score: int = Field(
        ge=0,
        le=100,
        description="How specific vs generic is the letter?",
    )
    keyword_alignment: list[str] = Field(
        description="JD requirements referenced in the letter"
    )
    length_assessment: str = Field(description="Is the letter an appropriate length?")
    strengths: list[str] = Field(description="What the letter does well")
    improvements: list[str] = Field(description="Specific suggestions for improvement")
    red_flags: list[str] = Field(
        default_factory=list,
        description="Factual errors or inappropriate content",
    )
