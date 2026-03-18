"""Tailored resume bullet model."""

from typing import Literal

from pydantic import BaseModel, Field


class TailoredBullet(BaseModel):
    """A resume bullet rewritten for a specific job application."""

    original: str = Field(description="Source bullet from KB")
    rewritten: str = Field(description="Tailored version optimized for the target JD")
    keywords_incorporated: list[str]
    confidence: Literal["high", "medium", "low"] = Field(
        description="high=faithful, medium=enhanced, low=stretched"
    )
