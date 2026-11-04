"""Estimate what a matrix run would cost before any model is called."""

import math
from collections.abc import Callable, Mapping, Sequence

from evals.graders.stage_graders import judge_calls
from evals.harness.tournament import screening_cases, screening_judge
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import EvalCase
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.tournament_estimate import TournamentEstimate
from evals.models.tournament_settings import TournamentSettings
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
    judges_for: Callable[[MatrixModel], Sequence[JudgeConfig]] | None = None,
) -> CostEstimate:
    """Estimate the cost of running ``matrix`` over ``cases`` in one round.

    Each model is charged the stage requirements' token estimates for every
    (case, stage, repeat) it runs. By default every judge of the panel
    scores every judged output, so each judge is charged every judge call at
    its own price; ``judges_for`` narrows the judges of a model's outputs (the
    screening round uses one). A model or judge without a catalog price costs
    None.

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

    judged = matrix.run.judged_stages
    per_model = repeats * sum(judge_calls(c, s, judged=judged) for c, s in runs)
    skipped = dict(skipped_judges or {}) if per_model and matrix.models else {}
    panel = [judge for judge in matrix.panel if judge.label not in skipped]
    counts: dict[str, int] = {}
    configs: dict[str, JudgeConfig] = {}
    for model in matrix.models if per_model else []:
        for judge in judges_for(model) if judges_for else panel:
            counts[judge.label] = counts.get(judge.label, 0) + per_model
            configs[judge.label] = judge
    judge_costs = {
        label: _judge_cost(
            catalog.price_for(configs[label].model, provider=configs[label].provider),
            count,
        )
        for label, count in counts.items()
    }
    judge_total, _ = (
        summarize_costs(list(judge_costs.values())) if judge_costs else (0.0, False)
    )
    known_costs = [*model_costs.values(), *judge_costs.values()]
    total, is_partial = summarize_costs(known_costs) if known_costs else (0.0, False)
    return CostEstimate(
        runs_per_model=len(runs) * repeats,
        model_costs=model_costs,
        judges=list(counts),
        judge_calls=max(counts.values(), default=0),
        judge_call_counts=counts,
        judge_costs=judge_costs,
        judge_cost_usd=judge_total,
        provider_costs=_by_provider(model_costs, judge_costs),
        total_usd=total,
        is_partial=is_partial,
        skipped_judges=skipped,
    )


def estimate_tournament_cost(
    matrix: MatrixConfig,
    cases: Sequence[EvalCase],
    catalog: ModelCatalog,
    *,
    skipped_judges: Mapping[str, str] | None = None,
) -> TournamentEstimate:
    """Estimate both rounds of a tournament run.

    Screening runs every model on the screening cases with the screening
    repeats, each model's outputs judged by its one screening judge. The
    finals run ``assumed_survivors`` on every case with ``[run] repeats`` and
    the whole panel; the worst case keeps every model.
    """
    available = [j for j in matrix.panel if j.label not in (skipped_judges or {})]
    settings = matrix.tournament

    def one_judge(model: MatrixModel) -> list[JudgeConfig]:
        chosen = screening_judge(model, available, catalog)
        return [chosen] if chosen is not None else []

    screening_matrix = matrix.model_copy(
        update={
            "run": matrix.run.model_copy(update={"repeats": settings.screening_repeats})
        }
    )
    survivors = assumed_survivors(matrix.models, settings, catalog)
    return TournamentEstimate(
        screening=estimate_matrix_cost(
            screening_matrix,
            screening_cases(cases, settings),
            catalog,
            skipped_judges=skipped_judges,
            judges_for=one_judge,
        ),
        finals=estimate_matrix_cost(
            matrix.model_copy(update={"models": survivors}),
            cases,
            catalog,
            skipped_judges=skipped_judges,
        ),
        finals_worst_case=estimate_matrix_cost(
            matrix, cases, catalog, skipped_judges=skipped_judges
        ),
        assumed_survivors=[model.label for model in survivors],
    )


def assumed_survivors(
    models: Sequence[MatrixModel], settings: TournamentSettings, catalog: ModelCatalog
) -> list[MatrixModel]:
    """The models a finals estimate assumes survive screening at every stage.

    The best of each provider always survives, and quality tends to follow
    price, so it takes the dearest model of each provider (input plus output
    price), then the next dearest models until ``keep_top`` are kept.
    """
    by_price = sorted(models, key=lambda m: -_list_price(m, catalog))
    kept: list[MatrixModel] = []
    for provider in dict.fromkeys(model.provider for model in models):
        kept.extend(
            [m for m in by_price if m.provider == provider][
                : settings.keep_per_provider
            ]
        )
    for model in by_price:
        if len(kept) >= settings.keep_top:
            break
        if model not in kept:
            kept.append(model)
    return kept


def _list_price(model: MatrixModel, catalog: ModelCatalog) -> float:
    price = catalog.price_for(model.model, provider=model.provider)
    return -math.inf if price is None else price[0] + price[1]


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
