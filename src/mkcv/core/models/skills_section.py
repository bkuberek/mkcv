"""Skills section wrapper model for structured LLM output."""

from pydantic import BaseModel

from mkcv.core.models.skill_group import SkillGroup


class SkillsSection(BaseModel):
    """Wrapper for a list of skill groups, used for structured LLM output.

    The ``complete_structured`` method requires a single ``BaseModel`` class,
    but the skills section is a ``list[SkillGroup]``. This wrapper provides
    the required top-level model.
    """

    skills: list[SkillGroup]
