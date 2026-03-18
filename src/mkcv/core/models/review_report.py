"""Complete review report model (Stage 5 output)."""

from pydantic import BaseModel, Field

from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.keyword_coverage import KeywordCoverage


class ReviewReport(BaseModel):
    """Complete quality review report (Stage 5 output)."""

    overall_score: int = Field(ge=0, le=100)
    bullet_reviews: list[BulletReview]
    keyword_coverage: KeywordCoverage
    ats_check: ATSCheck
    tone_consistency: str = Field(
        description="Assessment of voice consistency across the resume"
    )
    section_balance: str = Field(
        description="Assessment of space allocation across sections"
    )
    length_assessment: str = Field(description="Is the resume the right length?")
    top_suggestions: list[str] = Field(
        description="The 3-5 most impactful improvements"
    )
    low_confidence_items: list[str] = Field(
        description="Items flagged for human review"
    )
