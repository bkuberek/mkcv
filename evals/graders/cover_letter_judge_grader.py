"""A judge's score for the cover letter's persuasiveness and specificity."""

from evals.graders.grading_context import GradingContext
from evals.graders.rubric_judge_grader import RubricJudgeGrader


class CoverLetterJudgeGrader(RubricJudgeGrader):
    """Scores evidence, specificity, persuasiveness, and tone (1 to 5 each).

    The judge also sees the case's ``must``, ``should_connect``, and
    ``must_not`` guidance when it has any.
    """

    name = "cover_letter_judge"
    rubric = "cover_letter"
    criteria = (
        "evidence_connection",
        "specificity",
        "persuasiveness",
        "professional_tone",
    )
    output_label = "Cover letter (JSON)"

    def _prefix(self, ctx: GradingContext) -> str:
        message = super()._prefix(ctx)
        letter = ctx.case.letter
        for heading, items in (
            ("A great letter for this job must", letter.must),
            ("A strong letter for this job connects", letter.should_connect),
            ("The letter must not", letter.must_not),
        ):
            if items:
                listed = "\n".join(f"- {item}" for item in items)
                message += f"\n{heading}:\n{listed}\n"
        return message
