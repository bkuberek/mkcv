"""Does a judge find every sentence of the cover letter backed by the KB?"""

from evals.graders.cover_letter_text import load_letter, sentences
from evals.graders.faithfulness_judge_grader import FaithfulnessJudgeGrader, numbered
from evals.graders.grading_context import GradingContext


class CoverLetterFaithfulnessJudgeGrader(FaithfulnessJudgeGrader):
    """The faithfulness judge on a cover letter, sentence by sentence.

    It shares its name and scoring with the tailored content's judge, so the
    same hard gate applies. The judge also sees the job description (claims
    about the employer may come from it) and what the letter must not claim.
    """

    rubric = "cover_letter_faithfulness"

    def _claims(self, ctx: GradingContext) -> list[str]:
        try:
            return sentences(load_letter(ctx.output))
        except ValueError:
            return []

    def _user_message(self, ctx: GradingContext, bullets: list[str]) -> str:
        rules = [*ctx.case.cover_letter_forbidden, *ctx.case.letter.must_not]
        forbidden = "\n".join(f"- {rule}" for rule in rules)
        return (
            f"Knowledge base:\n{ctx.kb_text}\n\n"
            f"Job description:\n{ctx.jd_text}\n\n"
            f"Must not claim:\n{forbidden or '- (nothing listed)'}\n\n"
            f"Sentences to judge:\n{numbered(bullets)}\n"
        )
