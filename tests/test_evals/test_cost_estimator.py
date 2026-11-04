"""Tests for the matrix cost estimate (REQ-EV-21, design 9.8)."""

import pytest

from evals.harness.cost_estimator import (
    JUDGE_INPUT_TOKENS,
    JUDGE_OUTPUT_TOKENS,
    estimate_matrix_cost,
)
from evals.models.eval_case import EvalCase
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_settings import RunSettings
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import StageKey

HAIKU = "anthropic/claude-haiku-5-5"
JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
PER_MILLION = 1e6


def _case(case_id: str = "alpha", **fields: object) -> EvalCase:
    return EvalCase(id=case_id, persona="persona.md", jd="jd.md", **fields)  # type: ignore[arg-type]


def _matrix(
    stages: list[StageKey],
    *,
    models: list[MatrixModel] | None = None,
    repeats: int = 1,
) -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(stages=stages, repeats=repeats),
        judge=JUDGE,
        reference=JUDGE,
        models=models or [MatrixModel(provider="anthropic", model="claude-haiku-5-5")],
    )


def _priced(
    provider: str, model: str, cost_in: float, cost_out: float
) -> ModelCapability:
    return ModelCapability(
        provider=provider,
        match=model,
        input_price_per_mtok=cost_in,
        output_price_per_mtok=cost_out,
    )


def _unit_model(name: str) -> MatrixModel:
    return MatrixModel(provider="p", model=name)


JUDGED_CATALOG = ModelCatalog(
    [_priced("p", "m", 0.0, 0.0), _priced("anthropic", "claude-opus-5-5", 5.0, 25.0)]
)


def test_a_judge_call_is_estimated_at_the_documented_size() -> None:
    assert (JUDGE_INPUT_TOKENS, JUDGE_OUTPUT_TOKENS) == (6000, 1500)


class TestEvaluatedModelCost:
    def test_two_cases_on_analyze_cost_the_documented_amount(self) -> None:
        """REQ-EV-21: 2 x (4000 x 0.10 + 2000 x 0.50) / 1e6 = $0.0028."""
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]),
            [_case("one"), _case("two")],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == pytest.approx(0.0028)

    def test_analyze_has_no_judge_cost(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert (estimate.judge_calls, estimate.judge_cost_usd) == (0, 0.0)

    def test_total_is_the_evaluated_cost_when_there_are_no_judge_calls(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert estimate.total_usd == pytest.approx(0.0014)

    def test_repeats_multiply_the_cost(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE], repeats=3),
            [_case()],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == pytest.approx(0.0042)

    def test_every_stage_uses_its_own_token_estimate(self) -> None:
        stages = [StageKey.ANALYZE, StageKey.SELECT]
        tokens_in = sum(STAGE_REQUIREMENTS[s].est_input_tokens for s in stages)
        tokens_out = sum(STAGE_REQUIREMENTS[s].est_output_tokens for s in stages)
        estimate = estimate_matrix_cost(
            _matrix(stages, models=[_unit_model("m")]),
            [_case()],
            ModelCatalog([_priced("p", "m", 1.0, 2.0)]),
        )
        assert estimate.model_costs["p/m"] == pytest.approx(
            (tokens_in * 1.0 + tokens_out * 2.0) / PER_MILLION
        )

    def test_a_case_restricted_to_review_skips_other_stages(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]),
            [_case(stages=[StageKey.REVIEW])],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == 0.0

    def test_each_model_is_estimated_separately(self) -> None:
        catalog = ModelCatalog(
            [_priced("p", "cheap", 1.0, 1.0), _priced("p", "dear", 10.0, 10.0)]
        )
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.ANALYZE], models=[_unit_model("cheap"), _unit_model("dear")]
            ),
            [_case()],
            catalog,
        )
        costs = estimate.model_costs
        assert costs["p/dear"] == pytest.approx(10 * costs["p/cheap"])  # type: ignore[operator]


class TestUnknownPrices:
    def test_an_unpriced_model_costs_none(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog([])
        )
        assert estimate.model_costs[HAIKU] is None

    def test_no_known_price_leaves_the_total_unknown(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog([])
        )
        assert estimate.total_usd is None

    def test_a_missing_price_makes_the_total_partial(self) -> None:
        catalog = ModelCatalog(
            [
                _priced("p", "m", 1.0, 1.0),
                _priced("anthropic", "claude-opus-5-5", 5.0, 25.0),
            ]
        )
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.ANALYZE], models=[_unit_model("m"), _unit_model("unpriced")]
            ),
            [_case()],
            catalog,
        )
        assert estimate.is_partial is True

    def test_a_fully_priced_estimate_is_not_partial(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert estimate.is_partial is False


class TestJudgeCost:
    def _estimate(self, stage: StageKey, cases: list[EvalCase], **options: int):  # type: ignore[no-untyped-def]
        return estimate_matrix_cost(
            _matrix([stage], models=[_unit_model("m")], **options),
            cases,
            JUDGED_CATALOG,
        )

    def test_select_makes_one_judge_call_per_run(self) -> None:
        assert self._estimate(StageKey.SELECT, [_case()]).judge_calls == 1

    def test_tailor_makes_two_judge_calls_per_run(self) -> None:
        assert self._estimate(StageKey.TAILOR, [_case()]).judge_calls == 2

    def test_judge_calls_are_priced_at_the_judge_model(self) -> None:
        per_call = (JUDGE_INPUT_TOKENS * 5.0 + JUDGE_OUTPUT_TOKENS * 25.0) / PER_MILLION
        estimate = self._estimate(StageKey.TAILOR, [_case()])
        assert estimate.judge_cost_usd == pytest.approx(2 * per_call)

    def test_review_judges_only_cases_with_seeded_defects(self) -> None:
        probe = _case("probe", review_probe_defects=["a defect"])
        assert self._estimate(StageKey.REVIEW, [_case(), probe]).judge_calls == 1

    def test_judge_calls_scale_with_models_and_repeats(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.SELECT],
                models=[_unit_model("m"), _unit_model("n")],
                repeats=2,
            ),
            [_case()],
            JUDGED_CATALOG,
        )
        assert estimate.judge_calls == 4

    def test_an_unpriced_judge_leaves_its_cost_unknown(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.SELECT], models=[_unit_model("m")]),
            [_case()],
            ModelCatalog([_priced("p", "m", 0.0, 0.0)]),
        )
        assert estimate.judge_cost_usd is None

    def test_the_judge_is_named_in_the_estimate(self) -> None:
        assert self._estimate(StageKey.SELECT, [_case()]).judge == (
            "anthropic/claude-opus-5-5"
        )


class TestJudgeSkipped:
    """A judge without credentials makes no calls, so it costs nothing."""

    REASON = "no API key for provider 'anthropic' (set ANTHROPIC_API_KEY)"

    def _estimate(self, stages: list[StageKey], reason: str | None) -> object:
        return estimate_matrix_cost(
            _matrix(stages),
            [_case()],
            ModelCatalog.builtin(),
            judge_skipped=reason,
        )

    def test_a_skipped_judge_makes_no_calls_and_costs_nothing(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], self.REASON)
        assert (estimate.judge_calls, estimate.judge_cost_usd) == (0, 0.0)  # type: ignore[attr-defined]

    def test_the_reason_is_reported(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], self.REASON)
        assert estimate.judge_skipped == self.REASON  # type: ignore[attr-defined]

    def test_the_total_leaves_the_judge_out(self) -> None:
        skipped = self._estimate([StageKey.TAILOR], self.REASON)
        priced = self._estimate([StageKey.TAILOR], None)
        assert skipped.total_usd < priced.total_usd  # type: ignore[attr-defined]
        assert skipped.total_usd == skipped.model_costs[HAIKU]  # type: ignore[attr-defined]

    def test_a_stage_without_judge_calls_has_nothing_to_skip(self) -> None:
        estimate = self._estimate([StageKey.ANALYZE], self.REASON)
        assert estimate.judge_skipped is None  # type: ignore[attr-defined]

    def test_an_available_judge_is_priced_as_before(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], None)
        assert estimate.judge_calls == 2  # type: ignore[attr-defined]
        assert estimate.judge_skipped is None  # type: ignore[attr-defined]
