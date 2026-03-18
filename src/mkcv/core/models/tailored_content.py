"""Complete tailored content output model (Stage 3)."""

from pydantic import BaseModel, Field

from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_role import TailoredRole


class TailoredContent(BaseModel):
    """Complete tailored resume content (Stage 3 output)."""

    mission: MissionStatement
    skills: list[SkillGroup]
    roles: list[TailoredRole]
    earlier_experience: str | None = Field(
        default=None,
        description="Condensed summary of older roles",
    )
    languages: list[str] | None = None
    low_confidence_flags: list[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of items needing review",
    )
