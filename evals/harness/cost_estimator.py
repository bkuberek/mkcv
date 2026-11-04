"""Estimate what a matrix run would cost before any model is called."""

from collections.abc import Sequence

from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import EvalCase
from evals.models.matrix_config import MatrixConfig
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_report import summarize_costs
from mkcv.core.models.stage_key import StageKey

JUDGE_INPUT_TOKENS = 6000
JUDGE_OUTPUT_TOKENS = 1500
"""Planning size of one judge call (design section 9.8)."""

_TOKENS_PER_MILLION = 1_000_000

_JUDGE_CALLS_PER_RUN: dict[StageKey, int] = {
    StageKey.SELECT: 1,  # selection_judge
    StageKey.TAILOR: 2,  # faithfulness_judge and tailoring_judge
}
"""Judge calls one evaluated run makes, per the grader table in design 9.6."""


def estimate_matrix_cost(
    matrix: MatrixConfig,
    cases: Sequence[EvalCase],
    catalog: ModelCatalog,
    *,
    judge_skipped: str | None = None,
) -> CostEstimate:
    """Estimate the cost of running ``matrix`` over ``cases``.

    Each model is charged the stage requirements' token estimates for every
    (case, stage, repeat) it runs; judge calls are charged at the judge
    model's price. A model without a catalog price costs None.

    Args:
        matrix: The models, stages, and judge to price.
        cases: The cases to run.
        catalog: Where prices come from.
        judge_skipped: Why the judge will not run (no API key). Its calls are
            then left out; the reason is kept only if the run would have made
            judge calls.
    """
    runs = [
        (case, stage)
        for case in cases
        for stage in matrix.run.stages
        if case.applies_to(stage)
    ]
    repeats = matrix.run.repeats
    input_tokens = repeats * sum(
        STAGE_REQUIREMENTS[s].est_input_tokens for _, s in runs
    )
    output_tokens = repeats * sum(
        STAGE_REQUIREMENTS[s].est_output_tokens for _, s in runs
    )

    model_costs = {
        model.label: _price_tokens(
            catalog.price_for(model.model, provider=model.provider),
            input_tokens,
            output_tokens,
        )
        for model in matrix.models
    }

    planned_judge_calls = (
        len(matrix.models) * repeats * sum(_judge_calls(c, s) for c, s in runs)
    )
    skipped = judge_skipped if planned_judge_calls else None
    judge_calls = 0 if skipped else planned_judge_calls
    judge_cost = _judge_cost(
        catalog.price_for(matrix.judge.model, provider=matrix.judge.provider),
        judge_calls,
    )
    known_costs = [*model_costs.values(), *([judge_cost] if judge_calls else [])]
    total, is_partial = summarize_costs(known_costs)
    return CostEstimate(
        runs_per_model=len(runs) * repeats,
        model_costs=model_costs,
        judge=matrix.judge.label,
        judge_calls=judge_calls,
        judge_cost_usd=judge_cost,
        total_usd=total,
        is_partial=is_partial,
        judge_skipped=skipped,
    )


def _judge_calls(case: EvalCase, stage: StageKey) -> int:
    if stage is StageKey.REVIEW:
        return 1 if case.review_probe_defects else 0
    return _JUDGE_CALLS_PER_RUN.get(stage, 0)


def _judge_cost(price: tuple[float, float] | None, calls: int) -> float | None:
    if calls == 0:
        return 0.0
    return _price_tokens(price, calls * JUDGE_INPUT_TOKENS, calls * JUDGE_OUTPUT_TOKENS)


def _price_tokens(
    price: tuple[float, float] | None, input_tokens: int, output_tokens: int
) -> float | None:
    if price is None:
        return None
    input_price, output_price = price
    return (input_tokens * input_price + output_tokens * output_price) / (
        _TOKENS_PER_MILLION
    )
