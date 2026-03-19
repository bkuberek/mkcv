"""Compensation information model."""

from pydantic import BaseModel


class Compensation(BaseModel):
    """Compensation details extracted from a job description.

    All fields are optional strings to handle varied formats
    (e.g., "$150k-$200k", "Competitive", "150000 USD").
    """

    base: str | None = None
    equity: str | None = None
    bonus: str | None = None
    total: str | None = None
