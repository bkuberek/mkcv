"""Experience entry model for RenderCV resume."""

from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    """A single experience entry in RenderCV format."""

    company: str
    position: str
    location: str | None = None
    start_date: str
    end_date: str
    highlights: list[str] = Field(min_length=1, max_length=6)
