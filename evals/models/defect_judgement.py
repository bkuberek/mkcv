"""The judge's findings on all seeded defects."""

from pydantic import BaseModel, Field

from evals.models.defect_finding import DefectFinding


class DefectJudgement(BaseModel):
    """One finding for each seeded defect, in the order they were listed."""

    findings: list[DefectFinding] = Field(
        description="One finding for each listed defect"
    )
