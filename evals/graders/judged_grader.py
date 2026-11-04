"""The base of the graders that ask a judge model."""

from evals.graders.grading_context import GradingContext
from evals.models.eval_case import EvalCase
from evals.models.grade import Grade


class JudgedGrader:
    """A grader that needs a judge. The runner asks every judge of the panel.

    Each call sees one judge in its context, and the runner combines the
    judges' grades (see ``evals.graders.judge_panel``). ``applies_to`` says
    whether the grader makes a judge call for a case, which the cost estimate
    counts.
    """

    name: str

    def applies_to(self, case: EvalCase) -> bool:
        """Return True if the grader asks the judge for outputs of ``case``."""
        return True

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Score ``ctx.output`` with the judge in ``ctx``."""
        raise NotImplementedError
