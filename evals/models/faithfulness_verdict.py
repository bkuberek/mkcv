"""The judge's verdict on one bullet's faithfulness."""

from typing import Literal

from pydantic import BaseModel, Field


class FaithfulnessVerdict(BaseModel):
    """Whether one numbered bullet is backed by the knowledge base."""

    index: int = Field(description="The bullet's number, starting at 1")
    verdict: Literal["supported", "partial", "unsupported"]
    evidence: str = Field(description="The knowledge base text that backs the bullet")
