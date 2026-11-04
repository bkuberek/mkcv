"""The judge's verdicts on a list of bullets."""

from pydantic import BaseModel, Field

from evals.models.faithfulness_verdict import FaithfulnessVerdict


class FaithfulnessJudgement(BaseModel):
    """One verdict per bullet the judge was shown."""

    items: list[FaithfulnessVerdict] = Field(
        description="One verdict for each numbered bullet"
    )
