"""Does a judge find every tailored bullet backed by the knowledge base?"""

from typing import Any

from evals.graders.extracted_claims import extract_claims
from evals.graders.grading_context import GradingContext
from evals.graders.judge_call import (
    ask_judge,
    has_judge,
    judge_details,
    load_rubric,
)
from evals.models.faithfulness_judgement import FaithfulnessJudgement
from evals.models.faithfulness_verdict import FaithfulnessVerdict
from evals.models.grade import Grade

PARTIAL_CREDIT = 0.5
MAX_EVIDENCE_CHARS = 300


class FaithfulnessJudgeGrader:
    """A judge's verdict, bullet by bullet, on the tailored content (stage 3).

    A supported bullet scores 1, a partial one 0.5, an unsupported one 0; the
    grade is their mean over all bullets. It passes only when no bullet is
    unsupported, so ``passed`` is False for any fabricated claim (an
    embellished, partial bullet lowers the score but does not fail it). A
    bullet the judge gave no verdict counts as unsupported. Returns None
    without a judge or without bullets, and makes no call in either case.
    """

    name = "faithfulness_judge"

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Ask the judge about the rewritten bullets of ``ctx.output``."""
        claims = extract_claims(ctx.stage, ctx.output)
        bullets = claims.bullets if claims else []
        if not has_judge(ctx) or not bullets:
            return None

        judgement = await ask_judge(
            ctx,
            rubric=load_rubric("faithfulness"),
            user=_user_message(ctx.kb_text, bullets),
            response_model=FaithfulnessJudgement,
        )
        verdicts = _by_index(judgement)
        credit = {"supported": 1.0, "partial": PARTIAL_CREDIT, "unsupported": 0.0}
        score = sum(
            credit[verdicts[i].verdict] if i in verdicts else 0.0
            for i in range(1, len(bullets) + 1)
        ) / len(bullets)
        unsupported = _unsupported(bullets, verdicts)
        return Grade(
            name=self.name,
            score=score,
            passed=not unsupported,
            details={**judge_details(ctx), "unsupported": unsupported},
        )


def _user_message(kb_text: str, bullets: list[str]) -> str:
    numbered = "\n".join(f"{n}. {bullet}" for n, bullet in enumerate(bullets, start=1))
    return f"Knowledge base:\n{kb_text}\n\nBullets to judge:\n{numbered}\n"


def _by_index(judgement: FaithfulnessJudgement) -> dict[int, FaithfulnessVerdict]:
    """Map bullet number to its verdict, keeping the first one given."""
    verdicts: dict[int, FaithfulnessVerdict] = {}
    for item in judgement.items:
        verdicts.setdefault(item.index, item)
    return verdicts


def _unsupported(
    bullets: list[str], verdicts: dict[int, FaithfulnessVerdict]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for number, bullet in enumerate(bullets, start=1):
        verdict = verdicts.get(number)
        if verdict is None or verdict.verdict == "unsupported":
            evidence = verdict.evidence[:MAX_EVIDENCE_CHARS] if verdict else ""
            found.append({"index": number, "bullet": bullet, "evidence": evidence})
    return found
