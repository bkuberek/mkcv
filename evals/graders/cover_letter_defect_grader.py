"""Did the cover letter review catch the defects planted in the letter?"""

from evals.graders.defect_recall_grader import DefectRecallGrader
from evals.models.eval_case import EvalCase


class CoverLetterDefectGrader(DefectRecallGrader):
    """Recall of a cover letter probe's seeded defects (``cover_letter.review``)."""

    name = "cover_letter_defect_recall"
    rubric = "cover_letter_review_defects"

    def defects(self, case: EvalCase) -> list[str]:
        """The case's ``cover_letter.review_defects``."""
        return case.letter.review_defects
