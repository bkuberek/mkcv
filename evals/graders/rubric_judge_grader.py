"""Scores an output against a rubric of 1 to 5 criteria, using the judge."""

import json

from evals.graders.grading_context import GradingContext
from evals.graders.judge_call import (
    ask_judge,
    has_judge,
    judge_details,
    load_rubric,
)
from evals.graders.judged_grader import JudgedGrader
from evals.models.grade import Grade
from evals.models.rubric_judgement import RubricJudgement

MAX_SCORE = 5


class RubricJudgeGrader(JudgedGrader):
    """Base for the judges that score a stage output on named criteria.

    The grade is the mean criterion score divided by 5. It has no pass
    threshold. A criterion the judge left out is listed in
    ``details["missing_criteria"]`` and does not count. Subclasses set
    ``name``, ``rubric``, ``criteria``, and ``output_label``. Returns None
    without a judge, and makes no call.
    """

    name: str
    rubric: str
    criteria: tuple[str, ...]
    output_label: str

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Ask the judge to score ``ctx.output`` against the rubric."""
        if not has_judge(ctx):
            return None
        if ctx.output is None:
            return Grade(
                name=self.name, details={"error": "the stage produced no output"}
            )

        judgement = await ask_judge(
            ctx,
            rubric=load_rubric(self.rubric),
            prefix=self._prefix(ctx),
            user=self._user_message(ctx),
            response_model=RubricJudgement,
        )
        details = {**judge_details(ctx), "summary": judgement.summary}
        details["criteria"] = [item.model_dump() for item in judgement.criteria]
        scored = {item.name for item in judgement.criteria}
        details["missing_criteria"] = [n for n in self.criteria if n not in scored]
        if not judgement.criteria:
            return Grade(
                name=self.name,
                details={**details, "error": "the judge returned no criteria"},
            )
        mean = sum(item.score for item in judgement.criteria) / len(judgement.criteria)
        return Grade(name=self.name, score=mean / MAX_SCORE, details=details)

    def _prefix(self, ctx: GradingContext) -> str:
        """What every output of the case shares: the job and the knowledge base."""
        return f"Job description:\n{ctx.jd_text}\n\nKnowledge base:\n{ctx.kb_text}\n"

    def _user_message(self, ctx: GradingContext) -> str:
        return f"{self.output_label}:\n{json.dumps(ctx.output, indent=2)}\n"
