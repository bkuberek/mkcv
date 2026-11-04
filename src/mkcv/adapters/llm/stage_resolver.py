"""Resolve which provider, model, and temperature every stage runs on.

Precedence, highest first:

1. Command-line flags: ``--model-profile``, ``--provider``, and ``kb --model``.
2. Per-stage configuration: ``[default.pipeline.stages.<stage>]`` and the
   other stage sections, read as ``provider``, ``model``, ``temperature``.
3. The model profile: ``pipeline.model_profile``, else the profile of
   ``pipeline.provider``, else the profile of ``DEFAULT_PROVIDER``.

A preset contributes only two things: whether to prefer the economy variant
of a profile, and (for the legacy ``budget`` preset) a provider.

This module owns the one default provider; nothing else may hard-code it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from mkcv.adapters.llm.resolved_stages import ProfileSource, ResolvedStages
from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    get_profile,
    profile_for_provider,
    profile_stage_model,
)
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.profile_preset import resolve_preset
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_key import StageKey

if TYPE_CHECKING:
    from mkcv.adapters.llm.provider_registry import ProviderRegistry
    from mkcv.adapters.llm.resolution_request import ResolutionRequest
    from mkcv.config.configuration import Configuration
    from mkcv.core.models.model_profile import ModelProfile
    from mkcv.core.models.stage_requirement import StageRequirement

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "anthropic"
"""Provider used when neither a profile nor a provider is configured."""

STUB_MODEL = "stub-model"
"""Model name for the offline stub provider, which has no models of its own."""

_MIN_TEMPERATURE = 0.0
_MAX_TEMPERATURE = 2.0

type _Source = Literal["cli", "config", "profile"]


@dataclass(frozen=True)
class _Plan:
    """Decisions shared by every stage of one resolution."""

    request: ResolutionRequest
    profile: ModelProfile | None
    profile_source: ProfileSource
    base_provider: str
    """Provider a stage uses when nothing names one more specifically."""
    override: str | None
    """Provider every stage must use: ``--provider`` or the preset's provider."""
    economy: bool

    @property
    def override_from_cli(self) -> bool:
        return self.request.provider_override is not None


@dataclass(frozen=True)
class _Choice:
    """A stage's provider and model before they are checked and priced."""

    provider: str
    model: str | None
    source: _Source


class StageResolver:
    """Turns configuration, command-line flags, and profiles into stage models."""

    def __init__(self, config: Configuration, registry: ProviderRegistry) -> None:
        self._config = config
        self._registry = registry

    def resolve(
        self, stages: Sequence[StageKey], request: ResolutionRequest
    ) -> ResolvedStages:
        """Choose provider, model, and temperature for each of ``stages``.

        Raises:
            ConfigurationError: If the flags conflict, a profile or provider
                is unknown, a setting is invalid, or a stage has no model.
        """
        plan = self._plan(request)
        assignments: dict[StageKey, StageAssignment] = {}
        unresolved: list[str] = []

        for stage in stages:
            requirement = STAGE_REQUIREMENTS[stage]
            section = self._section(requirement.config_path)
            temperature = _temperature(section, requirement)
            choice = self._choose(stage, section, plan)
            spec = self._registry.get(choice.provider)
            model = choice.model
            if model is None and spec.kind is ProviderKind.STUB:
                model = STUB_MODEL
            if model is None:
                unresolved.append(_unresolved_line(requirement, choice.provider))
                continue
            assignments[stage] = StageAssignment(
                stage=stage,
                provider=choice.provider,
                provider_kind=spec.kind,
                model=model,
                temperature=temperature,
                source=choice.source,
            )

        if unresolved:
            raise ConfigurationError("Cannot resolve models:\n" + "\n".join(unresolved))

        for assignment in assignments.values():
            logger.info(
                "Stage %s: %s/%s (source=%s, temperature=%.2f)",
                assignment.stage,
                assignment.provider,
                assignment.model,
                assignment.source,
                assignment.temperature,
            )
        return ResolvedStages(
            assignments=assignments,
            profile=plan.profile,
            profile_source=plan.profile_source,
            preset_name=request.preset_name,
        )

    # ------------------------------------------------------------------
    # Profile selection
    # ------------------------------------------------------------------

    def _plan(self, request: ResolutionRequest) -> _Plan:
        if request.model_profile and request.provider_override:
            raise ConfigurationError(
                "--model-profile and --provider cannot be used together"
            )

        preset = resolve_preset(request.preset_name)
        economy = preset.economy if preset else False
        override = request.provider_override or (preset.provider if preset else None)
        if override:
            self._registry.get(override)

        if request.model_profile:
            named = _named_profile(request.model_profile)
            return _Plan(request, named, "cli", named.provider, override, economy)

        if override:
            source: ProfileSource = "cli" if request.provider_override else "preset"
            return _Plan(
                request,
                profile_for_provider(override, economy=economy),
                source,
                override,
                override,
                economy,
            )

        configured_profile = self._text_setting("pipeline.model_profile")
        if configured_profile:
            chosen = _economy_variant(_named_profile(configured_profile), economy)
            return _Plan(request, chosen, "config", chosen.provider, None, economy)

        configured_provider = self._text_setting("pipeline.provider")
        provider = configured_provider or DEFAULT_PROVIDER
        self._registry.get(provider)
        return _Plan(
            request,
            profile_for_provider(provider, economy=economy),
            "config" if configured_provider else "default",
            provider,
            None,
            economy,
        )

    # ------------------------------------------------------------------
    # Per-stage choice
    # ------------------------------------------------------------------

    def _choose(
        self, stage: StageKey, section: Mapping[str, Any], plan: _Plan
    ) -> _Choice:
        path = STAGE_REQUIREMENTS[stage].config_path
        configured_provider = _text(section, "provider", path)
        configured_model = _text(section, "model", path)
        request = plan.request

        if stage is StageKey.KB and request.model_override:
            provider = (
                request.provider_override or configured_provider or plan.base_provider
            )
            return _Choice(provider, request.model_override, "cli")

        if request.model_profile:
            return _Choice(plan.base_provider, _profile_model(plan, stage), "cli")

        override = plan.override
        if override:
            # Every stage must run on this provider: configuration for that
            # provider is kept, configuration for any other is ignored.
            if configured_model and configured_provider == override:
                return _Choice(override, configured_model, "config")
            source: _Source = "cli" if plan.override_from_cli else "profile"
            return _Choice(override, _profile_model(plan, stage), source)

        if configured_model:
            provider = configured_provider or self._infer_provider(
                configured_model, plan
            )
            return _Choice(provider, configured_model, "config")

        if configured_provider:
            profile = profile_for_provider(configured_provider, economy=plan.economy)
            model = profile_stage_model(profile, stage) if profile else None
            return _Choice(configured_provider, model, "config")

        return _Choice(plan.base_provider, _profile_model(plan, stage), "profile")

    def _infer_provider(self, model: str, plan: _Plan) -> str:
        """Provider for a model given without one: its only known home, else default."""
        candidates = self._registry.catalog.providers_for_model(model)
        return candidates[0] if len(candidates) == 1 else plan.base_provider

    # ------------------------------------------------------------------
    # Configuration access
    # ------------------------------------------------------------------

    def _section(self, path: str) -> Mapping[str, Any]:
        section = self._config.get(path)
        if section is None:
            return {}
        if not isinstance(section, Mapping):
            raise ConfigurationError(f"[default.{path}] must be a table")
        return section

    def _text_setting(self, path: str) -> str | None:
        value = self._config.get(path)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ConfigurationError(f"{path} must be a string")
        return value


def _named_profile(name: str) -> ModelProfile:
    profile = get_profile(name)
    if profile is None:
        available = ", ".join(sorted(BUILTIN_MODEL_PROFILES))
        raise ConfigurationError(
            f"Unknown model profile '{name}'. Available: {available}"
        )
    return profile


def _economy_variant(profile: ModelProfile, economy: bool) -> ModelProfile:
    """Swap a regular profile for its provider's economy variant when asked."""
    if not economy or profile.economy:
        return profile
    return profile_for_provider(profile.provider, economy=True) or profile


def _profile_model(plan: _Plan, stage: StageKey) -> str | None:
    return profile_stage_model(plan.profile, stage) if plan.profile else None


def _text(section: Mapping[str, Any], key: str, path: str) -> str | None:
    value = section.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ConfigurationError(f"{key} in [default.{path}] must be a string")
    return value


def _temperature(section: Mapping[str, Any], requirement: StageRequirement) -> float:
    raw = section.get("temperature", requirement.default_temperature)
    path = requirement.config_path
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ConfigurationError(
            f"temperature in [default.{path}] must be a number"
        ) from None
    if not _MIN_TEMPERATURE <= value <= _MAX_TEMPERATURE:
        raise ConfigurationError(
            f"temperature in [default.{path}] must be between 0 and 2"
        )
    return value


def _unresolved_line(requirement: StageRequirement, provider: str) -> str:
    return (
        f"No model for stage '{requirement.stage}' with provider '{provider}': "
        f"set model in [default.{requirement.config_path}] "
        "or choose a --model-profile."
    )
