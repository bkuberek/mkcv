"""A judge's score for the tailored content (stage 3)."""

from evals.graders.rubric_judge_grader import RubricJudgeGrader


class TailoringJudgeGrader(RubricJudgeGrader):
    """Scores relevance, keywords, impact, clarity, and prioritization."""

    name = "tailoring_judge"
    rubric = "tailoring"
    criteria = (
        "relevance",
        "keyword_integration",
        "impact",
        "clarity",
        "prioritization",
    )
    output_label = "Tailored content (JSON)"
