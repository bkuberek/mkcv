"""Advice about the models assigned to stages: tiers, recommendations, and cost.

The advisor is pure: it is given resolved assignments and the catalog, and
returns a report. It never reads configuration or touches providers.

Warnings are advice, not errors. A model that mkcv's own profile chose is never
questioned for its tier; only the user's explicit choices are.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    profile_stage_model,
)
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_profile import ModelProfile
from mkcv.core.models.model_report import ModelReport, summarize_costs
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_advice import StageAdvice
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.stage_requirement import StageRequirement

_NATIVE_PROVIDERS = frozenset({"anthropic", "openai", "google"})
_FALLBACK_PROVIDER = "anthropic"
_TOKENS_PER_MILLION = 1_000_000
_COST_DECIMALS = 6

type ProfileSource = Literal["cli", "config", "default", "preset"]


class ModelAdvisor:
    """Checks stage assignments against the catalog and the stage requirements."""

    def __init__(
        self,
        catalog: ModelCatalog,
        requirements: Mapping[StageKey, StageRequirement] = STAGE_REQUIREMENTS,
        profiles: Mapping[str, ModelProfile] = BUILTIN_MODEL_PROFILES,
    ) -> None:
        self._catalog = catalog
        self._requirements = requirements
        self._profiles = profiles

    def advise(
        self,
        assignments: Sequence[StageAssignment],
        *,
        profile: ModelProfile | None,
        profile_source: ProfileSource,
        preset_name: str,
        provider_warnings: Sequence[ModelWarning] = (),
        provider_defaults: Mapping[str, CapabilityOverlay] | None = None,
    ) -> ModelReport:
        """Build the report for ``assignments``.

        Args:
            assignments: Resolved stages, in the order to report them.
            profile: The model profile behind the assignments, if any.
            profile_source: Where the profile (or provider) choice came from.
            preset_name: The preset the run uses.
            provider_warnings: Provider-level warnings, reported first.
            provider_defaults: Capability defaults per provider name, used to
                price models the catalog has no price for (e.g. local models).
        """
        defaults = provider_defaults or {}
        advice = [self._advise_stage(a, profile, defaults) for a in assignments]
        total, is_partial = summarize_costs(item.estimated_cost_usd for item in advice)
        return ModelReport(
            profile_name=profile.name if profile else None,
            profile_evidence=profile.evidence if profile else None,
            profile_source=profile_source,
            preset_name=preset_name,
            stages=advice,
            warnings=[
                *provider_warnings,
                *(w for item in advice for w in item.warnings),
            ],
            estimated_total_usd=total,
            estimate_is_partial=is_partial,
        )

    def _advise_stage(
        self,
        assignment: StageAssignment,
        profile: ModelProfile | None,
        defaults: Mapping[str, CapabilityOverlay],
    ) -> StageAdvice:
        requirement = self._requirements[assignment.stage]
        canonical = _canonical_provider(assignment)
        entry = self._catalog.lookup(
            assignment.provider, assignment.model, canonical_provider=canonical
        )
        tier = entry.tier if entry else None
        recommended_provider, recommended_model = self._recommendation(assignment)
        return StageAdvice(
            assignment=assignment,
            recommended_model=recommended_model,
            recommended_provider=recommended_provider,
            tier=tier,
            min_tier=requirement.min_tier,
            known=entry is not None,
            estimated_cost_usd=self._cost(assignment, requirement, canonical, defaults),
            warnings=_stage_warnings(
                assignment,
                requirement,
                entry,
                recommended=_describe(recommended_provider, recommended_model),
                mkcv_choice=_is_mkcv_choice(
                    assignment, profile, (recommended_provider, recommended_model)
                ),
            ),
        )

    def _recommendation(
        self, assignment: StageAssignment
    ) -> tuple[str | None, str | None]:
        """Return the provider and model mkcv recommends for the stage."""
        own = self._base_profile_for(assignment.provider)
        model = profile_stage_model(own, assignment.stage) if own else None
        if model is not None:
            return assignment.provider, model

        fallback = self._profiles.get(_FALLBACK_PROVIDER)
        model = profile_stage_model(fallback, assignment.stage) if fallback else None
        return (_FALLBACK_PROVIDER, model) if model is not None else (None, None)

    def _base_profile_for(self, provider: str) -> ModelProfile | None:
        return next(
            (
                profile
                for profile in self._profiles.values()
                if profile.provider == provider and not profile.economy
            ),
            None,
        )

    def _cost(
        self,
        assignment: StageAssignment,
        requirement: StageRequirement,
        canonical: str | None,
        defaults: Mapping[str, CapabilityOverlay],
    ) -> float | None:
        price = self._catalog.price_for(assignment.model, provider=assignment.provider)
        if price is None and canonical is not None:
            price = self._catalog.price_for(assignment.model, provider=canonical)
        if price is None:
            price = _default_price(defaults.get(assignment.provider))
        if price is None:
            return None
        input_price, output_price = price
        cost = (
            requirement.est_input_tokens * input_price
            + requirement.est_output_tokens * output_price
        ) / _TOKENS_PER_MILLION
        return round(cost, _COST_DECIMALS)


def _canonical_provider(assignment: StageAssignment) -> str | None:
    """Native provider whose catalog entries describe a custom provider's models."""
    kind = assignment.provider_kind.value
    return kind if kind in _NATIVE_PROVIDERS else None


def _is_mkcv_choice(
    assignment: StageAssignment,
    profile: ModelProfile | None,
    recommended: tuple[str | None, str | None],
) -> bool:
    """Return True when the stage runs a model mkcv itself picked for it.

    That is the model the active profile assigns to the stage (reached through
    ``--model-profile`` or ``--provider``, which label their rows ``cli``), or
    the model mkcv recommends for the provider.
    """
    chosen = (assignment.provider, assignment.model)
    if chosen == recommended:
        return True
    return (
        profile is not None
        and profile.provider == assignment.provider
        and profile_stage_model(profile, assignment.stage) == assignment.model
    )


def _default_price(overlay: CapabilityOverlay | None) -> tuple[float, float] | None:
    if overlay is None:
        return None
    if overlay.input_price_per_mtok is None or overlay.output_price_per_mtok is None:
        return None
    return overlay.input_price_per_mtok, overlay.output_price_per_mtok


def _describe(provider: str | None, model: str | None) -> str:
    return f"{provider}/{model}" if provider and model else "none"


def _stage_warnings(
    assignment: StageAssignment,
    requirement: StageRequirement,
    entry: CapabilityOverlay | None,
    *,
    recommended: str,
    mkcv_choice: bool,
) -> list[ModelWarning]:
    """Warnings for one stage.

    The offline stub is never second-guessed, and neither is a model mkcv
    itself chose (see ``_is_mkcv_choice``): a tier warning that recommends the
    model already in use, or that questions a profile the user picked on
    purpose, only adds noise.
    """
    if assignment.provider_kind is ProviderKind.STUB:
        return []

    stage = assignment.stage.value
    subject = f"{assignment.provider}/{assignment.model}"
    questioned = assignment.source != "profile" and not mkcv_choice

    def warn(kind: ModelWarningKind, message: str) -> ModelWarning:
        return ModelWarning(
            kind=kind,
            stage=assignment.stage,
            provider=assignment.provider,
            model=assignment.model,
            message=message,
        )

    if entry is None:
        return [
            warn(
                ModelWarningKind.UNKNOWN_MODEL,
                f"{stage}: no capability data for {subject}; mkcv will use "
                "conservative defaults. Describe it with a "
                "[[default.model_catalog]] entry.",
            )
        ]

    warnings: list[ModelWarning] = []
    minimum = requirement.min_tier.value
    if questioned and entry.tier is None:
        warnings.append(
            warn(
                ModelWarningKind.TIER_UNKNOWN,
                f"{stage}: quality tier of {subject} is unknown; mkcv recommends "
                f"at least '{minimum}' for this stage (recommended: {recommended}).",
            )
        )
    elif questioned and _below(entry.tier, requirement.min_tier):
        warnings.append(
            warn(
                ModelWarningKind.BELOW_RECOMMENDED_TIER,
                f"{stage}: {subject} is tier '{_tier_name(entry.tier)}'; mkcv "
                f"recommends at least '{minimum}' for this stage "
                f"(recommended: {recommended}).",
            )
        )
    if entry.deprecated:
        notes = f" {entry.notes}" if entry.notes else ""
        warnings.append(
            warn(
                ModelWarningKind.DEPRECATED_MODEL,
                f"{stage}: {subject} is deprecated.{notes}",
            )
        )
    return warnings


def _below(tier: ModelTier | None, minimum: ModelTier) -> bool:
    return tier is not None and tier.rank() < minimum.rank()


def _tier_name(tier: ModelTier | None) -> str:
    return tier.value if tier is not None else "unknown"
