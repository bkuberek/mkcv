"""Aggregate a run's records into one summary per (stage, provider, model)."""

import statistics
from collections.abc import Sequence

from evals.graders.stage_graders import PRIMARY_METRIC
from evals.models.eval_record import EvalRecord
from evals.models.recommendation_settings import RecommendationSettings
from evals.models.stage_summary import StageSummary
from evals.stages import stage_position
from mkcv.core.models.stage_key import StageKey

LOW_SAMPLE_BELOW = 6
MIN_OK_RATE = 0.95
MIN_SCHEMA = 0.95
MIN_FAITHFULNESS_EXTRACTION = 0.95
MIN_FAITHFULNESS_JUDGE = 0.90
FAITHFULNESS_GRADES = ("faithfulness_extraction", "faithfulness_judge")
"""Grades whose failed runs count as fabrications (``passed`` is False)."""
MEDIAN = 0.5
P90 = 0.9
_EPSILON = 1e-9

_MEAN_FLOORS = {
    "faithfulness_extraction": MIN_FAITHFULNESS_EXTRACTION,
    "faithfulness_judge": MIN_FAITHFULNESS_JUDGE,
}

_Key = tuple[StageKey, str, str]


def aggregate(
    records: Sequence[EvalRecord], settings: RecommendationSettings | None = None
) -> list[StageSummary]:
    """Return a summary for every (stage, provider, model) with attempted runs.

    Skipped records do not count. Summaries come in evaluation order, then by
    provider and model. ``settings`` gives the tolerated fabrication rate
    (none by default).
    """
    rules = settings or RecommendationSettings()
    groups: dict[_Key, list[EvalRecord]] = {}
    for record in records:
        if record.status != "skipped":
            key = (record.stage, record.provider, record.model)
            groups.setdefault(key, []).append(record)
    ordered = sorted(groups, key=lambda k: (stage_position(k[0]), k[1], k[2]))
    return [_summarize(key, groups[key], rules) for key in ordered]


def gate_failures(
    ok_rate: float,
    mean: dict[str, float],
    fabrication_rate: dict[str, float],
    settings: RecommendationSettings,
) -> list[str]:
    """Return the hard gates a model missed, or an empty list if it passed all.

    A model needs an ok rate and schema score of at least 0.95. Where the
    stage has faithfulness grades, no more than ``max_fabrication_rate`` of
    its runs may contain a fabricated claim (none by default), its
    deterministic faithfulness mean must reach 0.95, and its judged one 0.90.
    """
    failures: list[str] = []
    if ok_rate < MIN_OK_RATE - _EPSILON:
        failures.append(f"ok rate below {MIN_OK_RATE}")
    schema = mean.get("schema")
    if schema is None or schema < MIN_SCHEMA - _EPSILON:
        failures.append(f"schema below {MIN_SCHEMA}")
    for name in FAITHFULNESS_GRADES:
        rate = fabrication_rate.get(name)
        if rate is not None and rate > settings.max_fabrication_rate + _EPSILON:
            failures.append(
                f"{name}: fabricated in {rate:.0%} of runs "
                f"(max {settings.max_fabrication_rate:.0%})"
            )
        value = mean.get(name)
        if value is not None and value < _MEAN_FLOORS[name] - _EPSILON:
            failures.append(f"{name} below {_MEAN_FLOORS[name]}")
    return failures


def _summarize(
    key: _Key, records: list[EvalRecord], settings: RecommendationSettings
) -> StageSummary:
    stage, provider, model = key
    ok = [record for record in records if record.status == "ok"]
    ok_rate = len(ok) / len(records)
    mean = _grade_means(ok)
    fabrication = _fabrication_rates(ok)
    failures = gate_failures(ok_rate, mean, fabrication, settings)
    latencies = sorted(record.latency_s for record in ok)
    return StageSummary(
        stage=stage,
        provider=provider,
        model=model,
        n=len(records),
        ok_rate=ok_rate,
        mean=mean,
        primary_score=mean.get(PRIMARY_METRIC.get(stage, "")),
        cost_mean_usd=statistics.fmean(r.cost_usd for r in ok) if ok else None,
        latency_p50_s=_percentile(latencies, MEDIAN),
        latency_p90_s=_percentile(latencies, P90),
        median_input_tokens=_median([r.input_tokens for r in ok]),
        median_output_tokens=_median([r.output_tokens for r in ok]),
        fabrication_rate=fabrication,
        eligible=not failures,
        gate_failures=failures,
        self_judged=any(
            grade.details.get("self_judged") is True
            for record in ok
            for grade in record.grades
        ),
        low_sample=len(records) < LOW_SAMPLE_BELOW,
    )


def _grade_means(ok_records: list[EvalRecord]) -> dict[str, float]:
    scores: dict[str, list[float]] = {}
    for record in ok_records:
        for grade in record.grades:
            if grade.score is not None:
                scores.setdefault(grade.name, []).append(grade.score)
    return {name: statistics.fmean(values) for name, values in scores.items()}


def _fabrication_rates(ok_records: list[EvalRecord]) -> dict[str, float]:
    """Share of runs whose faithfulness grade failed, per grade that says so."""
    outcomes: dict[str, list[bool]] = {}
    for record in ok_records:
        for grade in record.grades:
            if grade.name in FAITHFULNESS_GRADES and grade.passed is not None:
                outcomes.setdefault(grade.name, []).append(not grade.passed)
    return {
        name: sum(failed) / len(failed) for name, failed in outcomes.items() if failed
    }


def _median(values: list[int]) -> float | None:
    return float(statistics.median(values)) if values else None


def _percentile(sorted_values: list[float], fraction: float) -> float | None:
    """Return the ``fraction`` quantile, interpolating between neighbours."""
    if not sorted_values:
        return None
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (
        position - lower
    )
