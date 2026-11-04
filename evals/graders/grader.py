"""The interface every grader implements."""

from typing import Protocol

from evals.graders.grading_context import GradingContext
from evals.models.grade import Grade


class Grader(Protocol):
    """Scores one stage output; the grade's name is the grader's name."""

    @property
    def name(self) -> str:
        """The grade name this grader produces (``schema``, ``ats_rules``, ...)."""
        ...

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Score ``ctx.output``.

        The grade's ``score`` is None when the output cannot be scored; the
        grader returns None when it does not apply (a judge grader without a
        judge, or the review defect grader on a case with no seeded defects).
        """
        ...
