"""Immutable catalog of model capabilities with ordered overlay resolution."""

import functools
from collections.abc import Sequence

from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.resolved_model import ResolvedModel

# Providers whose model IDs identify a vendor, so an aggregator's
# "<vendor>/<model>" IDs can borrow vendor-neutral facts from them.
_VENDOR_PROVIDERS = frozenset({"anthropic", "openai", "google"})

# Facts that stay true when a model is served through an aggregator.
# Prices and request rules differ per host, so they are not borrowed.
_VENDOR_NEUTRAL_FIELDS = ("tier", "context_window", "max_output_tokens", "deprecated")

_REQUIRED_DEFAULT_FIELDS = (
    "structured_output",
    "allow_structured_fallback",
    "accepts_sampling_params",
    "token_param",
    "min_output_tokens",
)


class ModelCatalog:
    """Capability entries for known models, immutable after construction.

    Entries are overlaid in a fixed order (design section 4.3): prefix
    entries before exact entries, shorter matches before longer ones, and
    earlier entries before later ones. The last non-``None`` value wins.
    """

    def __init__(self, entries: Sequence[ModelCapability]) -> None:
        self._entries: tuple[ModelCapability, ...] = tuple(entries)

    @classmethod
    def builtin(cls) -> "ModelCatalog":
        """Return the shipped catalog (cached)."""
        return _builtin_catalog()

    @property
    def entries(self) -> tuple[ModelCapability, ...]:
        """All entries, built-ins first, then appended overrides in order."""
        return self._entries

    def with_overrides(self, overrides: Sequence[ModelCapability]) -> "ModelCatalog":
        """Return a new catalog with user entries layered on top.

        An override with the same key as an existing entry overlays that
        entry field by field; any other override is appended.
        """
        merged = list(self._entries)
        positions = {entry.key: index for index, entry in enumerate(merged)}
        for override in overrides:
            position = positions.get(override.key)
            if position is None:
                positions[override.key] = len(merged)
                merged.append(override)
            else:
                merged[position] = _overlay_entry(merged[position], override)
        return ModelCatalog(merged)

    def lookup(
        self,
        provider: str,
        model: str,
        *,
        canonical_provider: str | None = None,
    ) -> CapabilityOverlay | None:
        """Return the folded capabilities of ``model``, or None if unknown.

        Falls back to ``canonical_provider`` (for a custom provider that
        speaks a native provider's protocol) and then to the vendor prefix
        of an aggregator model ID such as ``openai/gpt-4o``.
        """
        matches = self._matching(provider, model)
        if not matches and canonical_provider and canonical_provider != provider:
            matches = self._matching(canonical_provider, model)
        if not matches and "/" in model:
            return self._lookup_vendor_model(model)
        return _fold(matches)

    def resolve(
        self,
        provider: str,
        model: str,
        *,
        defaults: CapabilityOverlay,
        canonical_provider: str | None = None,
    ) -> ResolvedModel:
        """Merge ``defaults`` with the catalog entry into a ``ResolvedModel``.

        Raises:
            ValueError: If ``defaults`` leaves a required capability unset.
        """
        missing = [
            name for name in _REQUIRED_DEFAULT_FIELDS if getattr(defaults, name) is None
        ]
        if missing:
            raise ValueError(
                f"Defaults for {provider}/{model} must set: {', '.join(missing)}"
            )

        found = self.lookup(provider, model, canonical_provider=canonical_provider)
        merged = defaults.overlay(found) if found is not None else defaults
        return ResolvedModel(
            provider=provider,
            model=model,
            known=found is not None,
            structured_output=_required(merged.structured_output, "structured_output"),
            allow_structured_fallback=_required(
                merged.allow_structured_fallback, "allow_structured_fallback"
            ),
            accepts_sampling_params=_required(
                merged.accepts_sampling_params, "accepts_sampling_params"
            ),
            token_param=_required(merged.token_param, "token_param"),
            min_output_tokens=_required(merged.min_output_tokens, "min_output_tokens"),
            max_output_tokens=merged.max_output_tokens,
            context_window=merged.context_window,
            input_price_per_mtok=merged.input_price_per_mtok,
            output_price_per_mtok=merged.output_price_per_mtok,
            tier=merged.tier,
            deprecated=bool(merged.deprecated),
            notes=merged.notes,
        )

    def price_for(
        self, model: str, *, provider: str | None = None
    ) -> tuple[float, float] | None:
        """Return ``(input, output)`` USD per 1M tokens, or None if unpriced.

        Without ``provider`` every provider's entries are considered.
        """
        folded = _fold(self._matching(provider, model))
        if folded is None:
            return None
        if folded.input_price_per_mtok is None or folded.output_price_per_mtok is None:
            return None
        return (folded.input_price_per_mtok, folded.output_price_per_mtok)

    def providers_for_model(self, model: str) -> tuple[str, ...]:
        """Return the native providers whose entries cover ``model``, sorted."""
        return tuple(
            sorted(
                {
                    entry.provider
                    for entry in self._entries
                    if entry.provider in _VENDOR_PROVIDERS and entry.matches(model)
                }
            )
        )

    def _matching(self, provider: str | None, model: str) -> list[ModelCapability]:
        """Return entries covering ``model`` in overlay order (last wins)."""
        candidates = [
            ((entry.match_type == "exact", len(entry.match), index), entry)
            for index, entry in enumerate(self._entries)
            if (provider is None or entry.provider == provider) and entry.matches(model)
        ]
        candidates.sort(key=lambda candidate: candidate[0])
        return [entry for _, entry in candidates]

    def _lookup_vendor_model(self, model: str) -> CapabilityOverlay | None:
        vendor, inner = model.split("/", 1)
        if vendor not in _VENDOR_PROVIDERS:
            return None
        folded = _fold(self._matching(vendor, inner))
        if folded is None:
            return None
        return CapabilityOverlay(
            **{name: getattr(folded, name) for name in _VENDOR_NEUTRAL_FIELDS}
        )


@functools.cache
def _builtin_catalog() -> ModelCatalog:
    # Imported lazily: the data module imports ``ModelCapability`` from this
    # package, so a top-level import here would be circular.
    from mkcv.core.catalog.builtin_models import BUILTIN_MODEL_CAPABILITIES

    return ModelCatalog(BUILTIN_MODEL_CAPABILITIES)


def _fold(matches: Sequence[ModelCapability]) -> CapabilityOverlay | None:
    if not matches:
        return None
    return functools.reduce(
        lambda folded, match: folded.overlay(match), matches, CapabilityOverlay()
    )


def _overlay_entry(
    existing: ModelCapability, override: ModelCapability
) -> ModelCapability:
    fields = existing.overlay(override).model_dump()
    return ModelCapability(
        provider=existing.provider,
        match=existing.match,
        match_type=existing.match_type,
        display_name=override.display_name or existing.display_name,
        **fields,
    )


def _required[T](value: T | None, name: str) -> T:
    if value is None:
        raise ValueError(f"Capability '{name}' is not set")
    return value
