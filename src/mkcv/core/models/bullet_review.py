"""Individual bullet review model."""

from typing import Literal

from pydantic import BaseModel


class BulletReview(BaseModel):
    """Review assessment of a single resume bullet."""

    bullet_text: str
    classification: Literal["faithful", "enhanced", "stretched", "fabricated"]
    explanation: str | None = None
    suggested_fix: str | None = None
