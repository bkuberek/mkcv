"""Estimate what a matrix run would cost before any model is called."""

from collections.abc import Mapping, Sequence

from evals.graders.stage_graders import judge_calls
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import EvalCase
from evals.models.matrix_config import MatrixConfig
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_report import summarize_costs

JUDGE_INPUT_TOKENS = 6000
JUDGE_OUTPUT_TOKENS = 1500
"""Planning size of one judge call (design section 9.8)."""

_TOKENS_PER_MILLION = 1_000_000


def estimate_matrix_cost(
    matrix: MatrixConfig,
    cases: Sequence[EvalCase],
    catalog: ModelCatalog,
    *,
    skipped_judges: Mapping[str, str] | None = None,
) -> CostEstimate:
    """Estimate the cost of running ``matrix`` over ``cases``.

    Each model is charged the stage requirements' token estimates for every
    (case, stage, repeat) it runs. Every judge of the panel scores every
    judged output, so each judge is charged every judge call at its own
    price. A model or judge without a catalog price costs None.

    Args:
        matrix: The models, stages, and judges to price.
        cases: The cases to run.
        catalog: Where prices come from.
        skipped_judges: Judges that will not run (no credentials), with the
            reason, by ``provider/model``. Their calls are left out; the
            reasons are kept only if the run would have made judge calls.
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

    calls = len(matrix.models) * repeats * sum(judge_calls(c, s) for c, s in runs)
    skipped = dict(skipped_judges or {}) if calls else {}
    judges = [] if not calls else [j for j in matrix.panel if j.label not in skipped]
    judge_costs = {
        judge.label: _judge_cost(
            catalog.price_for(judge.model, provider=judge.provider), calls
        )
        for judge in judges
    }
    judge_total, _ = (
        summarize_costs(list(judge_costs.values())) if judge_costs else (0.0, False)
    )
    known_costs = [*model_costs.values(), *judge_costs.values()]
    total, is_partial = summarize_costs(known_costs) if known_costs else (0.0, False)
    return CostEstimate(
        runs_per_model=len(runs) * repeats,
        model_costs=model_costs,
        judges=[judge.label for judge in judges],
        judge_calls=calls,
        judge_costs=judge_costs,
        judge_cost_usd=judge_total,
        provider_costs=_by_provider(model_costs, judge_costs),
        total_usd=total,
        is_partial=is_partial,
        skipped_judges=skipped,
    )


def _by_provider(*costs: Mapping[str, float | None]) -> dict[str, float | None]:
    """Sum ``provider/model`` costs per provider, in first-seen order."""
    grouped: dict[str, list[float | None]] = {}
    for table in costs:
        for label, cost in table.items():
            grouped.setdefault(label.partition("/")[0], []).append(cost)
    return {
        provider: summarize_costs(values)[0] for provider, values in grouped.items()
    }


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
