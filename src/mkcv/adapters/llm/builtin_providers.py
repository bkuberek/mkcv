"""Built-in provider data: kind defaults and the providers mkcv ships with.

``KIND_DEFAULTS`` are deliberately conservative. An unknown Anthropic, OpenAI,
or Google model is most likely a new model, which rejects sampling parameters
and thinks before answering, so those kinds omit ``temperature`` and keep a
large output floor. OpenAI-compatible endpoints keep sampling and may degrade
their structured-output mode.
"""

from mkcv.adapters.llm.provider_spec import ProviderSpec
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam

_REASONING_OUTPUT_FLOOR = 16000

KIND_DEFAULTS: dict[ProviderKind, CapabilityOverlay] = {
    ProviderKind.ANTHROPIC: CapabilityOverlay(
        structured_output=StructuredOutputMode.JSON_SCHEMA,
        allow_structured_fallback=False,
        accepts_sampling_params=False,
        token_param=TokenParam.MAX_TOKENS,
        min_output_tokens=_REASONING_OUTPUT_FLOOR,
    ),
    ProviderKind.OPENAI: CapabilityOverlay(
        structured_output=StructuredOutputMode.JSON_SCHEMA,
        allow_structured_fallback=False,
        accepts_sampling_params=False,
        token_param=TokenParam.MAX_COMPLETION_TOKENS,
        min_output_tokens=_REASONING_OUTPUT_FLOOR,
    ),
    ProviderKind.GOOGLE: CapabilityOverlay(
        structured_output=StructuredOutputMode.JSON_SCHEMA,
        allow_structured_fallback=False,
        accepts_sampling_params=False,
        token_param=TokenParam.MAX_TOKENS,
        min_output_tokens=_REASONING_OUTPUT_FLOOR,
    ),
    ProviderKind.OPENAI_COMPATIBLE: CapabilityOverlay(
        structured_output=StructuredOutputMode.JSON_SCHEMA,
        allow_structured_fallback=True,
        accepts_sampling_params=True,
        token_param=TokenParam.MAX_TOKENS,
        min_output_tokens=0,
    ),
    ProviderKind.STUB: CapabilityOverlay(
        structured_output=StructuredOutputMode.JSON_SCHEMA,
        allow_structured_fallback=False,
        accepts_sampling_params=True,
        token_param=TokenParam.MAX_TOKENS,
        min_output_tokens=0,
    ),
}

# Provider whose catalog entries describe the same models for a kind, so a
# custom provider speaking a native protocol inherits its model data.
CANONICAL_PROVIDER: dict[ProviderKind, str | None] = {
    ProviderKind.ANTHROPIC: "anthropic",
    ProviderKind.OPENAI: "openai",
    ProviderKind.GOOGLE: "google",
    ProviderKind.OPENAI_COMPATIBLE: None,
    ProviderKind.STUB: None,
}

BUILTIN_PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        name="anthropic",
        kind=ProviderKind.ANTHROPIC,
        api_key_env=("ANTHROPIC_API_KEY",),
        builtin=True,
    ),
    "openai": ProviderSpec(
        name="openai",
        kind=ProviderKind.OPENAI,
        api_key_env=("OPENAI_API_KEY",),
        builtin=True,
    ),
    "google": ProviderSpec(
        name="google",
        kind=ProviderKind.GOOGLE,
        api_key_env=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        builtin=True,
    ),
    "openrouter": ProviderSpec(
        name="openrouter",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="https://openrouter.ai/api/v1",
        api_key_env=("OPENROUTER_API_KEY",),
        builtin=True,
    ),
    # Ollama's JSON mode preserves the pre-registry behaviour; its zero
    # prices make local runs show as free.
    "ollama": ProviderSpec(
        name="ollama",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://localhost:11434/v1",
        requires_api_key=False,
        defaults=CapabilityOverlay(
            structured_output=StructuredOutputMode.JSON_OBJECT,
            input_price_per_mtok=0.0,
            output_price_per_mtok=0.0,
        ),
        builtin=True,
    ),
    "stub": ProviderSpec(
        name="stub",
        kind=ProviderKind.STUB,
        requires_api_key=False,
        builtin=True,
    ),
}
