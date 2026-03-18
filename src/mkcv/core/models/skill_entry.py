"""Skill entry model for RenderCV resume."""

from pydantic import BaseModel


class SkillEntry(BaseModel):
    """A single skill category entry."""

    label: str
    details: str
