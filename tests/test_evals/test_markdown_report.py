"""Tests for rendering the eval report (REQ-EV-18, design 9.9)."""

import re

from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.recommendation_settings import RecommendationSettings
from evals.report.markdown_report import render_markdown
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import (
    RUN_ID,
    manifest,
    recommendation,
    summary,
)

TABLE_HEADER = (
    "| Provider | Model | n | OK | Schema | Fabricated (det) | Fabricated (judge) | "
    "Faithfulness (judge) | Quality | All judges | Judge spread | Cost/run | "
    "p50 latency | Eligible | Notes |"
)
PANEL = [
    JudgeConfig(provider="anthropic", model="claude-opus-5-5"),
    JudgeConfig(provider="openai", model="gpt-6-astra"),
    JudgeConfig(provider="google", model="gemini-4-argon"),
]


def _headings(report: str) -> list[str]:
    return re.findall(r"^## .*$", report, flags=re.MULTILINE)


def _section(report: str, heading: str) -> str:
    start = report.index(f"## {heading}")
    following = report.find("\n## ", start + 1)
    return report[start:] if following == -1 else report[start:following]


def _render(**overrides: object) -> str:
    summaries = overrides.pop("summaries", [summary()])
    recs = overrides.pop("recommendations", [recommendation()])
    return render_markdown(
        overrides.pop("manifest", manifest()),  # type: ignore[arg-type]
        summaries,  # type: ignore[arg-type]
        recs,  # type: ignore[arg-type]
    )


class TestStructure:
    """REQ-EV-18."""

    def test_it_starts_with_the_run_title(self) -> None:
        assert _render().startswith(f"# mkcv eval report: {RUN_ID}\n")

    def test_the_sections_come_in_the_documented_order(self) -> None:
        assert _headings(_render()) == [
            "## Run",
            "## Caveats",
            "## Judge panel",
            "## Cost",
            "## Stage: tailor",
            "## Recommendations",
            "## Suggested profile changes",
            "## Token estimates",
        ]

    def test_there_is_one_stage_section_per_stage_present_in_pipeline_order(
        self,
    ) -> None:
        report = _render(
            summaries=[
                summary(stage=StageKey.REVIEW),
                summary(stage=StageKey.ANALYZE),
                summary(stage=StageKey.TAILOR),
            ]
        )
        stages = [h for h in _headings(report) if h.startswith("## Stage: ")]
        assert stages == ["## Stage: analyze", "## Stage: tailor", "## Stage: review"]

    def test_a_run_without_results_still_has_every_fixed_section(self) -> None:
        report = _render(summaries=[], recommendations=[])
        assert _headings(report) == [
            "## Run",
            "## Caveats",
            "## Judge panel",
            "## Cost",
            "## Recommendations",
            "## Suggested profile changes",
            "## Token estimates",
        ]

    def test_a_run_without_results_says_there_are_no_rows(self) -> None:
        assert "No results" in _render(summaries=[], recommendations=[])


class TestRunSection:
    def test_it_lists_the_run_metadata(self) -> None:
        section = _section(_render(), "Run")
        for expected in (
            RUN_ID,
            "1.3.0",
            "abc1234",
            "anthropic/claude-opus-5-5",
            "2026-11-04",
        ):
            assert expected in section

    def test_it_counts_the_cases(self) -> None:
        assert "case-a, case-b" in _section(_render(), "Run")

    def test_it_lists_the_judges_and_those_that_ran(self) -> None:
        report = _render(
            manifest=manifest(
                judges=PANEL, skipped_judges={"openai/gpt-6-astra": "no key"}
            )
        )
        section = _section(report, "Run")
        assert (
            "| Judges | anthropic/claude-opus-5-5, openai/gpt-6-astra, "
            "google/gemini-4-argon |" in section
        )
        assert (
            "| Judges that ran | anthropic/claude-opus-5-5, google/gemini-4-argon |"
            in section
        )


class TestCaveats:
    def test_a_clean_run_has_no_caveat_beyond_the_provisional_note(self) -> None:
        section = _section(_render(), "Caveats")
        assert "provisional" in section
        assert "self-judged" not in section
        assert "low sample" not in section

    def test_self_judged_rows_are_called_out(self) -> None:
        report = _render(summaries=[summary(model="gpt-6.1-sol", self_judged=True)])
        section = _section(report, "Caveats")
        assert "self-judged" in section
        assert "openai/gpt-6.1-sol" in section

    def test_low_sample_rows_are_called_out(self) -> None:
        report = _render(summaries=[summary(model="tiny", n=3)])
        section = _section(report, "Caveats")
        assert "low sample" in section
        assert "openai/tiny" in section

    def test_skipped_models_are_listed_with_their_reason(self) -> None:
        skipped = ["google/gemini-4-argon: no API key for provider 'google'"]
        section = _section(
            _render(manifest=manifest(skipped_models=skipped)), "Caveats"
        )
        assert "google/gemini-4-argon: no API key for provider 'google'" in section

    def test_a_judge_that_did_not_run_is_called_out(self) -> None:
        reason = "no API key for provider 'openai' (set OPENAI_API_KEY)"
        report = _render(
            manifest=manifest(
                judges=PANEL, skipped_judges={"openai/gpt-6-astra": reason}
            )
        )
        section = _section(report, "Caveats")
        assert f"openai/gpt-6-astra: {reason}" in section

    def test_a_run_where_no_judge_ran_says_judged_scores_are_missing(self) -> None:
        report = _render(
            manifest=manifest(skipped_judges={"anthropic/claude-opus-5-5": "no key"})
        )
        assert "No judge ran" in _section(report, "Caveats")

    def test_self_judged_rows_say_only_their_own_judge_scored_them(self) -> None:
        report = _render(summaries=[summary(model="gpt-6.1-sol", self_judged=True)])
        assert "only a judge from" in _section(report, "Caveats")

    def test_one_failed_record_reads_in_the_singular(self) -> None:
        report = _render(summaries=[summary(n=10, ok_rate=0.9)])
        assert "1 record failed" in _section(report, "Caveats")

    def test_failed_records_are_counted(self) -> None:
        report = _render(summaries=[summary(n=10, ok_rate=0.7)])
        assert "3 records failed" in _section(report, "Caveats")


class TestJudgePanelSection:
    def _panel_summary(self) -> object:
        return summary(model="gpt-x").model_copy(
            update={
                "primary_by_judge": {
                    "anthropic/claude-opus-5-5": 0.9,
                    "google/gemini-4-argon": 0.7,
                },
                "judge_spread": 0.2,
                "judge_agreement": 0.5,
                "judged_outputs": 4,
            }
        )

    def test_it_explains_how_the_panel_scores(self) -> None:
        section = _section(_render(manifest=manifest(judges=PANEL)), "Judge panel")
        assert "mean" in section
        assert "own provider" in section

    def test_it_reports_how_often_the_judges_agree(self) -> None:
        report = _render(
            manifest=manifest(judges=PANEL), summaries=[self._panel_summary()]
        )
        section = _section(report, "Judge panel")
        assert "within 0.1 of each other on 50% of 4 judged outputs" in section
        assert "mean spread 0.20" in section

    def test_it_shows_the_mean_primary_score_each_judge_gave(self) -> None:
        report = _render(
            manifest=manifest(judges=PANEL), summaries=[self._panel_summary()]
        )
        section = _section(report, "Judge panel")
        assert (
            "| Stage | anthropic/claude-opus-5-5 | openai/gpt-6-astra | "
            "google/gemini-4-argon |" in section
        )
        assert "| tailor | 0.90 | - | 0.70 |" in section

    def test_with_a_single_judge_there_is_no_agreement_to_report(self) -> None:
        section = _section(_render(), "Judge panel")
        assert "One judge" in section


class TestCost:
    def test_it_totals_each_models_cost_across_stages(self) -> None:
        report = _render(
            summaries=[
                summary(stage=StageKey.ANALYZE, n=10, cost=0.05),
                summary(stage=StageKey.TAILOR, n=10, cost=0.10),
            ]
        )
        assert "$1.5000" in _section(report, "Cost")

    def test_failed_runs_do_not_add_cost(self) -> None:
        report = _render(summaries=[summary(n=10, ok_rate=0.5, cost=0.20)])
        assert "$1.0000" in _section(report, "Cost")

    def test_each_model_has_its_own_row(self) -> None:
        report = _render(summaries=[summary(model="a"), summary(model="b")])
        section = _section(report, "Cost")
        assert "openai" in section
        assert "| a |" in section
        assert "| b |" in section

    def test_it_notes_that_judge_calls_are_not_included(self) -> None:
        assert "judge" in _section(_render(), "Cost").lower()


class TestStageTables:
    def test_the_table_has_the_documented_columns(self) -> None:
        assert TABLE_HEADER in _section(_render(), "Stage: tailor")

    def test_a_row_shows_the_models_numbers(self) -> None:
        row_summary = summary(
            model="gpt-x",
            n=8,
            ok_rate=0.875,
            mean={"schema": 1.0, "faithfulness_judge": 0.92},
            primary_score=0.85,
            cost=0.0512,
            p50=3.5,
            eligible=True,
        ).model_copy(
            update={
                "fabrication_rate": {
                    "faithfulness_extraction": 0.0,
                    "faithfulness_judge": 0.125,
                }
            }
        )
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert (
            "| openai | gpt-x | 8 | 88% | 1.00 | 0% | 12% | 0.92 | 0.85 | - | - "
            "| $0.0512 | 3.5s | yes |" in section
        )

    def test_a_judged_row_shows_the_all_judge_mean_and_the_spread(self) -> None:
        row_summary = summary(
            model="gpt-x",
            mean={"schema": 1.0, "tailoring_judge": 0.8},
            primary_score=0.75,
        ).model_copy(update={"judge_spread": 0.15})
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert "| 0.75 | 0.80 | 0.15 |" in section

    def test_values_a_model_does_not_have_show_as_a_dash(self) -> None:
        row_summary = summary(
            model="gpt-x",
            mean={"schema": 1.0},
            primary_score=None,
            cost=None,
            p50=None,
            eligible=False,
        )
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert "| 1.00 | - | - | - | - | - | - | - | - | no |" in section

    def test_notes_flag_self_judging_and_small_samples(self) -> None:
        row_summary = summary(model="gpt-x", n=3, self_judged=True)
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert "self-judged" in section
        assert "low sample" in section

    def test_an_ineligible_row_names_the_gates_it_missed(self) -> None:
        row_summary = summary(
            model="gpt-x",
            ok_rate=0.8,
            eligible=False,
            gate_failures=["ok rate below 0.95", "schema below 0.95"],
        )
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert "ok rate below 0.95, schema below 0.95" in section

    def test_an_eligible_row_has_no_threshold_notes(self) -> None:
        section = _section(_render(summaries=[summary()]), "Stage: tailor")
        assert "below" not in section

    def test_an_ineligible_row_with_no_quality_says_why(self) -> None:
        row_summary = summary(model="gpt-x", primary_score=None)
        section = _section(_render(summaries=[row_summary]), "Stage: tailor")
        assert "no quality score" in section

    def test_every_model_of_the_stage_has_a_row(self) -> None:
        report = _render(summaries=[summary(model="a"), summary(model="b")])
        section = _section(report, "Stage: tailor")
        assert section.count("| openai |") == 2


class TestStageWinners:
    def _stage(self, *recs: object) -> str:
        report = _render(
            summaries=[summary(model="gpt-6.1-sol")], recommendations=list(recs)
        )
        return _section(report, "Stage: tailor")

    def test_it_names_the_primary_metric(self) -> None:
        assert "Primary score: `tailoring_judge`" in self._stage(recommendation())

    def test_it_names_the_best_model_overall(self) -> None:
        stage = self._stage(recommendation(model="gpt-6.1-sol", score=0.9))
        assert "Best overall: **openai/gpt-6.1-sol** (0.90)" in stage

    def test_it_lists_the_best_model_of_each_provider(self) -> None:
        stage = self._stage(
            recommendation(),
            recommendation(scope="openai", model="gpt-6.1-sol", score=0.9),
            recommendation(scope="google", provider="google", model="argon", score=0.8),
        )
        assert "| Provider | Best model | Quality | Why |" in stage
        assert "| openai | gpt-6.1-sol | 0.90 | because |" in stage
        assert "| google | argon | 0.80 | because |" in stage

    def test_a_stage_without_a_winner_says_why(self) -> None:
        stage = self._stage(recommendation(model=None, reason="no eligible model"))
        assert "Best overall: none (no eligible model)" in stage


class TestRecommendations:
    def test_it_states_the_rule(self) -> None:
        section = _section(_render(), "Recommendations")
        assert "highest quality score" in section
        assert "within 0.01" in section

    def test_the_tie_epsilon_comes_from_the_run(self) -> None:
        matrix = manifest().matrix.model_copy(
            update={"recommendation": RecommendationSettings(tie_epsilon=0.03)}
        )
        report = _render(manifest=manifest().model_copy(update={"matrix": matrix}))
        assert "within 0.03" in _section(report, "Recommendations")

    def test_it_has_one_row_per_stage_with_a_column_per_provider(self) -> None:
        recs = [
            recommendation(),
            recommendation(scope="google", provider="google", model="argon", score=0.8),
            recommendation(scope="openai", model="gpt-6.1-sol", score=0.9),
        ]
        section = _section(_render(recommendations=recs), "Recommendations")
        assert "| Stage | Best overall | Quality | google | openai | Notes |" in section
        assert (
            "| tailor | openai/gpt-6.1-sol | 0.90 | argon (0.80) | gpt-6.1-sol (0.90) |"
            in section
        )

    def test_a_missing_winner_shows_as_a_dash(self) -> None:
        recs = [recommendation(model=None, reason="no eligible model")]
        section = _section(_render(recommendations=recs), "Recommendations")
        assert "| tailor | - | - | no eligible model |" in section

    def test_a_tie_decided_by_cost_is_noted(self) -> None:
        recs = [recommendation(decided_by_cost=True, tied_with=["openai/gpt-6-astra"])]
        section = _section(_render(recommendations=recs), "Recommendations")
        assert "cost tie with openai/gpt-6-astra" in section


class TestSuggestedProfileChanges:
    """Built-in provider profiles follow that provider's best model."""

    def _suggested(self, *recs: object) -> str:
        return _section(
            _render(recommendations=list(recs)), "Suggested profile changes"
        )  # type: ignore[arg-type]

    def test_a_different_best_model_is_listed(self) -> None:
        rec = recommendation(
            scope="anthropic", provider="anthropic", model="claude-sonnet-5-5"
        )
        assert (
            "anthropic / tailor: claude-opus-5-5 → claude-sonnet-5-5"
            in self._suggested(rec)
        )

    def test_a_best_model_equal_to_the_profile_is_not_listed(self) -> None:
        rec = recommendation(
            scope="anthropic", provider="anthropic", model="claude-opus-5-5"
        )
        assert "→" not in self._suggested(rec)

    def test_the_overall_winner_does_not_change_provider_profiles(self) -> None:
        rec = recommendation(provider="anthropic", model="claude-sonnet-5-5")
        assert "anthropic / tailor" not in self._suggested(rec)

    def test_economy_profiles_are_left_alone(self) -> None:
        rec = recommendation(scope="openai", model="gpt-6-luna")
        suggested = self._suggested(rec)
        assert "openai / tailor: gpt-6-astra → gpt-6-luna" in suggested
        assert "openai-economy /" not in suggested
        assert "Economy profiles" in suggested

    def test_only_profiles_of_the_same_provider_are_compared(self) -> None:
        rec = recommendation(
            scope="google", provider="google", model="gemini-3.8-flash"
        )
        suggested = self._suggested(rec)
        assert "anthropic /" not in suggested
        assert "openai /" not in suggested

    def test_a_stage_without_a_winner_is_left_alone(self) -> None:
        rec = recommendation(scope="anthropic", model=None, reason="no eligible model")
        assert "→" not in self._suggested(rec)

    def test_with_nothing_to_change_it_says_so(self) -> None:
        assert "No changes" in self._suggested()

    def test_it_reminds_that_the_maintainer_applies_changes_by_hand(self) -> None:
        assert "builtin_model_profiles.py" in self._suggested()


class TestTokenEstimates:
    def test_it_sets_measured_medians_beside_the_stage_requirements(self) -> None:
        report = _render(
            summaries=[summary(stage=StageKey.TAILOR, median_in=12345, median_out=6789)]
        )
        section = _section(report, "Token estimates")
        requirement = STAGE_REQUIREMENTS[StageKey.TAILOR]
        assert (
            f"| tailor | 12345 | 6789 | {requirement.est_input_tokens} "
            f"| {requirement.est_output_tokens} |" in section
        )

    def test_the_median_is_taken_across_the_models_of_a_stage(self) -> None:
        report = _render(
            summaries=[
                summary(model="a", median_in=1000, median_out=100),
                summary(model="b", median_in=3000, median_out=300),
                summary(model="c", median_in=9000, median_out=900),
            ]
        )
        assert "| tailor | 3000 | 300 |" in _section(report, "Token estimates")

    def test_stages_with_no_measurement_are_not_listed(self) -> None:
        report = _render(summaries=[summary(stage=StageKey.TAILOR)])
        assert "| analyze |" not in _section(report, "Token estimates")

    def test_a_stage_measured_only_on_one_side_is_not_listed(self) -> None:
        report = _render(
            summaries=[summary(stage=StageKey.TAILOR, median_in=4000, median_out=None)]
        )
        assert "No measurements." in _section(report, "Token estimates")

    def test_a_model_without_tokens_does_not_count(self) -> None:
        report = _render(
            summaries=[
                summary(model="a", median_in=None, median_out=None),
                summary(model="b", median_in=4000, median_out=400),
            ]
        )
        assert "| tailor | 4000 | 400 |" in _section(report, "Token estimates")


def test_the_report_ends_with_a_newline() -> None:
    assert _render().endswith("\n")


def test_models_from_the_matrix_without_results_do_not_appear_in_tables() -> None:
    report = _render(
        manifest=manifest(models=[MatrixModel(provider="google", model="ghost")]),
        summaries=[summary()],
    )
    assert "ghost" not in _section(report, "Stage: tailor")
