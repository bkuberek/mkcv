"""Pick the best model per stage: overall and within each provider.

The rule is quality first. Among the models that passed every hard gate
(``StageSummary.eligible``), the one with the highest primary quality score
wins. Cost matters only for a tie: models whose scores are within
``tie_epsilon`` of the best one count as tied, and the cheapest of them wins.

A win is too close to call when the winner's lead over another eligible
model is smaller than the noise of that lead: the standard error of the
per-case differences between the two (or, with fewer than two shared cases,
of the two run-level means). Those models are listed as runners-up.
"""

import math
import statistics
from collections.abc import Sequence

from evals.graders.stage_graders import PRIMARY_METRIC
from evals.models.recommendation import OVERALL, Recommendation
from evals.models.runner_up import RunnerUp
from evals.models.stage_summary import StageSummary
from evals.stages import stage_position
from mkcv.core.models.stage_key import StageKey

DEFAULT_TIE_EPSILON = 0.01
_EPSILON = 1e-9
NO_ELIGIBLE = "no eligible model"
NO_SCORE = (
    "no eligible model has a quality score (no judge ran, or no case gives one "
    "for this stage)"
)


def recommend(
    summaries: Sequence[StageSummary], *, tie_epsilon: float = DEFAULT_TIE_EPSILON
) -> list[Recommendation]:
    """Return, for each stage, the overall winner and then one per provider.

    Stages come in evaluation order and providers alphabetically. A model with
    an unknown cost ranks after one with a known cost when they tie, and the
    higher score and then the lower p50 latency settle a tie on cost.
    """
    by_stage: dict[StageKey, list[StageSummary]] = {}
    for summary in summaries:
        by_stage.setdefault(summary.stage, []).append(summary)

    recommendations: list[Recommendation] = []
    for stage in sorted(by_stage, key=stage_position):
        group = by_stage[stage]
        recommendations.append(_pick(stage, OVERALL, group, tie_epsilon))
        for provider in sorted({s.provider for s in group}):
            members = [s for s in group if s.provider == provider]
            recommendations.append(_pick(stage, provider, members, tie_epsilon))
    return recommendations


def _pick(
    stage: StageKey, scope: str, group: list[StageSummary], tie_epsilon: float
) -> Recommendation:
    eligible = [summary for summary in group if summary.eligible]
    if not eligible:
        return Recommendation(stage=stage, scope=scope, reason=NO_ELIGIBLE)
    scored = [summary for summary in eligible if summary.primary_score is not None]
    if not scored:
        return Recommendation(stage=stage, scope=scope, reason=NO_SCORE)

    top = max(_score(summary) for summary in scored)
    tied = [s for s in scored if _score(s) >= top - tie_epsilon - _EPSILON]
    winner = min(tied, key=_tie_rank)
    others = [_label(s) for s in tied if s is not winner]
    runners_up = _runners_up(winner, [s for s in scored if s is not winner])
    return Recommendation(
        stage=stage,
        scope=scope,
        provider=winner.provider,
        model=winner.model,
        score=winner.primary_score,
        std=winner.primary_std,
        decided_by_cost=bool(others),
        tied_with=others,
        too_close_to_call=bool(runners_up),
        runners_up=runners_up,
        reason=_reason(stage, winner, others, tie_epsilon, runners_up),
    )


def _runners_up(winner: StageSummary, others: list[StageSummary]) -> list[RunnerUp]:
    found: list[RunnerUp] = []
    for other in sorted(others, key=lambda s: -_score(s)):
        margin = _score(winner) - _score(other)
        noise = lead_noise(winner, other)
        if noise is not None and margin < noise - _EPSILON:
            found.append(
                RunnerUp(
                    label=_label(other), score=_score(other), margin=margin, noise=noise
                )
            )
    return found


def lead_noise(winner: StageSummary, other: StageSummary) -> float | None:
    """Return the standard error of ``winner``'s lead over ``other``.

    Paired by case when they share at least two cases (the deviation of the
    per-case differences over the square root of their count); otherwise from
    both models' run-level deviations. None when neither can be estimated.
    """
    shared = [case for case in winner.case_scores if case in other.case_scores]
    if len(shared) >= 2:
        leads = [winner.case_scores[c] - other.case_scores[c] for c in shared]
        return statistics.stdev(leads) / math.sqrt(len(leads))
    if (
        winner.primary_std is not None
        and other.primary_std is not None
        and winner.primary_n >= 2
        and other.primary_n >= 2
    ):
        return math.sqrt(
            winner.primary_std**2 / winner.primary_n
            + other.primary_std**2 / other.primary_n
        )
    return None


def _reason(
    stage: StageKey,
    winner: StageSummary,
    tied: list[str],
    tie_epsilon: float,
    runners_up: list[RunnerUp],
) -> str:
    metric = PRIMARY_METRIC.get(stage, "quality")
    reason = f"highest {metric}: {_score(winner):.2f}"
    if tied:
        reason += (
            f"; within {tie_epsilon} of {', '.join(tied)}, so the cheaper model "
            f"was chosen ({_usd(winner.cost_mean_usd)} per run)"
        )
    if runners_up:
        reason += "; too close to call with " + ", ".join(
            f"{r.label} ({r.score:.2f}, lead {r.margin:.2f} < noise {r.noise:.2f})"
            for r in runners_up
        )
    return reason


def _label(summary: StageSummary) -> str:
    return f"{summary.provider}/{summary.model}"


def _score(summary: StageSummary) -> float:
    assert summary.primary_score is not None
    return summary.primary_score


def _unknown_last(value: float | None) -> float:
    return math.inf if value is None else value


def _tie_rank(summary: StageSummary) -> tuple[float, float, float]:
    return (
        _unknown_last(summary.cost_mean_usd),
        -_score(summary),
        _unknown_last(summary.latency_p50_s),
    )


def _usd(amount: float | None) -> str:
    return "unknown cost" if amount is None else f"${amount:.4f}"
