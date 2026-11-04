"""Combine the grades every panel judge gave one output into a single grade."""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from evals.models.grade import Grade
from evals.models.judge_score import JudgeScore

AGREEMENT_SPREAD = 0.1
"""Judges agree on an output when their scores are at most this far apart."""


@dataclass(frozen=True)
class PanelVerdict:
    """What one judge of the panel made of an output (None: did not apply)."""

    judge: str
    provider: str
    grade: Grade | None


def combine_panel(
    name: str, verdicts: Sequence[PanelVerdict], *, evaluated_provider: str
) -> Grade | None:
    """Return the panel's grade, or None when no judge's grader applied.

    - ``score`` is the mean of the judges that scored the output.
    - ``independent_score`` leaves out the judge from ``evaluated_provider``;
      it is None when only that judge scored, and the grade is then
      self-judged.
    - ``passed`` is decided by the independent judges (all judges when there
      is none): it fails when at least half of them fail it, so one judge in
      two finding a fabrication is enough.
    - ``details`` lists the judges that scored, whether the grade is
      self-judged, the spread between the highest and lowest score, and the
      errors when no judge produced a score.
    """
    judged = [verdict for verdict in verdicts if verdict.grade is not None]
    if not judged:
        return None
    scores = [_judge_score(verdict, evaluated_provider) for verdict in judged]
    scored = [s for s in scores if s.score is not None]
    independent = [s for s in scored if not s.self_judged]
    details: dict[str, object] = {
        "judges": [s.judge for s in scored],
        "self_judged": bool(scored) and not independent,
        "spread": _spread(scored),
    }
    if not scored:
        details["error"] = "; ".join(
            f"{s.judge}: {s.details.get('error', 'no score')}" for s in scores
        )
    return Grade(
        name=name,
        score=_mean(scored),
        passed=_passed(scores),
        details=details,
        independent_score=_mean(independent),
        judge_scores=scores,
    )


def _judge_score(verdict: PanelVerdict, evaluated_provider: str) -> JudgeScore:
    assert verdict.grade is not None
    return JudgeScore(
        judge=verdict.judge,
        provider=verdict.provider,
        score=verdict.grade.score,
        passed=verdict.grade.passed,
        self_judged=verdict.provider == evaluated_provider,
        details=verdict.grade.details,
    )


def _mean(scores: Sequence[JudgeScore]) -> float | None:
    values = [s.score for s in scores if s.score is not None]
    return statistics.fmean(values) if values else None


def _spread(scores: Sequence[JudgeScore]) -> float | None:
    values = [s.score for s in scores if s.score is not None]
    return max(values) - min(values) if len(values) >= 2 else None


def _passed(scores: Sequence[JudgeScore]) -> bool | None:
    flagged = [s for s in scores if s.passed is not None]
    independent = [s for s in flagged if not s.self_judged]
    deciding = independent or flagged
    if not deciding:
        return None
    failing = sum(1 for s in deciding if s.passed is False)
    return failing * 2 < len(deciding)
