"""Skill group model for resume skills section."""

from pydantic import BaseModel


class SkillGroup(BaseModel):
    """A labeled group of skills for the resume skills section."""

    label: str
    skills: list[str]
