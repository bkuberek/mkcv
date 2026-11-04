"""Did the analysis pick up the job description's key terms?"""

import json

from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import contains_term
from evals.models.grade import Grade

PASS_THRESHOLD = 0.8


class JdRecallGrader:
    """Fraction of the case's expected keywords found in the analysis.

    A keyword counts when it appears as a whole word, in any case, anywhere in
    the analysis (so ``Go`` is not found inside ``ongoing``). It passes at 0.8.
    """

    name = "jd_keyword_recall"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Score the analysis; None when the case lists no expected keywords."""
        keywords = ctx.case.expected_keywords
        if not keywords:
            return Grade(
                name=self.name, details={"reason": "the case has no expected keywords"}
            )
        text = json.dumps(ctx.output, ensure_ascii=False)
        missing = [word for word in keywords if not contains_term(text, word)]
        score = (len(keywords) - len(missing)) / len(keywords)
        return Grade(
            name=self.name,
            score=score,
            passed=score >= PASS_THRESHOLD,
            details={"missing": missing},
        )
