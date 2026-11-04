"""Built-in model capability data.

Prices are USD per 1M tokens. Sources and verification dates are recorded in
``docs/changes/multi-provider-support/design.md`` (section 12). Blank values
are ``None`` and inherit from the provider-kind defaults.

Entry order matters only for ties between otherwise equal matches (later
wins); resolution orders entries by match type and length first.
"""

from typing import Any

from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.structured_output_mode import StructuredOutputMode

# Claude 5.x (and Opus 4.7/4.8) reject sampling parameters, always think
# before answering, and support schema-constrained output.
_CLAUDE_STRICT: dict[str, Any] = CapabilityOverlay(
    structured_output=StructuredOutputMode.JSON_SCHEMA,
    accepts_sampling_params=False,
    min_output_tokens=16000,
).model_dump(exclude_none=True)

# Older Claude models take temperature and use a forced tool call.
_CLAUDE_FORCED_TOOL: dict[str, Any] = CapabilityOverlay(
    structured_output=StructuredOutputMode.TOOL,
    accepts_sampling_params=True,
    min_output_tokens=0,
).model_dump(exclude_none=True)

_CLAUDE_5_WINDOW: dict[str, Any] = {
    "context_window": 1_000_000,
    "max_output_tokens": 128_000,
}

# GPT-5.x and GPT-6.x and the o-series are reasoning models.
_OPENAI_REASONING: dict[str, Any] = CapabilityOverlay(
    accepts_sampling_params=False,
    min_output_tokens=16000,
).model_dump(exclude_none=True)

_OPENAI_SAMPLING: dict[str, Any] = CapabilityOverlay(
    accepts_sampling_params=True,
    min_output_tokens=0,
).model_dump(exclude_none=True)

_GPT_6_WINDOW: dict[str, Any] = {
    "context_window": 1_050_000,
    "max_output_tokens": 128_000,
}

_GEMINI_FLASH_PROMO = "Promotional $0.75/$3.75 through 2026-12-31."

BUILTIN_MODEL_CAPABILITIES: tuple[ModelCapability, ...] = (
    # ------------------------------------------------------------------
    # Anthropic: family rules (prefix)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="anthropic",
        match="claude-fable-",
        match_type="prefix",
        tier=ModelTier.FRONTIER,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-mythos-",
        match_type="prefix",
        tier=ModelTier.FRONTIER,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-5",
        match_type="prefix",
        tier=ModelTier.FRONTIER,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-5",
        match_type="prefix",
        tier=ModelTier.STRONG,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-5",
        match_type="prefix",
        tier=ModelTier.EFFICIENT,
        **_CLAUDE_STRICT,
    ),
    # These two are longer than "claude-opus-4-" and therefore overlay it.
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-7",
        match_type="prefix",
        tier=ModelTier.STRONG,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-8",
        match_type="prefix",
        tier=ModelTier.STRONG,
        **_CLAUDE_STRICT,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-",
        match_type="prefix",
        tier=ModelTier.STRONG,
        **_CLAUDE_FORCED_TOOL,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-4-",
        match_type="prefix",
        tier=ModelTier.STRONG,
        **_CLAUDE_FORCED_TOOL,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-4-",
        match_type="prefix",
        tier=ModelTier.EFFICIENT,
        **_CLAUDE_FORCED_TOOL,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-3",
        match_type="prefix",
        tier=ModelTier.EFFICIENT,
        deprecated=True,
        notes="Claude 3.x models are retired or retiring; move to a 5.x model.",
        **_CLAUDE_FORCED_TOOL,
    ),
    # ------------------------------------------------------------------
    # Anthropic: prices and limits (exact)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="anthropic",
        match="claude-fable-5-1",
        input_price_per_mtok=10.00,
        output_price_per_mtok=50.00,
        notes="Most capable Claude model; priced above Opus.",
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-5-5",
        input_price_per_mtok=4.00,
        output_price_per_mtok=20.00,
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-5",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-5-5",
        input_price_per_mtok=2.00,
        output_price_per_mtok=10.00,
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-5",
        input_price_per_mtok=2.00,
        output_price_per_mtok=10.00,
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-5-5",
        input_price_per_mtok=0.10,
        output_price_per_mtok=0.50,
        notes="Prompts over 100K tokens bill at $0.50/$2.50.",
        **_CLAUDE_5_WINDOW,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-8",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-7",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-6",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-4-6",
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-4-5",
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-4-5-20251001",
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-opus-4-20250514",
        input_price_per_mtok=15.00,
        output_price_per_mtok=75.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-sonnet-4-20250514",
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
    ),
    ModelCapability(
        provider="anthropic",
        match="claude-haiku-4-20250414",
        input_price_per_mtok=0.80,
        output_price_per_mtok=4.00,
    ),
    # ------------------------------------------------------------------
    # OpenAI: family rules (prefix)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="openai",
        match="gpt-6",
        match_type="prefix",
        notes="GPT-6 family: reasoning models.",
        **_OPENAI_REASONING,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5",
        match_type="prefix",
        notes="GPT-5 family: reasoning models.",
        **_OPENAI_REASONING,
    ),
    ModelCapability(
        provider="openai", match="o1", match_type="prefix", **_OPENAI_REASONING
    ),
    ModelCapability(
        provider="openai", match="o3", match_type="prefix", **_OPENAI_REASONING
    ),
    ModelCapability(
        provider="openai", match="o4", match_type="prefix", **_OPENAI_REASONING
    ),
    ModelCapability(
        provider="openai", match="gpt-4.1", match_type="prefix", **_OPENAI_SAMPLING
    ),
    ModelCapability(
        provider="openai", match="gpt-4o", match_type="prefix", **_OPENAI_SAMPLING
    ),
    # ------------------------------------------------------------------
    # OpenAI: tiers, prices, and limits (exact)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="openai",
        match="gpt-6-astra",
        tier=ModelTier.FRONTIER,
        input_price_per_mtok=10.00,
        output_price_per_mtok=50.00,
        **_GPT_6_WINDOW,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-6.1-sol",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.00,
        output_price_per_mtok=10.00,
        **_GPT_6_WINDOW,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-6.1-terra",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
        **_GPT_6_WINDOW,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-6-luna",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.10,
        output_price_per_mtok=0.50,
        **_GPT_6_WINDOW,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.6-sol",
        tier=ModelTier.STRONG,
        input_price_per_mtok=4.00,
        output_price_per_mtok=20.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.6-terra",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=2.00,
        output_price_per_mtok=12.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.6-luna",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.20,
        output_price_per_mtok=1.20,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.5",
        tier=ModelTier.STRONG,
        input_price_per_mtok=5.00,
        output_price_per_mtok=30.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.4",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.50,
        output_price_per_mtok=15.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.4-mini",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.75,
        output_price_per_mtok=4.50,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5.4-nano",
        tier=ModelTier.MINIMAL,
        input_price_per_mtok=0.20,
        output_price_per_mtok=1.25,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5",
        tier=ModelTier.STRONG,
        input_price_per_mtok=1.25,
        output_price_per_mtok=10.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5-mini",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.25,
        output_price_per_mtok=2.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-5-nano",
        tier=ModelTier.MINIMAL,
        input_price_per_mtok=0.05,
        output_price_per_mtok=0.40,
    ),
    # GPT-4.x prices are carried unchanged from the pre-catalog pricing table.
    ModelCapability(
        provider="openai",
        match="gpt-4.1",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.00,
        output_price_per_mtok=8.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-4.1-mini",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.40,
        output_price_per_mtok=1.60,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-4.1-nano",
        tier=ModelTier.MINIMAL,
        input_price_per_mtok=0.10,
        output_price_per_mtok=0.40,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-4o",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.50,
        output_price_per_mtok=10.00,
    ),
    ModelCapability(
        provider="openai",
        match="gpt-4o-mini",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.15,
        output_price_per_mtok=0.60,
    ),
    # ------------------------------------------------------------------
    # Google Gemini (post-promotion standard rates)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="google",
        match="gemini-4-argon",
        tier=ModelTier.FRONTIER,
        context_window=1_000_000,
        input_price_per_mtok=4.00,
        output_price_per_mtok=20.00,
        notes="Promotional $2.00/$10.00 through 2026-11-30.",
    ),
    ModelCapability(
        provider="google",
        match="gemini-3.8-flash",
        tier=ModelTier.STRONG,
        input_price_per_mtok=1.50,
        output_price_per_mtok=7.50,
        notes=_GEMINI_FLASH_PROMO,
    ),
    ModelCapability(
        provider="google",
        match="gemini-3.6-flash",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=1.50,
        output_price_per_mtok=7.50,
        notes=_GEMINI_FLASH_PROMO,
    ),
    ModelCapability(
        provider="google",
        match="gemini-3.5-flash-lite",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.30,
        output_price_per_mtok=2.50,
    ),
    ModelCapability(
        provider="google",
        match="gemini-3.1-flash-lite",
        tier=ModelTier.MINIMAL,
        input_price_per_mtok=0.25,
        output_price_per_mtok=1.50,
    ),
    ModelCapability(
        provider="google",
        match="gemini-3.1-pro-preview",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.00,
        output_price_per_mtok=12.00,
        notes="Preview model; prompts over 200K tokens bill at $4.00/$18.00.",
    ),
    ModelCapability(
        provider="google",
        match="gemini-2.5-pro",
        deprecated=True,
        notes="Deprecated; from 2026-12-01 requests route to gemini-3.8-flash.",
    ),
    ModelCapability(
        provider="google",
        match="gemini-2.5-flash",
        deprecated=True,
        notes="Deprecated; from 2026-12-01 requests route to gemini-3.5-flash-lite.",
    ),
    ModelCapability(
        provider="google",
        match="gemini-2.5-flash-lite",
        notes="Limited to existing users; use gemini-3.5-flash-lite.",
    ),
    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------
    ModelCapability(
        provider="ollama",
        match="llama3.1",
        match_type="prefix",
        tier=ModelTier.MINIMAL,
        notes="Small local model; expect weaker tailoring than cloud profiles.",
    ),
    # ------------------------------------------------------------------
    # OpenRouter (pass-through rates carried from the pre-catalog table)
    # ------------------------------------------------------------------
    ModelCapability(
        provider="openrouter",
        match="anthropic/claude-sonnet-4",
        tier=ModelTier.STRONG,
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
    ),
    ModelCapability(
        provider="openrouter",
        match="anthropic/claude-haiku-4",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.80,
        output_price_per_mtok=4.00,
    ),
    ModelCapability(
        provider="openrouter",
        match="openai/gpt-4o",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.50,
        output_price_per_mtok=10.00,
    ),
    ModelCapability(
        provider="openrouter",
        match="openai/gpt-4.1",
        tier=ModelTier.STRONG,
        input_price_per_mtok=2.00,
        output_price_per_mtok=8.00,
    ),
    ModelCapability(
        provider="openrouter",
        match="google/gemini-2.5-pro-preview",
        tier=ModelTier.STRONG,
        input_price_per_mtok=1.25,
        output_price_per_mtok=10.00,
        deprecated=True,
    ),
    ModelCapability(
        provider="openrouter",
        match="google/gemini-2.5-flash-preview",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.15,
        output_price_per_mtok=0.60,
        deprecated=True,
    ),
    ModelCapability(
        provider="openrouter",
        match="deepseek/deepseek-chat-v3",
        tier=ModelTier.EFFICIENT,
        input_price_per_mtok=0.14,
        output_price_per_mtok=0.28,
    ),
)
