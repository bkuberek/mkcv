"""Tests for the built-in model capability data (design section 4.1)."""

import subprocess
import sys
from typing import Any

import pytest

from mkcv.core.catalog.builtin_models import BUILTIN_MODEL_CAPABILITIES
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.structured_output_mode import StructuredOutputMode

_OVERLAY_FIELDS = tuple(CapabilityOverlay.model_fields)
_BY_KEY = {entry.key: entry for entry in BUILTIN_MODEL_CAPABILITIES}

_FRONTIER = ModelTier.FRONTIER
_STRONG = ModelTier.STRONG
_EFFICIENT = ModelTier.EFFICIENT
_MINIMAL = ModelTier.MINIMAL
_SCHEMA = StructuredOutputMode.JSON_SCHEMA
_TOOL = StructuredOutputMode.TOOL

_MILLION = 1_000_000
_ANTHROPIC_WINDOW: dict[str, Any] = {
    "context_window": _MILLION,
    "max_output_tokens": 128_000,
}
_GPT_6_WINDOW: dict[str, Any] = {
    "context_window": 1_050_000,
    "max_output_tokens": 128_000,
}


def _strict(tier: ModelTier) -> dict[str, Any]:
    return {
        "tier": tier,
        "structured_output": _SCHEMA,
        "accepts_sampling_params": False,
        "min_output_tokens": 16000,
    }


def _forced_tool(tier: ModelTier) -> dict[str, Any]:
    return {
        "tier": tier,
        "structured_output": _TOOL,
        "accepts_sampling_params": True,
        "min_output_tokens": 0,
    }


def _price(price_in: float, price_out: float, **extra: Any) -> dict[str, Any]:
    return {
        "input_price_per_mtok": price_in,
        "output_price_per_mtok": price_out,
        **extra,
    }


# (provider, match, match_type, every non-None overlay field)
ANTHROPIC_ROWS: list[tuple[str, str, str, dict[str, Any]]] = [
    ("anthropic", "claude-fable-", "prefix", _strict(_FRONTIER)),
    ("anthropic", "claude-mythos-", "prefix", _strict(_FRONTIER)),
    ("anthropic", "claude-opus-5", "prefix", _strict(_FRONTIER)),
    ("anthropic", "claude-sonnet-5", "prefix", _strict(_STRONG)),
    ("anthropic", "claude-haiku-5", "prefix", _strict(_EFFICIENT)),
    ("anthropic", "claude-opus-4-7", "prefix", _strict(_STRONG)),
    ("anthropic", "claude-opus-4-8", "prefix", _strict(_STRONG)),
    ("anthropic", "claude-opus-4-", "prefix", _forced_tool(_STRONG)),
    ("anthropic", "claude-sonnet-4-", "prefix", _forced_tool(_STRONG)),
    ("anthropic", "claude-haiku-4-", "prefix", _forced_tool(_EFFICIENT)),
    (
        "anthropic",
        "claude-3",
        "prefix",
        _forced_tool(_EFFICIENT)
        | {
            "deprecated": True,
            "notes": "Claude 3.x models are retired or retiring; move to a 5.x model.",
        },
    ),
    (
        "anthropic",
        "claude-fable-5-1",
        "exact",
        _ANTHROPIC_WINDOW
        | _price(10.0, 50.0, notes="Most capable Claude model; priced above Opus."),
    ),
    ("anthropic", "claude-opus-5-5", "exact", _ANTHROPIC_WINDOW | _price(4.0, 20.0)),
    ("anthropic", "claude-opus-5", "exact", _ANTHROPIC_WINDOW | _price(5.0, 25.0)),
    ("anthropic", "claude-sonnet-5-5", "exact", _ANTHROPIC_WINDOW | _price(2.0, 10.0)),
    ("anthropic", "claude-sonnet-5", "exact", _ANTHROPIC_WINDOW | _price(2.0, 10.0)),
    (
        "anthropic",
        "claude-haiku-5-5",
        "exact",
        _ANTHROPIC_WINDOW
        | _price(0.10, 0.50, notes="Prompts over 100K tokens bill at $0.50/$2.50."),
    ),
    ("anthropic", "claude-opus-4-8", "exact", _price(5.0, 25.0)),
    ("anthropic", "claude-opus-4-7", "exact", _price(5.0, 25.0)),
    ("anthropic", "claude-opus-4-6", "exact", _price(5.0, 25.0)),
    ("anthropic", "claude-sonnet-4-6", "exact", _price(3.0, 15.0)),
    ("anthropic", "claude-haiku-4-5", "exact", _price(1.0, 5.0)),
    ("anthropic", "claude-haiku-4-5-20251001", "exact", _price(1.0, 5.0)),
    ("anthropic", "claude-opus-4-20250514", "exact", _price(15.0, 75.0)),
    ("anthropic", "claude-sonnet-4-20250514", "exact", _price(3.0, 15.0)),
    ("anthropic", "claude-haiku-4-20250414", "exact", _price(0.8, 4.0)),
]


def _reasoning(notes: str | None = None) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "accepts_sampling_params": False,
        "min_output_tokens": 16000,
    }
    if notes:
        fields["notes"] = notes
    return fields


_SAMPLING = {"accepts_sampling_params": True, "min_output_tokens": 0}

OPENAI_ROWS: list[tuple[str, str, str, dict[str, Any]]] = [
    ("openai", "gpt-6", "prefix", _reasoning("GPT-6 family: reasoning models.")),
    ("openai", "gpt-5", "prefix", _reasoning("GPT-5 family: reasoning models.")),
    ("openai", "o1", "prefix", _reasoning()),
    ("openai", "o3", "prefix", _reasoning()),
    ("openai", "o4", "prefix", _reasoning()),
    ("openai", "gpt-4.1", "prefix", dict(_SAMPLING)),
    ("openai", "gpt-4o", "prefix", dict(_SAMPLING)),
    (
        "openai",
        "gpt-6-astra",
        "exact",
        _GPT_6_WINDOW | _price(10.0, 50.0, tier=_FRONTIER),
    ),
    (
        "openai",
        "gpt-6.1-sol",
        "exact",
        _GPT_6_WINDOW | _price(2.0, 10.0, tier=_STRONG),
    ),
    (
        "openai",
        "gpt-6.1-terra",
        "exact",
        _GPT_6_WINDOW | _price(1.0, 5.0, tier=_EFFICIENT),
    ),
    (
        "openai",
        "gpt-6-luna",
        "exact",
        _GPT_6_WINDOW | _price(0.10, 0.50, tier=_EFFICIENT),
    ),
    ("openai", "gpt-5.6-sol", "exact", _price(4.0, 20.0, tier=_STRONG)),
    ("openai", "gpt-5.6-terra", "exact", _price(2.0, 12.0, tier=_EFFICIENT)),
    ("openai", "gpt-5.6-luna", "exact", _price(0.20, 1.20, tier=_EFFICIENT)),
    ("openai", "gpt-5.5", "exact", _price(5.0, 30.0, tier=_STRONG)),
    ("openai", "gpt-5.4", "exact", _price(2.5, 15.0, tier=_STRONG)),
    ("openai", "gpt-5.4-mini", "exact", _price(0.75, 4.5, tier=_EFFICIENT)),
    ("openai", "gpt-5.4-nano", "exact", _price(0.20, 1.25, tier=_MINIMAL)),
    ("openai", "gpt-5", "exact", _price(1.25, 10.0, tier=_STRONG)),
    ("openai", "gpt-5-mini", "exact", _price(0.25, 2.0, tier=_EFFICIENT)),
    ("openai", "gpt-5-nano", "exact", _price(0.05, 0.40, tier=_MINIMAL)),
    ("openai", "gpt-4.1", "exact", _price(2.0, 8.0, tier=_STRONG)),
    ("openai", "gpt-4.1-mini", "exact", _price(0.40, 1.60, tier=_EFFICIENT)),
    ("openai", "gpt-4.1-nano", "exact", _price(0.10, 0.40, tier=_MINIMAL)),
    ("openai", "gpt-4o", "exact", _price(2.5, 10.0, tier=_STRONG)),
    ("openai", "gpt-4o-mini", "exact", _price(0.15, 0.60, tier=_EFFICIENT)),
]

_ARGON_PROMO = "Promotional $2.00/$10.00 through 2026-11-30."
_FLASH_PROMO = "Promotional $0.75/$3.75 through 2026-12-31."

GOOGLE_ROWS: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        "google",
        "gemini-4-argon",
        "exact",
        _price(4.0, 20.0, tier=_FRONTIER, context_window=_MILLION, notes=_ARGON_PROMO),
    ),
    (
        "google",
        "gemini-3.8-flash",
        "exact",
        _price(1.5, 7.5, tier=_STRONG, notes=_FLASH_PROMO),
    ),
    (
        "google",
        "gemini-3.6-flash",
        "exact",
        _price(1.5, 7.5, tier=_EFFICIENT, notes=_FLASH_PROMO),
    ),
    ("google", "gemini-3.5-flash-lite", "exact", _price(0.30, 2.5, tier=_EFFICIENT)),
    ("google", "gemini-3.1-flash-lite", "exact", _price(0.25, 1.5, tier=_MINIMAL)),
    (
        "google",
        "gemini-3.1-pro-preview",
        "exact",
        _price(
            2.0,
            12.0,
            tier=_STRONG,
            notes="Preview model; prompts over 200K tokens bill at $4.00/$18.00.",
        ),
    ),
    (
        "google",
        "gemini-2.5-pro",
        "exact",
        {
            "deprecated": True,
            "notes": "Deprecated; from 2026-12-01 requests route to gemini-3.8-flash.",
        },
    ),
    (
        "google",
        "gemini-2.5-flash",
        "exact",
        {
            "deprecated": True,
            "notes": (
                "Deprecated; from 2026-12-01 requests route to gemini-3.5-flash-lite."
            ),
        },
    ),
    (
        "google",
        "gemini-2.5-flash-lite",
        "exact",
        {"notes": "Limited to existing users; use gemini-3.5-flash-lite."},
    ),
]

OLLAMA_ROWS: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        "ollama",
        "llama3.1",
        "prefix",
        {
            "tier": _MINIMAL,
            "notes": "Small local model; expect weaker tailoring than cloud profiles.",
        },
    ),
]

OPENROUTER_ROWS: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        "openrouter",
        "anthropic/claude-sonnet-4",
        "exact",
        _price(3.0, 15.0, tier=_STRONG),
    ),
    (
        "openrouter",
        "anthropic/claude-haiku-4",
        "exact",
        _price(0.80, 4.0, tier=_EFFICIENT),
    ),
    ("openrouter", "openai/gpt-4o", "exact", _price(2.5, 10.0, tier=_STRONG)),
    ("openrouter", "openai/gpt-4.1", "exact", _price(2.0, 8.0, tier=_STRONG)),
    (
        "openrouter",
        "google/gemini-2.5-pro-preview",
        "exact",
        _price(1.25, 10.0, tier=_STRONG, deprecated=True),
    ),
    (
        "openrouter",
        "google/gemini-2.5-flash-preview",
        "exact",
        _price(0.15, 0.60, tier=_EFFICIENT, deprecated=True),
    ),
    (
        "openrouter",
        "deepseek/deepseek-chat-v3",
        "exact",
        _price(0.14, 0.28, tier=_EFFICIENT),
    ),
]

ALL_ROWS = ANTHROPIC_ROWS + OPENAI_ROWS + GOOGLE_ROWS + OLLAMA_ROWS + OPENROUTER_ROWS


def _row_id(row: tuple[str, str, str, dict[str, Any]]) -> str:
    provider, match, match_type, _ = row
    return f"{provider}:{match}:{match_type}"


class TestBuiltinDataIsValid:
    """REQ-CAT-1: the shipped data validates and has unique keys."""

    def test_catalog_is_not_empty(self) -> None:
        assert len(BUILTIN_MODEL_CAPABILITIES) > 0

    def test_every_entry_is_a_model_capability(self) -> None:
        assert all(
            isinstance(entry, ModelCapability) for entry in BUILTIN_MODEL_CAPABILITIES
        )

    def test_every_entry_survives_a_validation_round_trip(self) -> None:
        for entry in BUILTIN_MODEL_CAPABILITIES:
            assert ModelCapability.model_validate(entry.model_dump()) == entry

    def test_no_two_entries_share_a_key(self) -> None:
        assert len(_BY_KEY) == len(BUILTIN_MODEL_CAPABILITIES)

    def test_collection_is_immutable(self) -> None:
        assert isinstance(BUILTIN_MODEL_CAPABILITIES, tuple)

    def test_every_listed_row_has_a_distinct_key(self) -> None:
        keys = [row[:3] for row in ALL_ROWS]
        assert len(set(keys)) == len(keys)

    def test_data_holds_exactly_the_listed_rows(self) -> None:
        assert len(BUILTIN_MODEL_CAPABILITIES) == len(ALL_ROWS)


class TestBuiltinDataMatchesTheDesignTables:
    @pytest.mark.parametrize("row", ALL_ROWS, ids=_row_id)
    def test_entry_has_exactly_the_listed_values(
        self, row: tuple[str, str, str, dict[str, Any]]
    ) -> None:
        provider, match, match_type, expected_fields = row
        entry = _BY_KEY[(provider, match, match_type)]
        expected = dict.fromkeys(_OVERLAY_FIELDS) | expected_fields
        actual = {name: getattr(entry, name) for name in _OVERLAY_FIELDS}
        assert actual == expected


class TestBuiltinDataCoversEveryProvider:
    @pytest.mark.parametrize(
        "provider", ["anthropic", "openai", "google", "ollama", "openrouter"]
    )
    def test_provider_has_entries(self, provider: str) -> None:
        assert any(entry.provider == provider for entry in BUILTIN_MODEL_CAPABILITIES)

    def test_no_entry_belongs_to_an_unlisted_provider(self) -> None:
        providers = {entry.provider for entry in BUILTIN_MODEL_CAPABILITIES}
        assert providers == {"anthropic", "openai", "google", "ollama", "openrouter"}


class TestImportOrder:
    """The catalog data and the pricing module import each other's package."""

    @pytest.mark.parametrize(
        "module",
        [
            "mkcv.core.catalog",
            "mkcv.core.catalog.builtin_models",
            "mkcv.core.models.model_catalog",
            "mkcv.core.models.pricing",
        ],
    )
    def test_module_imports_first_in_a_fresh_interpreter(self, module: str) -> None:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
