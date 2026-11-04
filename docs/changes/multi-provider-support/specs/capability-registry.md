# Spec: Model Capability Catalog and Pricing

Design references: §3 (models), §4 (catalog), §4.4 (pricing).

## REQ-CAT-1: Built-in data validates

- **When** `mkcv.core.catalog.builtin_models` is imported, **then** every entry is a valid `ModelCapability`, and no two entries share the same `(provider, match, match_type)` key.
- Every entry in design §4.1 MUST be present with the listed values (one parametrized test per provider table, checking `tier`, `accepts_sampling_params`, `min_output_tokens`, and prices where listed).

## REQ-CAT-2: Overlay order

- **Given** the built-in catalog, **when** `lookup("anthropic", "claude-opus-5-5")` is called, **then** the overlay has `tier == "frontier"`, `structured_output == "json_schema"`, `accepts_sampling_params is False`, `min_output_tokens == 16000`, `input_price_per_mtok == 4.0`, `output_price_per_mtok == 20.0`.
- **When** `lookup("anthropic", "claude-opus-4-7")`, **then** `structured_output == "json_schema"` and `accepts_sampling_params is False` (the longer prefix `claude-opus-4-7` overlays `claude-opus-4-`).
- **When** `lookup("anthropic", "claude-opus-4-6")`, **then** `structured_output == "tool"`, `accepts_sampling_params is True`, `min_output_tokens == 0`, prices 5.0/25.0.
- **When** `lookup("anthropic", "claude-sonnet-5-5-20261001")` (a dated variant), **then** the prefix `claude-sonnet-5` applies (`tier == "strong"`, strict rules) and prices are `None`.

## REQ-CAT-3: Unknown models

- **When** `lookup("openai", "gpt-7-nova")` is called, **then** it returns `None`.
- **When** `resolve("openai", "gpt-7-nova", defaults=KIND_DEFAULTS[OPENAI])` is called, **then** `known is False`, `structured_output == "json_schema"`, `accepts_sampling_params is False`, `token_param == "max_completion_tokens"`, `min_output_tokens == 16000`, and prices are `None`.
- **When** resolving `("groq", "some-model")` with `KIND_DEFAULTS[OPENAI_COMPATIBLE]`, **then** `known is False`, `structured_output == "json_schema"`, `allow_structured_fallback is True`, `accepts_sampling_params is True`, `token_param == "max_tokens"`, `min_output_tokens == 0`.
- **When** `resolve` is called with defaults missing `structured_output`, **then** `ValueError` is raised.

## REQ-CAT-4: Canonical and vendor fallback

- **Given** a user provider `my-proxy` of kind `openai`, **when** `lookup("my-proxy", "gpt-6.1-sol", canonical_provider="openai")` is called, **then** the overlay equals `lookup("openai", "gpt-6.1-sol")`.
- **When** `lookup("openrouter", "openai/gpt-6.1-sol")` is called, **then** the overlay has `tier == "strong"` and `context_window == 1050000`, and its prices, `structured_output`, `accepts_sampling_params`, `token_param`, and `min_output_tokens` are `None`.
- **When** `lookup("openrouter", "openai/gpt-4o")` is called, **then** the openrouter entry wins (prices 2.5/10.0, `tier == "strong"`).
- **When** `lookup("openrouter", "mistral/large")` is called, **then** it returns `None`.

## REQ-CAT-5: `output_limit`

- **Given** a resolved model with `min_output_tokens=16000` and `max_output_tokens=None`, **when** `output_limit(4096)`, **then** 16000; `output_limit(20000)` → 20000.
- **Given** `min_output_tokens=16000` and `max_output_tokens=8000`, **then** `output_limit(4096)` → 8000.
- **Given** `min_output_tokens=0`, **then** `output_limit(4096)` → 4096.

## REQ-CAT-6: User overrides from config

- **Given**
  ```toml
  [[default.model_catalog]]
  provider = "openai"
  match = "gpt-6.1-sol"
  input_price_per_mtok = 1.8
  ```
  **when** `load_model_catalog(config)` runs, **then** `lookup("openai", "gpt-6.1-sol")` has `input_price_per_mtok == 1.8`, `output_price_per_mtok == 10.0`, and `tier == "strong"` (field-level overlay of the same key).
- **Given** an entry for a new key (`provider = "groq"`, `match = "llama-3.3-70b-versatile"`, `tier = "efficient"`), **then** `lookup("groq", "llama-3.3-70b-versatile").tier == "efficient"`.
- **Given** a global config with an entry `{provider="groq", match="m", tier="minimal"}` and a workspace `mkcv.toml` with `{provider="groq", match="m", tier="strong"}`, **when** both are loaded, **then** `lookup("groq", "m").tier == "strong"`.
- **Given** `[[default.model_catalog]]` with `tier = "great"`, **then** `ConfigurationError` mentions `Invalid [[default.model_catalog]] entry #1`.
- **Given** `model_catalog = "x"` (not a list), **then** `ConfigurationError` mentions `must be an array of tables`.
- **Given** an entry with an unknown field `colour = "red"`, **then** `ConfigurationError` is raised (`extra="forbid"`).

## REQ-CAT-7: Pricing compatibility

- `MODEL_PRICING` MUST contain every key of the pre-change table with identical per-1K values (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-haiku-4-5-20251001`, `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, `claude-haiku-4-20250414`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `anthropic/claude-sonnet-4`, `anthropic/claude-haiku-4`, `openai/gpt-4o`, `openai/gpt-4.1`, `google/gemini-2.5-pro-preview`, `google/gemini-2.5-flash-preview`, `deepseek/deepseek-chat-v3`).
- The existing `tests/test_core/test_models/test_pricing.py` MUST pass unchanged.
- **Given** usage 1,000,000 in / 1,000,000 out, **when** `calculate_cost("gpt-6.1-sol", usage)`, **then** 12.0; `calculate_cost("gemini-4-argon", usage)` → 24.0.
- **When** `calculate_cost("llama3.1:8b", usage, provider="ollama")`, **then** 0.0 (the catalog entry has no price).
- **When** `calculate_cost("unknown-model", usage)`, **then** 0.0.
- **Given** a catalog with an override price for `gpt-6.1-sol` of 1.8 in, **when** `calculate_cost("gpt-6.1-sol", usage, catalog)`, **then** the override price is used.

## REQ-CAT-8: Services price with the injected catalog

- **Given** a `PipelineService` constructed with a catalog whose `claude-sonnet-5-5` input price is 100.0, **when** a stage runs with a stub reporting 1,000,000 input tokens on `claude-sonnet-5-5`, **then** that stage's `StageMetadata.cost_usd` reflects the override (≥ 100.0).
- **Given** no catalog argument, **then** costs equal the built-in prices (existing pipeline tests pass unchanged).

## REQ-CAT-9: `uses_strict_request_rules` compatibility

For each model below, `uses_strict_request_rules(model)` MUST return the listed value (the pre-change behaviour):

| Model | Result |
|---|---|
| `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1`, `claude-mythos-5-1`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-sonnet-5` | `True` |
| `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-sonnet-4-20250514` | `False` |
