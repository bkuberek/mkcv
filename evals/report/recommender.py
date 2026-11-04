"""Pick the best, recommended, and economy model per stage and provider."""

import math
from collections.abc import Sequence

from evals.graders.stage_graders import PRIMARY_METRIC
from evals.models.recommendation import Recommendation
from evals.models.stage_summary import StageSummary
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

RECOMMENDED_MARGIN = 0.05
ECONOMY_MIN_SCORE = 0.70
_EPSILON = 1e-9

_STAGE_ORDER = {stage: position for position, stage in enumerate(PIPELINE_STAGES)}


def recommend(summaries: Sequence[StageSummary]) -> list[Recommendation]:
    """Return one recommendation per (stage, provider) in ``summaries``.

    Among the eligible models that have a quality score:

    - ``best`` has the highest score (ties: lower cost, then lower p50 latency).
    - ``recommended`` is the cheapest whose score is within 0.05 of the best.
    - ``economy`` is the cheapest that scores at least 0.70.

    A model with an unknown cost or latency ranks after one with a known value.
    """
    groups: dict[tuple[StageKey, str], list[StageSummary]] = {}
    for summary in summaries:
        groups.setdefault((summary.stage, summary.provider), []).append(summary)
    ordered = sorted(
        groups, key=lambda k: (_STAGE_ORDER.get(k[0], len(_STAGE_ORDER)), k[1])
    )
    return [
        _recommend(stage, provider, groups[stage, provider])
        for stage, provider in ordered
    ]


def _recommend(
    stage: StageKey, provider: str, group: list[StageSummary]
) -> Recommendation:
    eligible = [summary for summary in group if summary.eligible]
    if not eligible:
        return _none(stage, provider, "no eligible model")
    scored = [summary for summary in eligible if summary.primary_score is not None]
    if not scored:
        return _none(
            stage,
            provider,
            "no quality score for any eligible model (is the judge available?)",
        )

    best = min(scored, key=_best_rank)
    best_score = _score(best)
    recommended = min(
        (s for s in scored if _score(s) >= best_score - RECOMMENDED_MARGIN - _EPSILON),
        key=_cheapest_rank,
    )
    economy = min(
        (s for s in scored if _score(s) >= ECONOMY_MIN_SCORE - _EPSILON),
        key=_cheapest_rank,
        default=None,
    )
    metric = PRIMARY_METRIC.get(stage, "quality")
    reason = (
        f"best {metric} {best_score:.2f} ({best.model}); the cheapest within "
        f"{RECOMMENDED_MARGIN} of it is {recommended.model} "
        f"({_usd(recommended.cost_mean_usd)} per run)"
    )
    if economy is None:
        reason += f"; no eligible model scores {ECONOMY_MIN_SCORE} or more"
    return Recommendation(
        stage=stage,
        provider=provider,
        best=best.model,
        recommended=recommended.model,
        economy=economy.model if economy else None,
        reason=reason,
    )


def _none(stage: StageKey, provider: str, reason: str) -> Recommendation:
    return Recommendation(stage=stage, provider=provider, reason=reason)


def _score(summary: StageSummary) -> float:
    assert summary.primary_score is not None
    return summary.primary_score


def _unknown_last(value: float | None) -> float:
    return math.inf if value is None else value


def _best_rank(summary: StageSummary) -> tuple[float, float, float]:
    return (
        -_score(summary),
        _unknown_last(summary.cost_mean_usd),
        _unknown_last(summary.latency_p50_s),
    )


def _cheapest_rank(summary: StageSummary) -> tuple[float, float, float]:
    return (
        _unknown_last(summary.cost_mean_usd),
        -_score(summary),
        _unknown_last(summary.latency_p50_s),
    )


def _usd(amount: float | None) -> str:
    return "unknown cost" if amount is None else f"${amount:.4f}"
