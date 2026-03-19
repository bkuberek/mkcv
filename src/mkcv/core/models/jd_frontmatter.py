"""JD YAML frontmatter model."""

import logging
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mkcv.core.models.compensation import Compensation

logger = logging.getLogger(__name__)

_VALID_WORKPLACES = ("remote", "hybrid", "onsite")


class JDFrontmatter(BaseModel):
    """YAML frontmatter metadata for a job description document.

    Parsed from the ``---`` delimited header of a jd.md file.
    All fields are optional --- a JD can have partial or no frontmatter.
    """

    model_config = ConfigDict(extra="ignore")

    company: str | None = None
    position: str | None = None
    url: str | None = None
    location: str | None = None
    workplace: str | None = Field(
        default=None,
        description="remote, hybrid, onsite",
    )
    compensation: Compensation | None = None
    posted_date: date | None = None
    source: str | None = Field(
        default=None,
        description="Where the JD was found: linkedin, company-site, etc.",
    )
    tags: list[str] = Field(default_factory=list)

    @field_validator("workplace", mode="before")
    @classmethod
    def _validate_workplace(cls, v: object) -> str | None:
        """Validate workplace is one of the allowed literals."""
        if v is None:
            return None
        if isinstance(v, str) and v.lower() in _VALID_WORKPLACES:
            return v.lower()
        logger.warning(
            "Invalid workplace value %r; setting to None. Valid values: %s",
            v,
            ", ".join(_VALID_WORKPLACES),
        )
        return None
