"""A judge's score for the experience selection (stage 2)."""

from evals.graders.rubric_judge_grader import RubricJudgeGrader


class SelectionJudgeGrader(RubricJudgeGrader):
    """Scores role relevance, requirement coverage, omissions, and ordering."""

    name = "selection_judge"
    rubric = "selection"
    criteria = (
        "role_relevance",
        "requirement_coverage",
        "omission_quality",
        "ordering",
    )
    output_label = "Experience selection (JSON)"
