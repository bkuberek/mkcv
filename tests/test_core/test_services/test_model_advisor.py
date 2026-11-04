"""Tests for ModelAdvisor (REQ-MP-5 to MP-11, design section 8.1).

The advisor is pure core logic: assignments, a catalog, and profiles go in; a
report comes out. No configuration or provider registry is involved.
"""

from collections.abc import Sequence

import pytest

from mkcv.core.catalog.builtin_model_profiles import BUILTIN_MODEL_PROFILES
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_report import ModelReport
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_advice import StageAdvice
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey
from mkcv.core.services.model_advisor import ModelAdvisor

_ANTHROPIC_PROFILE = BUILTIN_MODEL_PROFILES["anthropic"]
_KIND_FOR_PROVIDER = {
    "anthropic": ProviderKind.ANTHROPIC,
    "openai": ProviderKind.OPENAI,
    "google": ProviderKind.GOOGLE,
    "ollama": ProviderKind.OPENAI_COMPATIBLE,
    "openrouter": ProviderKind.OPENAI_COMPATIBLE,
    "groq": ProviderKind.OPENAI_COMPATIBLE,
    "stub": ProviderKind.STUB,
}


def _assignment(
    stage: StageKey,
    provider: str,
    model: str,
    source: str = "config",
    kind: ProviderKind | None = None,
) -> StageAssignment:
    return StageAssignment.model_validate(
        {
            "stage": stage,
            "provider": provider,
            "provider_kind": kind or _KIND_FOR_PROVIDER[provider],
            "model": model,
            "temperature": 0.3,
            "source": source,
        }
    )


def _default_assignments() -> list[StageAssignment]:
    """The five pipeline stages as the anthropic profile assigns them."""
    return [
        _assignment(stage, "anthropic", _ANTHROPIC_PROFILE.stages[stage], "profile")
        for stage in PIPELINE_STAGES
    ]


def _advise(
    assignments: Sequence[StageAssignment],
    *,
    catalog: ModelCatalog | None = None,
    provider_warnings: Sequence[ModelWarning] = (),
    provider_defaults: dict[str, CapabilityOverlay] | None = None,
) -> ModelReport:
    advisor = ModelAdvisor(catalog or ModelCatalog.builtin())
    return advisor.advise(
        assignments,
        profile=_ANTHROPIC_PROFILE,
        profile_source="default",
        preset_name="standard",
        provider_warnings=provider_warnings,
        provider_defaults=provider_defaults,
    )


def _warning_kinds(report: ModelReport) -> list[ModelWarningKind]:
    return [warning.kind for warning in report.warnings]


def _advice(report: ModelReport, stage: StageKey) -> StageAdvice:
    return next(item for item in report.stages if item.assignment.stage is stage)


class TestProfileAssignmentsAreNotQuestioned:
    """REQ-MP-5."""

    def test_the_default_profile_produces_no_warnings(self) -> None:
        assert _advise(_default_assignments()).warnings == []

    def test_economy_models_below_the_minimum_tier_are_not_flagged(self) -> None:
        haiku = [
            _assignment(stage, "anthropic", "claude-haiku-5-5", "profile")
            for stage in PIPELINE_STAGES
        ]
        assert _advise(haiku).warnings == []

    def test_a_config_choice_of_the_same_models_is_flagged(self) -> None:
        haiku = [
            _assignment(StageKey.SELECT, "anthropic", "claude-haiku-5-5", "config")
        ]
        assert _warning_kinds(_advise(haiku)) == [
            ModelWarningKind.BELOW_RECOMMENDED_TIER
        ]


class TestBelowRecommendedTier:
    """REQ-MP-6."""

    def test_the_message_names_the_stage_model_tier_and_recommendation(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        assert [w.message for w in report.warnings] == [
            "tailor: openai/gpt-6.1-terra is tier 'efficient'; mkcv recommends at "
            "least 'strong' for this stage (recommended: openai/gpt-6-astra)."
        ]

    def test_the_warning_carries_stage_provider_and_model(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        warning = report.warnings[0]
        assert (warning.kind, warning.stage, warning.provider, warning.model) == (
            ModelWarningKind.BELOW_RECOMMENDED_TIER,
            StageKey.TAILOR,
            "openai",
            "gpt-6.1-terra",
        )

    def test_a_model_at_the_minimum_tier_is_accepted(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "openai", "gpt-6.1-terra", "config")]
        )
        assert report.warnings == []

    def test_cli_choices_are_checked_like_config_choices(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "cli")]
        )
        assert _warning_kinds(report) == [ModelWarningKind.BELOW_RECOMMENDED_TIER]


class TestUnknownModel:
    """REQ-MP-7."""

    def test_the_message_says_no_capability_data_exists(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config")]
        )
        assert [w.message for w in report.warnings] == [
            "analyze: no capability data for openai/gpt-7-nova; mkcv will use "
            "conservative defaults. Describe it with a [[default.model_catalog]] "
            "entry."
        ]

    def test_an_unknown_model_gets_only_the_unknown_warning(self) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "openai", "gpt-7-nova", "config")]
        )
        assert _warning_kinds(report) == [ModelWarningKind.UNKNOWN_MODEL]

    def test_advice_marks_the_model_unknown(self) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "openai", "gpt-7-nova", "config")]
        )
        advice = _advice(report, StageKey.SELECT)
        assert (advice.known, advice.tier) == (False, None)


class TestTierUnknown:
    """REQ-MP-8."""

    @pytest.fixture
    def catalog(self) -> ModelCatalog:
        return ModelCatalog.builtin().with_overrides(
            [ModelCapability(provider="groq", match="m")]
        )

    def test_a_catalogued_model_without_a_tier_is_reported(
        self, catalog: ModelCatalog
    ) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "groq", "m", "config")], catalog=catalog
        )
        assert [w.message for w in report.warnings] == [
            "select: quality tier of groq/m is unknown; mkcv recommends at least "
            "'strong' for this stage (recommended: anthropic/claude-opus-5-5)."
        ]

    def test_the_kind_is_tier_unknown(self, catalog: ModelCatalog) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "groq", "m", "config")], catalog=catalog
        )
        assert _warning_kinds(report) == [ModelWarningKind.TIER_UNKNOWN]

    def test_profile_assignments_are_not_reported(self, catalog: ModelCatalog) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "groq", "m", "profile")], catalog=catalog
        )
        assert report.warnings == []


class TestDeprecatedModel:
    """REQ-MP-9."""

    def test_the_message_includes_the_catalog_note(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "google", "gemini-2.5-flash", "config")]
        )
        deprecated = next(
            w for w in report.warnings if w.kind is ModelWarningKind.DEPRECATED_MODEL
        )
        assert "route to gemini-3.5-flash-lite" in deprecated.message

    def test_the_message_starts_with_stage_and_model(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "google", "gemini-2.5-flash", "config")]
        )
        deprecated = next(
            w for w in report.warnings if w.kind is ModelWarningKind.DEPRECATED_MODEL
        )
        assert deprecated.message.startswith(
            "analyze: google/gemini-2.5-flash is deprecated. "
        )

    def test_a_note_is_optional(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [ModelCapability(provider="groq", match="old", deprecated=True)]
        )
        report = _advise(
            [_assignment(StageKey.ANALYZE, "groq", "old", "profile")], catalog=catalog
        )
        assert [w.message for w in report.warnings] == [
            "analyze: groq/old is deprecated."
        ]

    def test_profile_assignments_are_still_reported(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [ModelCapability(provider="groq", match="old", deprecated=True)]
        )
        report = _advise(
            [_assignment(StageKey.ANALYZE, "groq", "old", "profile")], catalog=catalog
        )
        assert _warning_kinds(report) == [ModelWarningKind.DEPRECATED_MODEL]


class TestProviderWarningsComeFirst:
    def test_provider_warnings_precede_stage_warnings(self) -> None:
        provider_warning = ModelWarning(
            kind=ModelWarningKind.MISSING_API_KEY,
            stage=None,
            provider="openai",
            model=None,
            message="openai: no API key found",
        )
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")],
            provider_warnings=[provider_warning],
        )
        assert _warning_kinds(report) == [
            ModelWarningKind.MISSING_API_KEY,
            ModelWarningKind.BELOW_RECOMMENDED_TIER,
        ]

    def test_stage_warnings_follow_assignment_order(self) -> None:
        report = _advise(
            [
                _assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config"),
                _assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config"),
            ]
        )
        assert [w.stage for w in report.warnings] == [
            StageKey.TAILOR,
            StageKey.ANALYZE,
        ]

    def test_each_advice_carries_only_its_own_warnings(self) -> None:
        report = _advise(
            [
                _assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config"),
                _assignment(StageKey.ANALYZE, "anthropic", "claude-haiku-5-5"),
            ]
        )
        assert [len(a.warnings) for a in report.stages] == [1, 0]


class TestRecommendation:
    """REQ-MP-11, recommended model."""

    def test_the_recommendation_comes_from_the_providers_profile(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        advice = _advice(report, StageKey.TAILOR)
        assert (advice.recommended_provider, advice.recommended_model) == (
            "openai",
            "gpt-6-astra",
        )

    def test_a_provider_without_a_profile_is_pointed_at_anthropic(self) -> None:
        report = _advise([_assignment(StageKey.TAILOR, "groq", "llama-3.3-70b")])
        advice = _advice(report, StageKey.TAILOR)
        assert (advice.recommended_provider, advice.recommended_model) == (
            "anthropic",
            "claude-opus-5-5",
        )

    def test_the_recommendation_ignores_the_economy_variant(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6-luna", "config")]
        )
        assert _advice(report, StageKey.TAILOR).recommended_model == "gpt-6-astra"

    def test_the_recommendation_skips_an_economy_profile_listed_first(self) -> None:
        profiles = {
            "openai-economy": BUILTIN_MODEL_PROFILES["openai-economy"],
            "openai": BUILTIN_MODEL_PROFILES["openai"],
        }
        advisor = ModelAdvisor(ModelCatalog.builtin(), profiles=profiles)
        report = advisor.advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6-luna", "config")],
            profile=None,
            profile_source="config",
            preset_name="default",
        )
        assert _advice(report, StageKey.TAILOR).recommended_model == "gpt-6-astra"

    def test_advice_reports_tier_and_required_tier(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        advice = _advice(report, StageKey.TAILOR)
        assert (advice.tier, advice.min_tier) == (
            ModelTier.EFFICIENT,
            ModelTier.STRONG,
        )


class TestCost:
    """REQ-MP-11, cost."""

    def test_stage_cost_applies_the_catalog_price_to_the_token_estimate(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        requirement = STAGE_REQUIREMENTS[StageKey.TAILOR]
        expected = round(
            (requirement.est_input_tokens * 1.0 + requirement.est_output_tokens * 5.0)
            / 1_000_000,
            6,
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd == expected

    def test_tailor_cost_matches_the_specified_figure(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "openai", "gpt-6.1-terra", "config")]
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd == round(
            (15000 * 1.0 + 8000 * 5.0) / 1_000_000, 6
        )

    def test_the_total_sums_every_stage(self) -> None:
        report = _advise(_default_assignments())
        assert report.estimated_total_usd == pytest.approx(
            sum(a.estimated_cost_usd or 0.0 for a in report.stages)
        )

    def test_a_complete_estimate_is_not_partial(self) -> None:
        assert _advise(_default_assignments()).estimate_is_partial is False

    def test_an_unknown_model_has_no_cost(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config")]
        )
        assert _advice(report, StageKey.ANALYZE).estimated_cost_usd is None

    def test_an_unknown_model_makes_the_estimate_partial(self) -> None:
        report = _advise(
            [
                _assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config"),
                _assignment(StageKey.SELECT, "anthropic", "claude-opus-5-5"),
            ]
        )
        assert report.estimate_is_partial is True

    def test_the_partial_total_still_sums_the_known_stages(self) -> None:
        report = _advise(
            [
                _assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config"),
                _assignment(StageKey.SELECT, "anthropic", "claude-opus-5-5"),
            ]
        )
        assert (
            report.estimated_total_usd
            == _advice(report, StageKey.SELECT).estimated_cost_usd
        )

    def test_when_nothing_is_priced_the_total_is_none_and_not_partial(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "openai", "gpt-7-nova", "config")]
        )
        assert (report.estimated_total_usd, report.estimate_is_partial) == (
            None,
            False,
        )

    def test_provider_defaults_price_models_the_catalog_does_not(self) -> None:
        defaults = {
            "ollama": CapabilityOverlay(
                input_price_per_mtok=0.0, output_price_per_mtok=0.0
            )
        }
        report = _advise(
            [_assignment(StageKey.TAILOR, "ollama", "llama3.1:8b", "profile")],
            provider_defaults=defaults,
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd == 0.0

    def test_without_provider_defaults_that_model_has_no_cost(self) -> None:
        report = _advise(
            [_assignment(StageKey.TAILOR, "ollama", "llama3.1:8b", "profile")]
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd is None

    def test_provider_defaults_with_only_one_price_are_ignored(self) -> None:
        defaults = {"ollama": CapabilityOverlay(input_price_per_mtok=0.0)}
        report = _advise(
            [_assignment(StageKey.TAILOR, "ollama", "llama3.1:8b", "profile")],
            provider_defaults=defaults,
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd is None

    def test_the_stage_cost_is_rounded_to_six_places(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [
                ModelCapability(
                    provider="groq",
                    match="m",
                    input_price_per_mtok=0.1234567,
                    output_price_per_mtok=0.0,
                )
            ]
        )
        report = _advise(
            [_assignment(StageKey.ANALYZE, "groq", "m", "config")], catalog=catalog
        )
        assert _advice(report, StageKey.ANALYZE).estimated_cost_usd == 0.000494

    def test_a_custom_provider_borrows_the_prices_of_its_native_kind(self) -> None:
        report = _advise(
            [
                _assignment(
                    StageKey.TAILOR,
                    "my-openai",
                    "gpt-6.1-terra",
                    "config",
                    kind=ProviderKind.OPENAI,
                )
            ]
        )
        assert _advice(report, StageKey.TAILOR).estimated_cost_usd == round(
            (15000 * 1.0 + 8000 * 5.0) / 1_000_000, 6
        )

    def test_a_custom_provider_borrows_the_catalog_entry_of_its_native_kind(
        self,
    ) -> None:
        report = _advise(
            [
                _assignment(
                    StageKey.TAILOR,
                    "my-openai",
                    "gpt-6.1-terra",
                    "config",
                    kind=ProviderKind.OPENAI,
                )
            ]
        )
        assert _advice(report, StageKey.TAILOR).known is True


class TestOfflineStub:
    def test_the_stub_provider_is_never_questioned(self) -> None:
        report = _advise(
            [
                _assignment(
                    StageKey.TAILOR, "stub", "stub-model", "cli", kind=ProviderKind.STUB
                )
            ]
        )
        assert report.warnings == []


class TestReportMetadata:
    def test_the_report_names_the_profile_and_its_evidence(self) -> None:
        report = _advise(_default_assignments())
        assert (
            report.profile_name,
            report.profile_evidence,
            report.profile_source,
            report.preset_name,
        ) == ("anthropic", "provisional", "default", "standard")

    def test_without_a_profile_the_report_has_no_profile(self) -> None:
        report = ModelAdvisor(ModelCatalog.builtin()).advise(
            _default_assignments(),
            profile=None,
            profile_source="config",
            preset_name="default",
        )
        assert (report.profile_name, report.profile_evidence) == (None, None)

    def test_stages_keep_the_order_of_the_assignments(self) -> None:
        assignments = list(reversed(_default_assignments()))
        report = _advise(assignments)
        assert [a.assignment.stage for a in report.stages] == [
            a.stage for a in assignments
        ]


class TestRunningTheRecommendedModel:
    """A tier warning that recommends the model already in use is pointless."""

    def test_the_only_local_model_is_not_flagged_when_chosen_explicitly(self) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "ollama", "llama3.1:8b", "cli")]
        )
        assert report.warnings == []

    def test_the_recommended_cloud_model_is_not_flagged_when_chosen_in_config(
        self,
    ) -> None:
        report = _advise(
            [_assignment(StageKey.ANALYZE, "anthropic", "claude-haiku-5-5", "config")]
        )
        assert report.warnings == []

    def test_a_different_model_of_the_same_provider_is_still_flagged(self) -> None:
        report = _advise(
            [_assignment(StageKey.SELECT, "anthropic", "claude-haiku-5-5", "cli")]
        )
        assert _warning_kinds(report) == [ModelWarningKind.BELOW_RECOMMENDED_TIER]

    def test_a_deprecated_recommended_model_is_still_reported(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [ModelCapability(provider="ollama", match="llama3.1:8b", deprecated=True)]
        )
        report = _advise(
            [_assignment(StageKey.ANALYZE, "ollama", "llama3.1:8b", "cli")],
            catalog=catalog,
        )
        assert _warning_kinds(report) == [ModelWarningKind.DEPRECATED_MODEL]
