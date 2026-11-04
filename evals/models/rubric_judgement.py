"""The judge's scores for a rubric."""

from pydantic import BaseModel, Field

from evals.models.criterion_score import CriterionScore


class RubricJudgement(BaseModel):
    """A score for each rubric criterion and a short overall summary."""

    criteria: list[CriterionScore] = Field(
        description="One score for each criterion in the rubric"
    )
    summary: str = Field(description="One or two sentences on the output overall")
