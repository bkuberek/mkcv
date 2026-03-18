"""Tailored role entry for a resume."""

from pydantic import BaseModel, Field

from mkcv.core.models.tailored_bullet import TailoredBullet


class TailoredRole(BaseModel):
    """A complete role entry tailored for a specific job application."""

    company: str
    position: str
    location: str | None = None
    start_date: str
    end_date: str
    summary: str | None = Field(
        default=None,
        description="Optional 1-sentence role context",
    )
    bullets: list[TailoredBullet]
    tech_stack: str | None = Field(
        default=None,
        description="Tech line to display under the role",
    )
