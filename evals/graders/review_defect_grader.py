"""Did the resume review catch the defects planted in the review probe?"""

from evals.graders.defect_recall_grader import DefectRecallGrader
from evals.models.eval_case import EvalCase


class ReviewDefectGrader(DefectRecallGrader):
    """Recall of the resume review probe's seeded defects (stage 5)."""

    name = "review_defect_recall"
    rubric = "review_defects"

    def defects(self, case: EvalCase) -> list[str]:
        """The case's ``review_probe_defects``."""
        return case.review_probe_defects
