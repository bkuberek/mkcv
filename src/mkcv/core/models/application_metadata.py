"""Application metadata model (parsed from application.toml)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApplicationMetadata(BaseModel):
    """Metadata about a job application, stored in application.toml."""

    company: str
    position: str
    date: date
    status: Literal[
        "draft", "applied", "interviewing", "offered", "rejected", "withdrawn"
    ] = "draft"
    url: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
