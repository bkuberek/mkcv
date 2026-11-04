"""Tests for aggregating records into stage summaries (REQ-EV-16, design 9.9)."""

import pytest

from evals.models.eval_record import EvalRecord
from evals.models.grade import Grade
from evals.models.recommendation_settings import RecommendationSettings
from evals.models.stage_summary import StageSummary
from evals.report.aggregator import aggregate
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import grade, panel_grade, record


def _one(records: list[EvalRecord]) -> StageSummary:
    [summary] = aggregate(records)
    return summary


def _tailor_grades(
    *, schema: float = 1.0, extraction: float = 1.0, judge: float = 1.0
) -> list[Grade]:
    return [
        grade("schema", schema),
        grade("faithfulness_extraction", extraction),
        grade("faithfulness_judge", judge),
        grade("tailoring_judge", 0.8),
    ]


class TestCounts:
    """REQ-EV-16."""

    def _requirement_records(self) -> list[EvalRecord]:
        return [
            *(record(latency=float(i), repeat=i) for i in range(1, 7)),
            record(status="error", repeat=7),
        ]

    def test_six_ok_and_one_error_record_make_seven_runs(self) -> None:
        assert _one(self._requirement_records()).n == 7

    def test_the_ok_rate_is_the_share_of_ok_records(self) -> None:
        assert _one(self._requirement_records()).ok_rate == pytest.approx(6 / 7)

    def test_the_median_latency_uses_ok_records_only(self) -> None:
        assert _one(self._requirement_records()).latency_p50_s == 3.5

    def test_seven_runs_is_not_a_low_sample(self) -> None:
        assert _one(self._requirement_records()).low_sample is False

    def test_skipped_records_are_not_counted(self) -> None:
        records = [record(), record(status="skipped", repeat=1)]
        assert _one(records).n == 1

    def test_a_group_with_only_skipped_records_has_no_summary(self) -> None:
        assert aggregate([record(status="skipped")]) == []

    @pytest.mark.parametrize(("runs", "low"), [(5, True), (6, False)])
    def test_fewer_than_six_runs_is_a_low_sample(self, runs: int, low: bool) -> None:
        records = [record(repeat=i) for i in range(runs)]
        assert _one(records).low_sample is low

    def test_no_records_give_no_summaries(self) -> None:
        assert aggregate([]) == []

    def test_all_errors_give_a_zero_ok_rate_and_no_timings(self) -> None:
        summary = _one([record(status="error"), record(status="error", repeat=1)])
        assert (summary.ok_rate, summary.latency_p50_s, summary.cost_mean_usd) == (
            0.0,
            None,
            None,
        )


class TestTimingsCostAndTokens:
    def test_the_90th_percentile_interpolates_between_runs(self) -> None:
        records = [record(latency=float(i), repeat=i) for i in range(1, 7)]
        assert _one(records).latency_p90_s == pytest.approx(5.5)

    def test_one_run_has_the_same_p50_and_p90(self) -> None:
        summary = _one([record(latency=4.0)])
        assert (summary.latency_p50_s, summary.latency_p90_s) == (4.0, 4.0)

    def test_the_mean_cost_is_over_ok_records(self) -> None:
        records = [
            record(cost=0.10),
            record(cost=0.30, repeat=1),
            record(status="error", repeat=2),
        ]
        assert _one(records).cost_mean_usd == pytest.approx(0.20)

    def test_token_medians_are_over_ok_records(self) -> None:
        records = [
            record(input_tokens=1000, output_tokens=100, repeat=0),
            record(input_tokens=3000, output_tokens=300, repeat=1),
            record(input_tokens=9000, output_tokens=900, repeat=2),
        ]
        summary = _one(records)
        assert (summary.median_input_tokens, summary.median_output_tokens) == (
            3000,
            300,
        )


class TestGrouping:
    def test_each_stage_provider_and_model_gets_its_own_summary(self) -> None:
        records = [
            record(stage=StageKey.TAILOR, provider="openai", model="a"),
            record(stage=StageKey.TAILOR, provider="openai", model="b"),
            record(stage=StageKey.TAILOR, provider="google", model="a"),
            record(stage=StageKey.ANALYZE, provider="openai", model="a"),
        ]
        assert len(aggregate(records)) == 4

    def test_summaries_follow_pipeline_order_then_provider_then_model(self) -> None:
        records = [
            record(stage=StageKey.REVIEW, provider="a", model="z"),
            record(stage=StageKey.ANALYZE, provider="b", model="y"),
            record(stage=StageKey.ANALYZE, provider="a", model="z"),
            record(stage=StageKey.ANALYZE, provider="a", model="x"),
        ]
        order = [(s.stage.value, s.provider, s.model) for s in aggregate(records)]
        assert order == [
            ("analyze", "a", "x"),
            ("analyze", "a", "z"),
            ("analyze", "b", "y"),
            ("review", "a", "z"),
        ]

    def test_cases_and_repeats_of_one_model_are_pooled(self) -> None:
        records = [
            record(case="a", repeat=0),
            record(case="a", repeat=1),
            record(case="b", repeat=0),
        ]
        assert _one(records).n == 3


class TestMeans:
    def test_each_grade_is_averaged_over_the_records_that_have_it(self) -> None:
        records = [
            record(grades=[grade("schema", 1.0), grade("tailoring_judge", 0.6)]),
            record(
                grades=[grade("schema", 0.0), grade("tailoring_judge", 1.0)], repeat=1
            ),
        ]
        assert _one(records).mean == {"schema": 0.5, "tailoring_judge": 0.8}

    def test_a_grade_without_a_score_is_left_out_of_its_mean(self) -> None:
        records = [
            record(grades=[grade("tailoring_judge", None, error="down")]),
            record(grades=[grade("tailoring_judge", 0.6)], repeat=1),
        ]
        assert _one(records).mean == {"tailoring_judge": 0.6}

    def test_a_grade_that_never_had_a_score_has_no_mean(self) -> None:
        records = [record(grades=[grade("tailoring_judge", None)])]
        assert "tailoring_judge" not in _one(records).mean

    def test_error_records_have_no_grades_to_average(self) -> None:
        records = [
            record(grades=[grade("schema", 1.0)]),
            record(status="error", repeat=1),
        ]
        assert _one(records).mean == {"schema": 1.0}


class TestPrimaryScore:
    @pytest.mark.parametrize(
        ("stage", "metric"),
        [
            (StageKey.ANALYZE, "jd_keyword_recall"),
            (StageKey.SELECT, "selection_judge"),
            (StageKey.TAILOR, "tailoring_judge"),
            (StageKey.STRUCTURE, "ats_rules"),
            (StageKey.REVIEW, "review_defect_recall"),
        ],
    )
    def test_it_is_the_mean_of_the_stages_primary_metric(
        self, stage: StageKey, metric: str
    ) -> None:
        records = [
            record(stage=stage, grades=[grade("schema", 1.0), grade(metric, 0.7)])
        ]
        assert _one(records).primary_score == pytest.approx(0.7)

    def test_it_is_none_when_the_metric_was_not_graded(self) -> None:
        records = [record(grades=[grade("schema", 1.0)])]
        assert _one(records).primary_score is None

    def test_another_stages_metric_does_not_count(self) -> None:
        records = [record(stage=StageKey.TAILOR, grades=[grade("ats_rules", 1.0)])]
        assert _one(records).primary_score is None


class TestEligibility:
    """The hard gates: ok rate, schema, and faithfulness in every run."""

    def test_a_clean_run_is_eligible(self) -> None:
        records = [record(grades=_tailor_grades())]
        assert _one(records).eligible is True

    def test_an_ok_rate_below_point_95_is_not_eligible(self) -> None:
        records = [record(repeat=i, grades=_tailor_grades()) for i in range(18)]
        records.append(record(status="error", repeat=18))
        records.append(record(status="error", repeat=19))
        assert _one(records).ok_rate == pytest.approx(0.9)
        assert _one(records).eligible is False

    def test_an_ok_rate_of_exactly_point_95_is_eligible(self) -> None:
        records = [record(repeat=i, grades=_tailor_grades()) for i in range(19)]
        records.append(record(status="error", repeat=19))
        assert _one(records).ok_rate == 0.95
        assert _one(records).eligible is True

    def test_a_schema_mean_of_exactly_point_95_is_eligible(self) -> None:
        records = [record(repeat=i, grades=_tailor_grades()) for i in range(19)]
        records.append(record(repeat=19, grades=_tailor_grades(schema=0.0)))
        summary = _one(records)
        assert summary.mean["schema"] == pytest.approx(0.95)
        assert summary.eligible is True

    def test_a_schema_mean_below_point_95_is_not_eligible(self) -> None:
        records = [record(grades=_tailor_grades(schema=0.9))]
        assert _one(records).eligible is False

    def test_a_deterministic_faithfulness_mean_below_point_95_is_not_eligible(
        self,
    ) -> None:
        records = [record(grades=_tailor_grades(extraction=0.94))]
        assert _one(records).eligible is False

    def test_a_judge_faithfulness_mean_below_point_90_is_not_eligible(self) -> None:
        records = [record(grades=_tailor_grades(judge=0.89))]
        assert _one(records).eligible is False

    def test_a_judge_faithfulness_mean_of_exactly_point_90_is_eligible(self) -> None:
        records = [record(grades=_tailor_grades(judge=0.9))]
        assert _one(records).eligible is True

    def test_the_gate_failures_name_each_missed_gate(self) -> None:
        records = [record(grades=_tailor_grades(schema=0.9, judge=0.5))]
        assert _one(records).gate_failures == [
            "schema below 0.95",
            "faithfulness_judge below 0.9",
        ]

    def test_an_eligible_model_has_no_gate_failures(self) -> None:
        assert _one([record(grades=_tailor_grades())]).gate_failures == []

    def test_a_stage_without_faithfulness_grades_needs_only_ok_rate_and_schema(
        self,
    ) -> None:
        records = [
            record(
                stage=StageKey.ANALYZE,
                grades=[grade("schema", 1.0), grade("jd_keyword_recall", 0.5)],
            )
        ]
        assert _one(records).eligible is True

    def test_a_group_with_no_ok_record_is_not_eligible(self) -> None:
        assert _one([record(status="error")]).eligible is False

    def test_a_missing_schema_grade_is_not_eligible(self) -> None:
        assert _one([record(grades=[])]).eligible is False


class TestFabricationGate:
    """A model that fabricates in any run is not eligible, whatever its mean."""

    def _runs(
        self, *passes: bool, name: str = "faithfulness_extraction"
    ) -> list[EvalRecord]:
        return [
            record(
                repeat=i,
                grades=[
                    grade("schema", 1.0),
                    grade(name, 1.0 if passed else 0.98, passed=passed),
                ],
            )
            for i, passed in enumerate(passes)
        ]

    def test_one_fabricating_run_in_twenty_is_not_eligible(self) -> None:
        summary = _one(self._runs(*[True] * 19, False))
        assert summary.mean["faithfulness_extraction"] > 0.95
        assert summary.eligible is False

    def test_the_fabrication_rate_is_the_share_of_failing_runs(self) -> None:
        summary = _one(self._runs(True, True, True, False))
        assert summary.fabrication_rate == {"faithfulness_extraction": 0.25}

    def test_the_gate_failure_gives_the_rate(self) -> None:
        summary = _one(self._runs(True, False))
        assert summary.gate_failures == [
            "faithfulness_extraction: fabricated in 50% of runs (max 0%)"
        ]

    def test_the_judge_faithfulness_grade_is_gated_the_same_way(self) -> None:
        summary = _one(self._runs(True, False, name="faithfulness_judge"))
        assert summary.eligible is False

    def test_runs_that_never_fabricate_pass_the_gate(self) -> None:
        assert _one(self._runs(True, True)).eligible is True

    def test_a_higher_limit_tolerates_some_fabrication(self) -> None:
        settings = RecommendationSettings(max_fabrication_rate=0.25)
        [summary] = aggregate(self._runs(True, True, True, False), settings)
        assert summary.eligible is True

    def test_grades_that_say_nothing_about_passing_are_not_counted(self) -> None:
        records = [
            record(grades=[grade("schema", 1.0), grade("faithfulness_extraction", 1.0)])
        ]
        assert _one(records).fabrication_rate == {}

    def test_other_grades_have_no_fabrication_rate(self) -> None:
        records = [
            record(grades=[grade("schema", 1.0), grade("ats_rules", 0.5, passed=False)])
        ]
        assert _one(records).fabrication_rate == {}


class TestSelfJudged:
    """REQ-EV-15, summary side, for single-judge records."""

    def test_a_grade_only_its_own_provider_judged_marks_the_summary(self) -> None:
        records = [
            record(grades=[grade("tailoring_judge", 0.8, self_judged=True)]),
            record(grades=[grade("tailoring_judge", 0.6, self_judged=True)], repeat=1),
        ]
        assert _one(records).self_judged is True

    def test_its_quality_then_falls_back_to_the_self_judged_score(self) -> None:
        records = [record(grades=[grade("tailoring_judge", 0.8, self_judged=True)])]
        assert _one(records).primary_score == pytest.approx(0.8)

    def test_one_independently_judged_run_is_enough(self) -> None:
        records = [
            record(grades=[grade("tailoring_judge", 0.9, self_judged=True)]),
            record(grades=[grade("tailoring_judge", 0.6, self_judged=False)], repeat=1),
        ]
        summary = _one(records)
        assert summary.self_judged is False
        assert summary.primary_score == pytest.approx(0.6)

    def test_grades_judged_by_another_provider_do_not(self) -> None:
        records = [record(grades=[grade("tailoring_judge", 0.8, self_judged=False)])]
        assert _one(records).self_judged is False

    def test_grades_without_a_judge_do_not(self) -> None:
        assert _one([record(grades=[grade("schema", 1.0)])]).self_judged is False


class TestJudgePanel:
    """Panel grades: self-preference removed, spread and agreement measured."""

    def _tailor(self, **scores: float | None) -> list[EvalRecord]:
        return [
            record(
                provider="openai",
                grades=[grade("schema", 1.0), panel_grade("tailoring_judge", scores)],
            )
        ]

    def test_quality_leaves_out_the_models_own_providers_judge(self) -> None:
        summary = _one(self._tailor(anthropic=0.6, openai=1.0, google=0.8))
        assert summary.primary_score == pytest.approx(0.7)

    def test_the_all_judge_mean_is_still_reported(self) -> None:
        summary = _one(self._tailor(anthropic=0.6, openai=1.0, google=0.8))
        assert summary.mean["tailoring_judge"] == pytest.approx(0.8)
        assert summary.independent_mean["tailoring_judge"] == pytest.approx(0.7)

    def test_a_row_is_self_judged_only_when_its_own_judge_was_alone(self) -> None:
        assert _one(self._tailor(openai=1.0, google=0.8)).self_judged is False
        assert _one(self._tailor(openai=1.0, google=None)).self_judged is True

    def test_a_self_judged_row_falls_back_to_its_own_judges_score(self) -> None:
        summary = _one(self._tailor(openai=1.0, google=None))
        assert summary.primary_score == pytest.approx(1.0)

    def test_each_judges_mean_primary_score_is_kept(self) -> None:
        summary = _one(self._tailor(anthropic=0.6, openai=1.0, google=0.8))
        assert summary.primary_by_judge == {
            "anthropic/judge": pytest.approx(0.6),
            "openai/judge": pytest.approx(1.0),
            "google/judge": pytest.approx(0.8),
        }

    def test_the_spread_is_averaged_over_judged_outputs(self) -> None:
        records = [
            *self._tailor(anthropic=0.6, google=0.8),
            *(
                r.model_copy(update={"repeat": 1})
                for r in self._tailor(anthropic=0.8, google=0.8)
            ),
        ]
        summary = _one(records)
        assert summary.judge_spread == pytest.approx(0.1)
        assert summary.judged_outputs == 2

    def test_agreement_is_the_share_of_outputs_within_a_tenth(self) -> None:
        records = [
            *self._tailor(anthropic=0.6, google=0.8),
            *(
                r.model_copy(update={"repeat": 1})
                for r in self._tailor(anthropic=0.75, google=0.8)
            ),
        ]
        assert _one(records).judge_agreement == pytest.approx(0.5)

    def test_one_judge_gives_no_spread_or_agreement(self) -> None:
        summary = _one(self._tailor(anthropic=0.6))
        assert (summary.judge_spread, summary.judge_agreement) == (None, None)
        assert summary.judged_outputs == 0

    def test_the_faithfulness_floor_uses_the_independent_judges(self) -> None:
        records = [
            record(
                provider="openai",
                grades=[
                    grade("schema", 1.0),
                    panel_grade("faithfulness_judge", {"openai": 1.0, "google": 0.8}),
                ],
            )
        ]
        assert "faithfulness_judge below 0.9" in _one(records).gate_failures


class TestSpreadAcrossRuns:
    """Repeats and cases give each model a mean, a deviation, and case means."""

    def _runs(self, *scored: tuple[str, int, float]) -> list[EvalRecord]:
        return [
            record(
                case=case,
                repeat=repeat,
                grades=[grade("schema", 1.0), grade("tailoring_judge", score)],
            )
            for case, repeat, score in scored
        ]

    def test_the_standard_deviation_is_over_every_scored_run(self) -> None:
        summary = _one(self._runs(("a", 0, 0.6), ("a", 1, 0.8), ("b", 0, 1.0)))
        assert summary.primary_std == pytest.approx(0.2)
        assert summary.primary_n == 3

    def test_one_run_has_no_standard_deviation(self) -> None:
        summary = _one(self._runs(("a", 0, 0.6)))
        assert (summary.primary_std, summary.primary_n) == (None, 1)

    def test_case_scores_average_the_repeats_of_each_case(self) -> None:
        summary = _one(self._runs(("a", 0, 0.6), ("a", 1, 0.8), ("b", 0, 1.0)))
        assert summary.case_scores == {
            "a": pytest.approx(0.7),
            "b": pytest.approx(1.0),
        }

    def test_judged_runs_use_the_independent_score(self) -> None:
        records = [
            record(
                provider="openai",
                case="a",
                repeat=repeat,
                grades=[
                    grade("schema", 1.0),
                    panel_grade("tailoring_judge", {"openai": 1.0, "google": score}),
                ],
            )
            for repeat, score in enumerate((0.6, 0.8))
        ]
        summary = _one(records)
        assert summary.case_scores == {"a": pytest.approx(0.7)}
        assert summary.primary_std == pytest.approx(0.1414, abs=1e-4)
