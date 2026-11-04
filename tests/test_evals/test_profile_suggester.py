"""Tests for the suggested provider profiles and the cross-provider profile."""

from evals.models.recommendation import OVERALL
from evals.report.profile_suggester import (
    RECOMMENDED_PROFILE,
    not_evaluated,
    suggest_profiles,
)
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import recommendation, summary


def _by_name(*recs: object) -> dict[str, object]:
    return {p.name: p for p in suggest_profiles(list(recs))}  # type: ignore[arg-type]


class TestProviderProfiles:
    def test_each_evaluated_providers_profile_follows_its_best_models(self) -> None:
        profiles = _by_name(
            recommendation(
                scope="anthropic", provider="anthropic", model="claude-sonnet-5-5"
            ),
            recommendation(scope="openai", model="gpt-6.1-sol"),
        )
        anthropic = profiles["anthropic"]
        [choice] = anthropic.choices  # type: ignore[attr-defined]
        assert (choice.stage, choice.model, choice.current) == (
            StageKey.TAILOR,
            "claude-sonnet-5-5",
            "claude-opus-5-5",
        )
        assert choice.changed is True
        assert sorted(profiles) == ["anthropic", "openai"]

    def test_a_choice_equal_to_the_profile_is_not_a_change(self) -> None:
        profiles = _by_name(
            recommendation(
                scope="anthropic", provider="anthropic", model="claude-opus-5-5"
            )
        )
        assert profiles["anthropic"].choices[0].changed is False  # type: ignore[attr-defined]

    def test_economy_profiles_are_not_suggested(self) -> None:
        profiles = _by_name(recommendation(scope="openai", model="gpt-6-luna"))
        assert "openai-economy" not in profiles

    def test_a_stage_without_a_winner_has_no_choice(self) -> None:
        profiles = _by_name(
            recommendation(scope="openai", model=None, reason="no eligible model")
        )
        assert "openai" not in profiles


class TestRecommendedProfile:
    def test_it_takes_the_overall_winner_of_every_stage(self) -> None:
        profiles = _by_name(
            recommendation(stage=StageKey.ANALYZE, provider="google", model="flash"),
            recommendation(
                stage=StageKey.TAILOR, provider="anthropic", model="claude-opus-5-5"
            ),
        )
        recommended = profiles[RECOMMENDED_PROFILE]
        assert recommended.provider is None  # type: ignore[attr-defined]
        assert [
            (c.stage, c.provider, c.model)
            for c in recommended.choices  # type: ignore[attr-defined]
        ] == [
            (StageKey.ANALYZE, "google", "flash"),
            (StageKey.TAILOR, "anthropic", "claude-opus-5-5"),
        ]

    def test_a_new_profile_has_no_current_model(self) -> None:
        profiles = _by_name(recommendation())
        assert profiles[RECOMMENDED_PROFILE].choices[0].current is None  # type: ignore[attr-defined]

    def test_a_choice_too_close_to_call_is_marked(self) -> None:
        profiles = _by_name(recommendation(scope=OVERALL, too_close_to_call=True))
        assert profiles[RECOMMENDED_PROFILE].choices[0].too_close_to_call is True  # type: ignore[attr-defined]


class TestNotEvaluated:
    def test_kb_and_validate_are_always_listed_with_why(self) -> None:
        missing = not_evaluated([summary(stage=StageKey.TAILOR)])
        assert "source-document" in missing[StageKey.KB]
        assert "PDF" in missing[StageKey.VALIDATE]

    def test_a_stage_the_run_left_out_is_listed(self) -> None:
        missing = not_evaluated([summary(stage=StageKey.TAILOR)])
        assert missing[StageKey.ANALYZE] == "not in this run"
        assert StageKey.TAILOR not in missing
