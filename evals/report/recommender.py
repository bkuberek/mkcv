"""Pick the best model per stage: overall and within each provider.

The rule is quality first. Among the models that passed every hard gate
(``StageSummary.eligible``), the one with the highest primary quality score
wins. Cost matters only for a tie: models whose scores are within
``tie_epsilon`` of the best one count as tied, and the cheapest of them wins.
"""

import math
from collections.abc import Sequence

from evals.graders.stage_graders import PRIMARY_METRIC
from evals.models.recommendation import OVERALL, Recommendation
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
    return Recommendation(
        stage=stage,
        scope=scope,
        provider=winner.provider,
        model=winner.model,
        score=winner.primary_score,
        decided_by_cost=bool(others),
        tied_with=others,
        reason=_reason(stage, winner, others, tie_epsilon),
    )


def _reason(
    stage: StageKey, winner: StageSummary, tied: list[str], tie_epsilon: float
) -> str:
    metric = PRIMARY_METRIC.get(stage, "quality")
    reason = f"highest {metric}: {_score(winner):.2f}"
    if tied:
        reason += (
            f"; within {tie_epsilon} of {', '.join(tied)}, so the cheaper model "
            f"was chosen ({_usd(winner.cost_mean_usd)} per run)"
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
