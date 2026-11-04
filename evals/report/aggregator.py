"""Aggregate a run's records into one summary per (stage, provider, model)."""

import statistics
from collections.abc import Sequence

from evals.graders.stage_graders import PRIMARY_METRIC
from evals.models.eval_record import EvalRecord
from evals.models.stage_summary import StageSummary
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

LOW_SAMPLE_BELOW = 6
MIN_OK_RATE = 0.95
MIN_SCHEMA = 0.95
MIN_FAITHFULNESS_EXTRACTION = 0.95
MIN_FAITHFULNESS_JUDGE = 0.90
MEDIAN = 0.5
P90 = 0.9
_EPSILON = 1e-9

_STAGE_ORDER = {stage: position for position, stage in enumerate(PIPELINE_STAGES)}

_Key = tuple[StageKey, str, str]


def aggregate(records: Sequence[EvalRecord]) -> list[StageSummary]:
    """Return a summary for every (stage, provider, model) with attempted runs.

    Skipped records do not count. Summaries come in pipeline order, then by
    provider and model.
    """
    groups: dict[_Key, list[EvalRecord]] = {}
    for record in records:
        if record.status != "skipped":
            key = (record.stage, record.provider, record.model)
            groups.setdefault(key, []).append(record)
    ordered = sorted(
        groups, key=lambda k: (_STAGE_ORDER.get(k[0], len(_STAGE_ORDER)), k[1], k[2])
    )
    return [_summarize(key, groups[key]) for key in ordered]


def ineligible_reasons(ok_rate: float, mean: dict[str, float]) -> list[str]:
    """Return why a model cannot be recommended, or an empty list if it can.

    A model needs an ok rate and schema score of at least 0.95; where the
    stage has them, a deterministic faithfulness mean of at least 0.95 and a
    judged one of at least 0.90.
    """
    reasons: list[str] = []
    if ok_rate < MIN_OK_RATE - _EPSILON:
        reasons.append(f"ok rate below {MIN_OK_RATE}")
    schema = mean.get("schema")
    if schema is None or schema < MIN_SCHEMA - _EPSILON:
        reasons.append(f"schema below {MIN_SCHEMA}")
    for name, floor in (
        ("faithfulness_extraction", MIN_FAITHFULNESS_EXTRACTION),
        ("faithfulness_judge", MIN_FAITHFULNESS_JUDGE),
    ):
        value = mean.get(name)
        if value is not None and value < floor - _EPSILON:
            reasons.append(f"{name} below {floor}")
    return reasons


def _summarize(key: _Key, records: list[EvalRecord]) -> StageSummary:
    stage, provider, model = key
    ok = [record for record in records if record.status == "ok"]
    ok_rate = len(ok) / len(records)
    mean = _grade_means(ok)
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
        eligible=not ineligible_reasons(ok_rate, mean),
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
