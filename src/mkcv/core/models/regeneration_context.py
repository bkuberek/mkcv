"""Context model for section regeneration."""

from pydantic import BaseModel, Field


class RegenerationContext(BaseModel):
    """Context from the original pipeline run, needed for section regeneration.

    Carries the JD analysis, ATS keywords, knowledge base text, and
    experience selection so the LLM can maintain quality when
    regenerating individual sections.
    """

    jd_analysis: dict[str, object] = Field(
        description="JDAnalysis.model_dump() from Stage 1",
    )
    ats_keywords: list[str] = Field(
        default_factory=list,
        description="ATS keywords extracted from the JD",
    )
    kb_text: str = Field(
        default="",
        description="Full knowledge base text for accuracy reference",
    )
    selection: dict[str, object] | None = Field(
        default=None,
        description="ExperienceSelection.model_dump() from Stage 2",
    )
