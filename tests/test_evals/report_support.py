"""Builders for synthetic records, summaries, and manifests in report tests."""

from datetime import UTC, datetime
from typing import Any, Literal

from evals.models.eval_record import EvalRecord
from evals.models.grade import Grade
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.recommendation import OVERALL, Recommendation
from evals.models.run_manifest import RunManifest
from evals.models.run_settings import RunSettings
from evals.models.stage_summary import StageSummary
from mkcv.core.models.stage_key import StageKey

RUN_ID = "20261104-010203-abc1234"
JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")


def grade(
    name: str, score: float | None, *, passed: bool | None = None, **details: Any
) -> Grade:
    """A grade with the given score, pass flag, and details."""
    return Grade(name=name, score=score, passed=passed, details=details)


def record(
    *,
    stage: StageKey = StageKey.TAILOR,
    provider: str = "openai",
    model: str = "gpt-6.1-sol",
    status: Literal["ok", "error", "skipped"] = "ok",
    case: str = "case-a",
    repeat: int = 0,
    cost: float = 0.10,
    latency: float = 1.0,
    input_tokens: int = 1000,
    output_tokens: int = 500,
    grades: list[Grade] | None = None,
) -> EvalRecord:
    """A record; an error or skipped one carries no tokens, cost, or grades."""
    ok = status == "ok"
    return EvalRecord(
        run_id=RUN_ID,
        case_id=case,
        stage=stage,
        provider=provider,
        model=model,
        repeat=repeat,
        status=status,
        error=None if ok else "boom",
        input_tokens=input_tokens if ok else 0,
        output_tokens=output_tokens if ok else 0,
        cost_usd=cost if ok else 0.0,
        latency_s=latency if ok else 0.0,
        grades=(grades or []) if ok else [],
    )


def summary(
    *,
    stage: StageKey = StageKey.TAILOR,
    provider: str = "openai",
    model: str = "gpt-6.1-sol",
    n: int = 10,
    ok_rate: float = 1.0,
    mean: dict[str, float] | None = None,
    primary_score: float | None = 0.9,
    cost: float | None = 0.10,
    p50: float | None = 2.0,
    p90: float | None = 3.0,
    median_in: float | None = 1000.0,
    median_out: float | None = 500.0,
    eligible: bool = True,
    gate_failures: list[str] | None = None,
    self_judged: bool = False,
) -> StageSummary:
    """A stage summary; ``low_sample`` follows ``n`` as the aggregator sets it.

    An ineligible summary without ``gate_failures`` gets a placeholder one.
    """
    return StageSummary(
        stage=stage,
        provider=provider,
        model=model,
        n=n,
        ok_rate=ok_rate,
        mean=mean if mean is not None else {"schema": 1.0},
        primary_score=primary_score,
        cost_mean_usd=cost,
        latency_p50_s=p50,
        latency_p90_s=p90,
        median_input_tokens=median_in,
        median_output_tokens=median_out,
        eligible=eligible,
        gate_failures=(
            gate_failures
            if gate_failures is not None
            else ([] if eligible else ["schema below 0.95"])
        ),
        self_judged=self_judged,
        low_sample=n < 6,
    )


def recommendation(
    *,
    stage: StageKey = StageKey.TAILOR,
    scope: str = OVERALL,
    provider: str | None = "openai",
    model: str | None = "gpt-6.1-sol",
    score: float | None = 0.9,
    reason: str = "because",
    **fields: Any,
) -> Recommendation:
    """A recommendation; a missing model also has no provider or score."""
    return Recommendation(
        stage=stage,
        scope=scope,
        provider=provider if model else None,
        model=model,
        score=score if model else None,
        reason=reason,
        **fields,
    )


def manifest(
    *,
    models: list[MatrixModel] | None = None,
    skipped_models: list[str] | None = None,
    judge_skipped: str | None = None,
    cases: list[str] | None = None,
) -> RunManifest:
    """A finished run manifest."""
    return RunManifest(
        run_id=RUN_ID,
        started_at=datetime(2026, 11, 4, 1, 2, 3, tzinfo=UTC),
        finished_at=datetime(2026, 11, 4, 1, 40, 0, tzinfo=UTC),
        mkcv_version="1.3.0",
        git_sha="abc1234",
        matrix=MatrixConfig(
            run=RunSettings(),
            judge=JUDGE,
            reference=JUDGE,
            models=models or [MatrixModel(provider="openai", model="gpt-6.1-sol")],
        ),
        judge=JUDGE,
        cases=cases or ["case-a", "case-b"],
        skipped_models=skipped_models or [],
        judge_skipped=judge_skipped,
    )
