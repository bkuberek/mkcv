"""The judge's finding on one seeded defect."""

from pydantic import BaseModel, Field


class DefectFinding(BaseModel):
    """Whether a review caught one seeded defect, with the text that shows it."""

    defect: str = Field(description="The seeded defect, copied as listed")
    detected: bool = Field(description="True if the review identifies the defect")
    quote: str = Field(
        description="The review text that identifies the defect, or an empty string"
    )
