"""Tests for the two-round tournament: screening, eliminations, and finals."""

import pytest

from evals.cli import DEFAULT_MATRIX as MATRIX_FILE
from evals.harness.case_loader import load_matrix
from evals.harness.tournament import (
    decide_survivors,
    finals_models,
    screening_cases,
    screening_judges,
    unknown_screening_cases,
)
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.tournament_settings import TournamentSettings
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import CASE_BY_ID, make_case
from tests.test_evals.report_support import summary

DEFAULT_MATRIX = load_matrix(MATRIX_FILE)
PANEL = [
    JudgeConfig(provider="anthropic", model="claude-opus-5-5"),
    JudgeConfig(provider="openai", model="gpt-6-astra"),
    JudgeConfig(provider="google", model="gemini-4-argon"),
]


class TestSettings:
    def test_the_shipped_matrix_runs_a_tournament(self) -> None:
        settings = DEFAULT_MATRIX.tournament
        assert settings.enabled is True
        assert (settings.screening_repeats, DEFAULT_MATRIX.run.repeats) == (1, 2)
        assert (settings.keep_top, settings.keep_per_provider) == (3, 1)

    def test_the_shipped_screening_subset_is_about_eight_known_cases(self) -> None:
        subset = DEFAULT_MATRIX.tournament.screening_cases
        assert 6 <= len(subset) <= 10
        assert set(subset) <= set(CASE_BY_ID)

    def test_the_shipped_subset_covers_match_stretch_and_overreach(self) -> None:
        subset = DEFAULT_MATRIX.tournament.screening_cases
        for kind in ("-match", "-stretch", "-overreach"):
            assert any(case.endswith(kind) for case in subset)

    def test_the_shipped_subset_has_cover_letter_cases(self) -> None:
        subset = DEFAULT_MATRIX.tournament.screening_cases
        assert sum(CASE_BY_ID[c].cover_letter is not None for c in subset) >= 3

    def test_the_margin_must_not_be_negative(self) -> None:
        with pytest.raises(ValueError):
            TournamentSettings(margin=-0.1)


class TestScreeningCases:
    def test_the_listed_cases_and_every_probe_are_screened(self) -> None:
        settings = TournamentSettings(screening_cases=["backend-platform-match"])
        chosen = [c.id for c in screening_cases(list(CASE_BY_ID.values()), settings)]
        assert chosen[0] == "backend-platform-match"
        assert {"review-probe", "review-probe-clinical"} <= set(chosen)
        assert "data-mlops-stretch" not in chosen

    def test_without_a_subset_every_case_is_screened(self) -> None:
        cases = list(CASE_BY_ID.values())
        assert screening_cases(cases, TournamentSettings()) == cases

    def test_a_subset_outside_the_selected_cases_screens_them_all(self) -> None:
        cases = [CASE_BY_ID["backend-ml-stretch"]]
        settings = TournamentSettings(screening_cases=["ghost"])
        assert screening_cases(cases, settings) == cases

    def test_unknown_screening_cases_are_reported(self) -> None:
        settings = TournamentSettings(screening_cases=["ghost", "review-probe"])
        assert unknown_screening_cases(list(CASE_BY_ID.values()), settings) == ["ghost"]

    def test_every_shipped_screening_case_exists(self) -> None:
        assert (
            unknown_screening_cases(
                list(CASE_BY_ID.values()), DEFAULT_MATRIX.tournament
            )
            == []
        )

    def test_a_cover_letter_probe_is_always_screened(self) -> None:
        probe = make_case(id="letter-probe", cover_letter={"review_defects": ["x"]})
        chosen = screening_cases([probe], TournamentSettings(screening_cases=[]))
        assert chosen == [probe]
        chosen = screening_cases(
            [make_case(id="a"), probe], TournamentSettings(screening_cases=["a"])
        )
        assert [c.id for c in chosen] == ["a", "letter-probe"]


class TestScreeningJudges:
    """Screening uses the finals' rule: every judge but the model's own provider's."""

    def test_they_are_the_panel_without_the_models_own_provider(self) -> None:
        model = MatrixModel(provider="openai", model="gpt-6-luna")
        assert screening_judges(model, PANEL) == [PANEL[0], PANEL[2]]

    def test_every_provider_is_judged_by_the_same_rule(self) -> None:
        judged_by = {
            provider: [
                j.provider
                for j in screening_judges(
                    MatrixModel(provider=provider, model="m"), PANEL
                )
            ]
            for provider in ("anthropic", "openai", "google")
        }
        assert judged_by == {
            "anthropic": ["openai", "google"],
            "openai": ["anthropic", "google"],
            "google": ["anthropic", "openai"],
        }

    def test_a_model_of_another_provider_gets_the_whole_panel(self) -> None:
        model = MatrixModel(provider="stub", model="m")
        assert screening_judges(model, PANEL) == PANEL

    def test_with_only_its_own_provider_it_falls_back_to_that_judge(self) -> None:
        model = MatrixModel(provider="openai", model="gpt-6-luna")
        assert screening_judges(model, PANEL[1:2]) == [PANEL[1]]

    def test_without_judges_there_are_none(self) -> None:
        model = MatrixModel(provider="openai", model="gpt-6-luna")
        assert screening_judges(model, []) == []


def _decisions(*summaries: object, **settings: object) -> dict[str, object]:
    found = decide_survivors(list(summaries), TournamentSettings(**settings))  # type: ignore[arg-type]
    return {f"{d.provider}/{d.model}": d for d in found}


class TestSurvivors:
    def test_a_model_that_fails_a_hard_gate_is_eliminated(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(
                model="faker",
                primary_score=0.95,
                eligible=False,
                gate_failures=["faithfulness_extraction: fabricated in 5% of runs"],
            ),
        )
        faker = decisions["openai/faker"]
        assert faker.kept is False  # type: ignore[attr-defined]
        assert "fabricated" in faker.reason  # type: ignore[attr-defined]

    def test_a_model_clearly_behind_the_leader_is_eliminated(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(model="weak", primary_score=0.6),
        )
        weak = decisions["openai/weak"]
        assert weak.kept is False  # type: ignore[attr-defined]
        assert "behind the leader" in weak.reason  # type: ignore[attr-defined]

    def test_a_model_within_the_margin_survives(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(model="close", primary_score=0.87),
        )
        assert decisions["openai/close"].kept is True  # type: ignore[attr-defined]

    def test_the_margin_is_configurable(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(model="close", primary_score=0.87),
            margin=0.01,
        )
        assert decisions["openai/close"].kept is False  # type: ignore[attr-defined]

    def test_the_noise_widens_the_tie_zone(self) -> None:
        def noisy(model: str, *scores: float) -> object:
            return summary(
                model=model, primary_score=sum(scores) / len(scores)
            ).model_copy(
                update={
                    "case_scores": {f"c{i}": s for i, s in enumerate(scores)},
                    "primary_n": len(scores),
                }
            )

        decisions = _decisions(
            *(noisy(f"m{i}", 0.9, 0.9, 0.9) for i in range(3)),
            noisy("swingy", 0.95, 0.5, 0.85),
            margin=0.05,
        )
        assert decisions["openai/swingy"].kept is True  # type: ignore[attr-defined]

    def test_the_top_three_always_survive(self) -> None:
        decisions = _decisions(
            summary(model="a", primary_score=0.9),
            summary(model="b", primary_score=0.5),
            summary(model="c", primary_score=0.4),
            summary(model="d", primary_score=0.3),
        )
        kept = sorted(k for k, d in decisions.items() if d.kept)  # type: ignore[attr-defined]
        assert kept == ["openai/a", "openai/b", "openai/c"]

    def test_the_best_of_each_provider_always_survives(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(provider="google", model="g-weak", primary_score=0.2),
            summary(provider="google", model="g-weaker", primary_score=0.1),
        )
        assert decisions["google/g-weak"].kept is True  # type: ignore[attr-defined]
        assert "best of google" in decisions["google/g-weak"].reason  # type: ignore[attr-defined]
        assert decisions["google/g-weaker"].kept is False  # type: ignore[attr-defined]

    def test_a_model_without_a_quality_score_survives(self) -> None:
        decisions = _decisions(
            *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
            summary(model="unscored", primary_score=None),
        )
        assert decisions["openai/unscored"].kept is True  # type: ignore[attr-defined]

    def test_decisions_are_per_stage(self) -> None:
        found = decide_survivors(
            [
                summary(stage=StageKey.TAILOR, model="a", primary_score=0.9),
                summary(stage=StageKey.ANALYZE, model="a", primary_score=0.9),
            ],
            TournamentSettings(),
        )
        assert sorted(d.stage.value for d in found) == ["analyze", "tailor"]


class TestFinalsModels:
    def test_finals_run_the_survivors_of_each_stage(self) -> None:
        found = decide_survivors(
            [
                *(summary(model=f"m{i}", primary_score=0.9) for i in range(3)),
                summary(model="weak", primary_score=0.1),
            ],
            TournamentSettings(),
        )
        survivors = finals_models(found)
        assert survivors[StageKey.TAILOR] == {
            "openai/m0",
            "openai/m1",
            "openai/m2",
        }
