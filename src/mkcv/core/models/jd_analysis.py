"""Job description analysis output model."""

from pydantic import BaseModel, Field

from mkcv.core.models.requirement import Requirement


class JDAnalysis(BaseModel):
    """Structured analysis of a job description (Stage 1 output)."""

    company: str
    role_title: str
    seniority_level: str
    team_or_org: str | None = None
    location: str | None = None
    compensation: str | None = None
    core_requirements: list[Requirement]
    technical_stack: list[str]
    soft_skills: list[str]
    leadership_signals: list[str]
    culture_keywords: list[str]
    ats_keywords: list[str] = Field(
        description="Exact phrases likely used as ATS keyword filters"
    )
    hidden_requirements: list[str] = Field(
        description="Requirements implied but not explicitly stated"
    )
    role_summary: str = Field(
        description="2-3 sentence synthesis of what they actually need"
    )
