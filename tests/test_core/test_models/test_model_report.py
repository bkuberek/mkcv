"""Tests for the model-advice models (design section 3.6)."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.model_report import ModelReport, summarize_costs
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_advice import StageAdvice
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_key import StageKey


def _advice(stage: StageKey, cost: float | None) -> StageAdvice:
    return StageAdvice(
        assignment=StageAssignment(
            stage=stage,
            provider="anthropic",
            provider_kind=ProviderKind.ANTHROPIC,
            model="claude-opus-5-5",
            temperature=0.3,
            source="profile",
        ),
        recommended_model="claude-opus-5-5",
        recommended_provider="anthropic",
        tier=ModelTier.FRONTIER,
        min_tier=ModelTier.STRONG,
        known=True,
        estimated_cost_usd=cost,
        warnings=[],
    )


def _report(*advice: StageAdvice) -> ModelReport:
    return ModelReport(
        profile_name="anthropic",
        profile_evidence="provisional",
        profile_source="default",
        preset_name="standard",
        stages=list(advice),
        warnings=[],
        estimated_total_usd=None,
        estimate_is_partial=False,
    )


class TestSummarizeCosts:
    def test_known_costs_are_summed(self) -> None:
        assert summarize_costs([0.25, 0.5]) == (0.75, False)

    def test_the_sum_is_not_rounded(self) -> None:
        total, _ = summarize_costs([0.1, 0.2])
        assert total == 0.1 + 0.2

    def test_an_unknown_cost_among_known_ones_makes_the_sum_partial(self) -> None:
        assert summarize_costs([0.25, None]) == (0.25, True)

    def test_only_unknown_costs_give_no_total_and_no_partial_flag(self) -> None:
        assert summarize_costs([None, None]) == (None, False)

    def test_no_costs_give_no_total(self) -> None:
        assert summarize_costs([]) == (None, False)

    def test_a_free_stage_counts_as_known(self) -> None:
        assert summarize_costs([0.0, 0.0]) == (0.0, False)


class TestResumeRunEstimate:
    def test_only_the_five_pipeline_stages_count(self) -> None:
        report = _report(
            _advice(StageKey.ANALYZE, 1.0),
            _advice(StageKey.COVER_LETTER_GENERATE, 10.0),
            _advice(StageKey.KB, 100.0),
        )
        assert report.resume_run_estimate() == (1.0, False)

    def test_an_unpriced_pipeline_stage_makes_it_partial(self) -> None:
        report = _report(_advice(StageKey.ANALYZE, 1.0), _advice(StageKey.SELECT, None))
        assert report.resume_run_estimate() == (1.0, True)

    def test_a_report_without_pipeline_stages_has_no_estimate(self) -> None:
        report = _report(_advice(StageKey.KB, 100.0))
        assert report.resume_run_estimate() == (None, False)


class TestSerialisation:
    def test_a_report_round_trips_through_json(self) -> None:
        report = _report(_advice(StageKey.ANALYZE, 0.5)).model_copy(
            update={
                "warnings": [
                    ModelWarning(
                        kind=ModelWarningKind.MISSING_API_KEY,
                        stage=None,
                        provider="openai",
                        model=None,
                        message="openai: no API key found",
                    )
                ]
            }
        )
        assert ModelReport.model_validate_json(report.model_dump_json()) == report

    def test_stage_keys_serialise_as_their_config_names(self) -> None:
        report = _report(_advice(StageKey.COVER_LETTER_REVIEW, 0.5))
        assert '"cover_letter.review"' in report.model_dump_json()

    def test_reports_are_immutable(self) -> None:
        report = _report()
        with pytest.raises(ValidationError):
            report.preset_name = "concise"  # type: ignore[misc]
