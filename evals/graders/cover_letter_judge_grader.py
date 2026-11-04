"""A judge's score for the cover letter's persuasiveness and specificity."""

from evals.graders.grading_context import GradingContext
from evals.graders.rubric_judge_grader import RubricJudgeGrader


class CoverLetterJudgeGrader(RubricJudgeGrader):
    """Scores evidence, specificity, persuasiveness, and tone (1 to 5 each).

    When the case lists ``should_connect``, the judge sees those connections
    between the knowledge base and the job as what a strong letter makes.
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

    def _user_message(self, ctx: GradingContext) -> str:
        message = super()._user_message(ctx)
        hints = ctx.case.cover_letter.should_connect
        if not hints:
            return message
        listed = "\n".join(f"- {hint}" for hint in hints)
        return f"{message}\nA strong letter for this job connects:\n{listed}\n"
