# Design: Multi-Provider Support

This document settles every design decision for the change. Implementers follow it together with `specs/*.md` (behaviour) and `tasks.md` (order, files, checks). Where this document gives a name, a field, a constant, or a message, use it exactly.

## 1. Decisions at a glance

| # | Decision | Why |
|---|---|---|
| D1 | Native adapters for Anthropic (exists), OpenAI, and Google Gemini | Reliable schema-constrained output matters for a five-stage pipeline where every stage parses the previous one. (Brief decision 1.) |
| D2 | One `OpenAICompatibleAdapter` configured by `base_url` + API-key env var; `ollama` and `openrouter` are built-in instances of it | One code path for every Chat Completions endpoint. (Brief decision 2.) |
| D3 | `OpenAIAdapter` is a subclass of `OpenAICompatibleAdapter` with structured-output degradation disabled and refusal handling | OpenAI and compatible endpoints share request shaping; the native adapter differs only in strictness. |
| D4 | OpenAI uses the Chat Completions API, not Responses | Every current OpenAI model supports Chat Completions with structured outputs (§12). mkcv uses no tools, and one request shape serves OpenAI and every compatible endpoint. The Responses API is a follow-up. |
| D5 | Provider registry: `ProviderSpec` data plus a builder per provider kind, in `adapters/llm/` | Replaces the `if/elif` chain. (Brief decision 3.) |
| D6 | Model capability catalog: Pydantic entries with optional fields, overlaid in a fixed order (§4.3). Built-in data is a Python data module in `core/catalog/`; user entries come from `[[default.model_catalog]]` | Data, not code branches. Core needs the catalog for `calculate_cost` without I/O; a typed Python data module is validated at import and needs no package-data config. Provider names in core are data, the same as the pricing table that already lives there. (Brief decision 4.) |
| D7 | Prices in USD per million tokens in the catalog; `MODEL_PRICING` (per 1K) is derived for compatibility | Providers publish per-1M prices; the old dict and `calculate_cost` keep their results. |
| D8 | Two orthogonal axes: **preset** (content density) and **model profile** (which model runs each stage). Presets keep their names; a preset only says whether to prefer the economy variant of a profile, and the legacy `budget` preset pins the `ollama` provider | Today a preset mixes density and models, which is why per-stage config is ignored. Separating them keeps every preset name working. |
| D9 | Profile names: `anthropic`, `anthropic-economy`, `openai`, `openai-economy`, `google`, `google-economy`, `local`. No new profile is called `budget` | `budget` is already a legacy preset (concise + Ollama). Reusing it for a cloud profile would change its meaning. |
| D10 | One `StageResolver` in `adapters/llm/stage_resolver.py` owns stage precedence; the only default provider constant is `DEFAULT_PROVIDER = "anthropic"` there | Removes the scattered `"anthropic"`/`"claude-sonnet-5-5"` fallbacks. (Brief decision 3.) |
| D11 | Per-stage config keys override the model profile; CLI flags override both | Users stay free to tweak per stage. Fixes the bug where `generate` ignored `mkcv.toml` stage models. |
| D12 | New CLI flag `--model-profile`; config key `pipeline.model_profile`; config key `pipeline.provider` | A flag name that cannot be confused with listing models. |
| D13 | `mkcv models` is a new top-level command; warnings print from a small CLI helper module; advice is computed by a core `ModelAdvisor` service | CLI keeps no business logic. |
| D14 | Warnings never fire for a stage whose model came from the active profile, except `deprecated_model` and `missing_api_key` | Our own recommendations (including economy profiles) must not nag. |
| D15 | Eval harness lives in a top-level `evals/` package, run with `uv run python -m evals` | It costs money, needs keys, and is a maintainer tool, not a user feature. The wheel only packages `src/mkcv`, so `evals/` never ships. It imports mkcv as a library and drives the real `PipelineService`. |
| D16 | Stage-isolated evals reuse the pipeline's `from_stage` resume plus a stop-after-stage callback, with committed reference artifacts for upstream stages | Measures one stage per model without changing pipeline code; references make runs reproducible. |
| D17 | Recommendations are applied by a human from the report; the report prints suggested profile changes | Keeps a reviewer between a noisy LLM-judged run and the defaults users get. |
| D18 | `google-genai>=2.34.0` is a core dependency, imported lazily | Same status as `anthropic` and `openai`; lazy import keeps startup unchanged. |
| D19 | New `ConfigurationError(MkcvError)` with `exit_code=3` | Exit code 3 is unused (`rg -n "exit_code=" src/mkcv/core/exceptions/`). |
| D20 | Unknown models resolve with the provider kind's conservative defaults; adapters also adapt a request once when a 400 names `temperature` or `max_tokens` | Code must not depend on unverified facts (§12.4). |

## 2. Architecture

### 2.1 Component map

```
cli/
  commands/generate.py        --model-profile flag, prints warnings (via cli/model_warnings.py)
  commands/cover_letter.py    --model-profile flag, prints warnings
  commands/models.py          NEW  mkcv models
  model_warnings.py           NEW  print_model_warnings(report, console)
        │
        ▼
adapters/factory.py           create_* functions; delegate to registry + resolver
adapters/llm/
  provider_spec.py            NEW  ProviderSpec (Pydantic)
  builtin_providers.py        NEW  BUILTIN_PROVIDERS data + KIND_DEFAULTS + CANONICAL_PROVIDER
  model_resolver.py           NEW  ModelResolver type alias + builtin_resolver(kind) factory function
  provider_registry.py        NEW  ProviderRegistry (specs, keys, adapter builders)
  stage_resolver.py           NEW  StageResolver, DEFAULT_PROVIDER
  resolution_request.py       NEW  ResolutionRequest (Pydantic)
  resolved_stages.py          NEW  ResolvedStages (Pydantic)
  model_catalog_loader.py     NEW  load_model_catalog(config) -> ModelCatalog
  request_adaptation.py       NEW  rejected-parameter detection helpers
  strict_schema.py            NEW  to_strict_json_schema(), drop_nulls_for_defaulted_fields()
  openai_compatible.py        NEW  OpenAICompatibleAdapter (fallback chain, repair)
  openai.py                   REWRITE  OpenAIAdapter(OpenAICompatibleAdapter)
  google.py                   NEW  GoogleGeminiAdapter
  anthropic.py                MODIFY  capability-driven request shaping
  ollama.py                   DELETE (ollama = built-in openai-compatible provider)
  retry.py, stub.py, _utils.py  unchanged
        │ implements LLMPort
        ▼
core/
  ports/llm.py                unchanged
  models/                     NEW  provider_kind, structured_output_mode, model_tier,
                                   token_param, capability_overlay, model_capability,
                                   resolved_model, model_catalog, stage_key,
                                   stage_requirement, model_profile, stage_assignment,
                                   model_warning_kind, model_warning, stage_advice,
                                   model_report
                              MODIFY profile_preset.py, pricing.py
  catalog/                    NEW  builtin_models.py, builtin_model_profiles.py,
                                   stage_requirements.py (data only)
  services/model_advisor.py   NEW  ModelAdvisor
  services/pipeline.py, cover_letter.py   MODIFY  accept optional catalog for cost
  services/validation.py      MODIFY  model bound at construction
  exceptions/configuration.py NEW  ConfigurationError
config/settings.toml          MODIFY  drop per-stage provider/model; add validate section
evals/                        NEW  offline eval harness (not packaged)
```

### 2.2 Dependency direction

- `core/models` and `core/catalog` import only stdlib, Pydantic, and other `core` modules.
- `core/services/model_advisor.py` depends on `core/models` and `core/catalog`; it never imports adapters or config.
- `adapters/llm/*` may import `core`. `stage_resolver.py`, `provider_registry.py`, and `model_catalog_loader.py` read the Dynaconf `Configuration` (typed under `TYPE_CHECKING`, as `factory.py` does today).
- CLI imports factory functions and core models for display only.
- `evals/` imports `mkcv` (factory, core, adapters). Nothing in `src/` imports `evals`.

### 2.3 One class per file

Every class named in this document gets its own module named after it in `snake_case`. Data modules (`core/catalog/*.py`, `adapters/llm/builtin_providers.py`) hold constants only. Module-level helper functions are allowed where noted.

## 3. Core domain models

All are Pydantic v2 `BaseModel` (frozen where stated) or `StrEnum`. Field order below is the declaration order.

### 3.1 Enums

| Module | Class | Members (`value`) |
|---|---|---|
| `core/models/provider_kind.py` | `ProviderKind(StrEnum)` | `ANTHROPIC="anthropic"`, `OPENAI="openai"`, `GOOGLE="google"`, `OPENAI_COMPATIBLE="openai-compatible"`, `STUB="stub"` |
| `core/models/structured_output_mode.py` | `StructuredOutputMode(StrEnum)` | `JSON_SCHEMA="json_schema"`, `TOOL="tool"`, `JSON_OBJECT="json_object"`, `PROMPT="prompt"` |
| `core/models/model_tier.py` | `ModelTier(StrEnum)` | `MINIMAL="minimal"`, `EFFICIENT="efficient"`, `STRONG="strong"`, `FRONTIER="frontier"`; method `rank(self) -> int` returns 0, 1, 2, 3 in that order |
| `core/models/token_param.py` | `TokenParam(StrEnum)` | `MAX_TOKENS="max_tokens"`, `MAX_COMPLETION_TOKENS="max_completion_tokens"` |
| `core/models/stage_key.py` | `StageKey(StrEnum)` | `ANALYZE="analyze"`, `SELECT="select"`, `TAILOR="tailor"`, `STRUCTURE="structure"`, `REVIEW="review"`, `COVER_LETTER_GENERATE="cover_letter.generate"`, `COVER_LETTER_REVIEW="cover_letter.review"`, `KB="kb"`, `VALIDATE="validate"` |
| `core/models/model_warning_kind.py` | `ModelWarningKind(StrEnum)` | `UNKNOWN_MODEL="unknown_model"`, `TIER_UNKNOWN="tier_unknown"`, `BELOW_RECOMMENDED_TIER="below_recommended_tier"`, `DEPRECATED_MODEL="deprecated_model"`, `MISSING_API_KEY="missing_api_key"` |

`stage_key.py` also defines module constants `PIPELINE_STAGES: tuple[StageKey, ...] = (ANALYZE, SELECT, TAILOR, STRUCTURE, REVIEW)` and `COVER_LETTER_STAGES = (COVER_LETTER_GENERATE, COVER_LETTER_REVIEW)`, and `PIPELINE_STAGE_NUMBERS: dict[StageKey, int]` mapping the five pipeline stages to 1..5.

`StructuredOutputMode.TOOL` is meaningful only to the Anthropic adapter (forced tool call). Other adapters treat `TOOL` as `JSON_SCHEMA`.

### 3.2 `CapabilityOverlay` (`core/models/capability_overlay.py`)

A partial set of capabilities. Every field is optional; `None` means "inherit".

| Field | Type | Meaning |
|---|---|---|
| `structured_output` | `StructuredOutputMode \| None` | First structured-output mode to try |
| `allow_structured_fallback` | `bool \| None` | Whether the adapter may degrade to a weaker mode after a rejection |
| `accepts_sampling_params` | `bool \| None` | Whether `temperature` may be sent |
| `token_param` | `TokenParam \| None` | Name of the output-limit parameter (OpenAI-family only) |
| `min_output_tokens` | `int \| None`, `ge=0` | Floor applied to the requested output limit |
| `max_output_tokens` | `int \| None`, `gt=0` | Ceiling applied after the floor |
| `context_window` | `int \| None`, `gt=0` | Informational |
| `input_price_per_mtok` | `float \| None`, `ge=0` | USD per 1M input tokens |
| `output_price_per_mtok` | `float \| None`, `ge=0` | USD per 1M output tokens |
| `tier` | `ModelTier \| None` | Quality tier |
| `deprecated` | `bool \| None` | Provider has deprecated the model |
| `notes` | `str \| None` | Shown with warnings and in `mkcv models --catalog` |

`model_config = ConfigDict(frozen=True, extra="forbid")`. Method `overlay(self, other: CapabilityOverlay) -> CapabilityOverlay` returns a copy where every non-`None` field of `other` replaces the field of `self`.

### 3.3 `ModelCapability(CapabilityOverlay)` (`core/models/model_capability.py`)

A catalog entry. Adds:

| Field | Type | Meaning |
|---|---|---|
| `provider` | `str`, `min_length=1` | Provider name the entry applies to (`anthropic`, `openai`, `google`, `ollama`, `openrouter`, or a user provider) |
| `match` | `str`, `min_length=1` | Model ID or prefix |
| `match_type` | `Literal["exact", "prefix"] = "exact"` | |
| `display_name` | `str \| None = None` | |

Method `matches(self, model: str) -> bool`: exact → `model == match`; prefix → `model.startswith(match)`. Property `key -> tuple[str, str, str]` = `(provider, match, match_type)`.

### 3.4 `ResolvedModel` (`core/models/resolved_model.py`)

Frozen. What an adapter uses for one request.

| Field | Type |
|---|---|
| `provider` | `str` |
| `model` | `str` |
| `known` | `bool` (at least one catalog entry matched) |
| `structured_output` | `StructuredOutputMode` |
| `allow_structured_fallback` | `bool` |
| `accepts_sampling_params` | `bool` |
| `token_param` | `TokenParam` |
| `min_output_tokens` | `int` |
| `max_output_tokens` | `int \| None` |
| `context_window` | `int \| None` |
| `input_price_per_mtok` | `float \| None` |
| `output_price_per_mtok` | `float \| None` |
| `tier` | `ModelTier \| None` |
| `deprecated` | `bool` |
| `notes` | `str \| None` |

Method `output_limit(self, requested: int) -> int`: `limit = max(requested, self.min_output_tokens)`; if `max_output_tokens` is set, `limit = min(limit, max_output_tokens)`; return `limit`.

### 3.5 `ModelCatalog` (`core/models/model_catalog.py`)

Plain class (holds behaviour), immutable after construction.

```python
class ModelCatalog:
    def __init__(self, entries: Sequence[ModelCapability]) -> None: ...
    @classmethod
    def builtin(cls) -> ModelCatalog: ...          # cached; BUILTIN_MODEL_CAPABILITIES
    def with_overrides(self, overrides: Sequence[ModelCapability]) -> ModelCatalog: ...
    @property
    def entries(self) -> tuple[ModelCapability, ...]: ...
    def lookup(self, provider: str, model: str, *, canonical_provider: str | None = None) -> CapabilityOverlay | None: ...
    def resolve(self, provider: str, model: str, *, defaults: CapabilityOverlay, canonical_provider: str | None = None) -> ResolvedModel: ...
    def price_for(self, model: str, *, provider: str | None = None) -> tuple[float, float] | None: ...
    def providers_for_model(self, model: str) -> tuple[str, ...]: ...
```

Algorithms are specified in §4.3.

### 3.6 Stage and profile models

`StageRequirement` (`core/models/stage_requirement.py`, frozen): `stage: StageKey`, `config_path: str` (dotted Dynaconf path of the section), `default_temperature: float`, `min_tier: ModelTier`, `est_input_tokens: int`, `est_output_tokens: int`, `label: str`.

`ModelProfile` (`core/models/model_profile.py`, frozen): `name: str`, `description: str`, `provider: str`, `economy: bool = False`, `extends: str | None = None`, `evidence: Literal["provisional", "eval"] = "provisional"`, `eval_run: str | None = None`, `stages: dict[StageKey, str]` (stage → model ID). An economy profile lists only the five pipeline stages and sets `extends` to its base profile.

`StageAssignment` (`core/models/stage_assignment.py`, frozen): `stage: StageKey`, `provider: str`, `provider_kind: ProviderKind`, `model: str`, `temperature: float`, `source: Literal["cli", "config", "profile"]`. Method `to_stage_config(self) -> StageConfig`.

`ModelWarning` (`core/models/model_warning.py`, frozen): `kind: ModelWarningKind`, `stage: StageKey | None`, `provider: str`, `model: str | None`, `message: str`.

`StageAdvice` (`core/models/stage_advice.py`, frozen): `assignment: StageAssignment`, `recommended_model: str | None`, `recommended_provider: str | None`, `tier: ModelTier | None`, `min_tier: ModelTier`, `known: bool`, `estimated_cost_usd: float | None`, `warnings: list[ModelWarning]`.

`ModelReport` (`core/models/model_report.py`, frozen): `profile_name: str | None`, `profile_evidence: Literal["provisional", "eval"] | None`, `profile_source: Literal["cli", "config", "default", "preset"]`, `preset_name: str`, `stages: list[StageAdvice]`, `warnings: list[ModelWarning]` (all warnings, including provider-level), `estimated_total_usd: float | None`, `estimate_is_partial: bool`.

### 3.7 `ConfigurationError` (`core/exceptions/configuration.py`)

```python
class ConfigurationError(MkcvError):
    """Invalid or incomplete mkcv configuration."""
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)
```

Export from `core/exceptions/__init__.py` and add to `__all__`. Add `3 | Configuration error` to the exit-code table in `docs/specs/cli-interface.md`.

## 4. Capability catalog

### 4.1 Built-in data (`core/catalog/builtin_models.py`)

`BUILTIN_MODEL_CAPABILITIES: tuple[ModelCapability, ...]`. Every row below becomes one entry. Blank cells are `None`. Prices are USD per 1M tokens. `S` = `accepts_sampling_params`, `SO` = `structured_output`, `min` = `min_output_tokens`, `ctx` = `context_window`, `maxo` = `max_output_tokens`.

**Anthropic** (`provider="anthropic"`). Source: claude-api skill model table (cached 2026-10-06) and the existing `pricing.py` table (verified in the `claude-5-5-models` feature).

| match | type | tier | SO | S | min | ctx | maxo | in | out | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| `claude-fable-` | prefix | frontier | json_schema | false | 16000 | | | | | |
| `claude-mythos-` | prefix | frontier | json_schema | false | 16000 | | | | | |
| `claude-opus-5` | prefix | frontier | json_schema | false | 16000 | | | | | |
| `claude-sonnet-5` | prefix | strong | json_schema | false | 16000 | | | | | |
| `claude-haiku-5` | prefix | efficient | json_schema | false | 16000 | | | | | |
| `claude-opus-4-7` | prefix | strong | json_schema | false | 16000 | | | | | |
| `claude-opus-4-8` | prefix | strong | json_schema | false | 16000 | | | | | |
| `claude-opus-4-` | prefix | strong | tool | true | 0 | | | | | |
| `claude-sonnet-4-` | prefix | strong | tool | true | 0 | | | | | |
| `claude-haiku-4-` | prefix | efficient | tool | true | 0 | | | | | |
| `claude-3` | prefix | efficient | tool | true | 0 | | | | | deprecated=true, "Claude 3.x models are retired or retiring; move to a 5.x model." |
| `claude-fable-5-1` | exact | | | | | 1000000 | 128000 | 10.00 | 50.00 | "Most capable Claude model; priced above Opus." |
| `claude-opus-5-5` | exact | | | | | 1000000 | 128000 | 4.00 | 20.00 | |
| `claude-opus-5` | exact | | | | | 1000000 | 128000 | 5.00 | 25.00 | |
| `claude-sonnet-5-5` | exact | | | | | 1000000 | 128000 | 2.00 | 10.00 | |
| `claude-sonnet-5` | exact | | | | | 1000000 | 128000 | 2.00 | 10.00 | |
| `claude-haiku-5-5` | exact | | | | | 1000000 | 128000 | 0.10 | 0.50 | "Prompts over 100K tokens bill at $0.50/$2.50." |
| `claude-opus-4-8` | exact | | | | | | | 5.00 | 25.00 | |
| `claude-opus-4-7` | exact | | | | | | | 5.00 | 25.00 | |
| `claude-opus-4-6` | exact | | | | | | | 5.00 | 25.00 | |
| `claude-sonnet-4-6` | exact | | | | | | | 3.00 | 15.00 | |
| `claude-haiku-4-5` | exact | | | | | | | 1.00 | 5.00 | |
| `claude-haiku-4-5-20251001` | exact | | | | | | | 1.00 | 5.00 | |
| `claude-opus-4-20250514` | exact | | | | | | | 15.00 | 75.00 | |
| `claude-sonnet-4-20250514` | exact | | | | | | | 3.00 | 15.00 | |
| `claude-haiku-4-20250414` | exact | | | | | | | 0.80 | 4.00 | |

Keep the `claude-opus-4-7` / `claude-opus-4-8` prefix rows: they are longer than `claude-opus-4-` and therefore overlay it (§4.3), which reproduces today's `_STRICT_REQUEST_PREFIXES`.

**OpenAI** (`provider="openai"`). Sources in §12.

| match | type | tier | S | min | ctx | maxo | in | out | notes |
|---|---|---|---|---|---|---|---|---|---|
| `gpt-6` | prefix | | false | 16000 | | | | | "GPT-6 family: reasoning models." |
| `gpt-5` | prefix | | false | 16000 | | | | | "GPT-5 family: reasoning models." |
| `o1` | prefix | | false | 16000 | | | | | |
| `o3` | prefix | | false | 16000 | | | | | |
| `o4` | prefix | | false | 16000 | | | | | |
| `gpt-4.1` | prefix | | true | 0 | | | | | |
| `gpt-4o` | prefix | | true | 0 | | | | | |
| `gpt-6-astra` | exact | frontier | | | 1050000 | 128000 | 10.00 | 50.00 | |
| `gpt-6.1-sol` | exact | strong | | | 1050000 | 128000 | 2.00 | 10.00 | |
| `gpt-6.1-terra` | exact | efficient | | | 1050000 | 128000 | 1.00 | 5.00 | |
| `gpt-6-luna` | exact | efficient | | | 1050000 | 128000 | 0.10 | 0.50 | |
| `gpt-5.6-sol` | exact | strong | | | | | 4.00 | 20.00 | |
| `gpt-5.6-terra` | exact | efficient | | | | | 2.00 | 12.00 | |
| `gpt-5.6-luna` | exact | efficient | | | | | 0.20 | 1.20 | |
| `gpt-5.5` | exact | strong | | | | | 5.00 | 30.00 | |
| `gpt-5.4` | exact | strong | | | | | 2.50 | 15.00 | |
| `gpt-5.4-mini` | exact | efficient | | | | | 0.75 | 4.50 | |
| `gpt-5.4-nano` | exact | minimal | | | | | 0.20 | 1.25 | |
| `gpt-5` | exact | strong | | | | | 1.25 | 10.00 | |
| `gpt-5-mini` | exact | efficient | | | | | 0.25 | 2.00 | |
| `gpt-5-nano` | exact | minimal | | | | | 0.05 | 0.40 | |
| `gpt-4.1` | exact | strong | | | | | 2.00 | 8.00 | |
| `gpt-4.1-mini` | exact | efficient | | | | | 0.40 | 1.60 | |
| `gpt-4.1-nano` | exact | minimal | | | | | 0.10 | 0.40 | |
| `gpt-4o` | exact | strong | | | | | 2.50 | 10.00 | |
| `gpt-4o-mini` | exact | efficient | | | | | 0.15 | 0.60 | |

GPT-4.x prices are carried unchanged from today's `pricing.py` (not re-verified; they keep existing tests green). `structured_output` and `token_param` come from the OpenAI kind defaults (§5.2).

**Google** (`provider="google"`). Sources in §12. Prices are the post-promotion standard rates (D: conservative estimates).

| match | type | tier | ctx | in | out | deprecated | notes |
|---|---|---|---|---|---|---|---|
| `gemini-4-argon` | exact | frontier | 1000000 | 4.00 | 20.00 | | "Promotional $2.00/$10.00 through 2026-11-30." |
| `gemini-3.8-flash` | exact | strong | | 1.50 | 7.50 | | "Promotional $0.75/$3.75 through 2026-12-31." |
| `gemini-3.6-flash` | exact | efficient | | 1.50 | 7.50 | | "Promotional $0.75/$3.75 through 2026-12-31." |
| `gemini-3.5-flash-lite` | exact | efficient | | 0.30 | 2.50 | | |
| `gemini-3.1-flash-lite` | exact | minimal | | 0.25 | 1.50 | | |
| `gemini-3.1-pro-preview` | exact | strong | | 2.00 | 12.00 | | "Preview model; prompts over 200K tokens bill at $4.00/$18.00." |
| `gemini-2.5-pro` | exact | | | | | true | "Deprecated; from 2026-12-01 requests route to gemini-3.8-flash." |
| `gemini-2.5-flash` | exact | | | | | true | "Deprecated; from 2026-12-01 requests route to gemini-3.5-flash-lite." |
| `gemini-2.5-flash-lite` | exact | | | | | | "Limited to existing users; use gemini-3.5-flash-lite." |

**Ollama** (`provider="ollama"`): one entry `match="llama3.1"`, `prefix`, `tier=minimal`, `notes="Small local model; expect weaker tailoring than cloud profiles."`.

**OpenRouter** (`provider="openrouter"`), carried from today's table for compatibility:

| match | tier | in | out | deprecated |
|---|---|---|---|---|
| `anthropic/claude-sonnet-4` | strong | 3.00 | 15.00 | |
| `anthropic/claude-haiku-4` | efficient | 0.80 | 4.00 | |
| `openai/gpt-4o` | strong | 2.50 | 10.00 | |
| `openai/gpt-4.1` | strong | 2.00 | 8.00 | |
| `google/gemini-2.5-pro-preview` | strong | 1.25 | 10.00 | true |
| `google/gemini-2.5-flash-preview` | efficient | 0.15 | 0.60 | true |
| `deepseek/deepseek-chat-v3` | efficient | 0.14 | 0.28 | |

All `exact`.

### 4.2 User overrides (config file format)

Users add entries in any config layer (global `~/.config/mkcv/settings.toml`, workspace `mkcv.toml`, or env) as a TOML array of tables. Field names equal the `ModelCapability` field names:

```toml
[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"
structured_output = "json_object"
tier = "efficient"
input_price_per_mtok = 0.59
output_price_per_mtok = 0.79

[[default.model_catalog]]
provider = "openai"
match = "gpt-6.1-sol"
input_price_per_mtok = 1.80     # overlays the built-in price only
```

An array of tables avoids quoting model IDs that contain dots as TOML keys. Dynaconf runs with `merge_enabled=True`; for lists, `dynaconf.utils.object_merge` prepends the earlier layer's items, so items from later layers come later in the merged list (verified in Dynaconf 3.2.13 source). Later entries therefore win ties (§4.3).

`load_model_catalog(config) -> ModelCatalog` (`adapters/llm/model_catalog_loader.py`):

1. `raw = config.get("model_catalog", [])`. If `raw` is not a list, raise `ConfigurationError("model_catalog must be an array of tables ([[default.model_catalog]])")`.
2. Validate each item with `ModelCapability.model_validate(dict(item))`. On `pydantic.ValidationError` raise `ConfigurationError(f"Invalid [[default.model_catalog]] entry #{index + 1}: {error}")` (1-based index, error text from Pydantic).
3. Return `ModelCatalog.builtin().with_overrides(validated)`.

`with_overrides`: for each override, if an existing entry has the same `key` (`provider`, `match`, `match_type`), replace it with `existing.overlay(override)` re-wrapped as a `ModelCapability` with the same key (field-level overlay). Otherwise append the override. Order of appended overrides is preserved.

### 4.3 Resolution algorithm

Origin order: each entry has an index `i` in `entries` (built-ins first, then appended overrides in order).

`_matching(provider, model)` → entries with `entry.provider == provider and entry.matches(model)`, sorted ascending by `(entry.match_type == "exact", len(entry.match), i)`.

`lookup(provider, model, *, canonical_provider=None) -> CapabilityOverlay | None`:

1. `matches = _matching(provider, model)`.
2. If empty and `canonical_provider` is set and differs from `provider`: `matches = _matching(canonical_provider, model)`.
3. If still empty and `"/" in model`: split once into `vendor, inner`. If `vendor in {"anthropic", "openai", "google"}`, `inner_matches = _matching(vendor, inner)`; fold them (step 4) and return an overlay that keeps only `tier`, `context_window`, `max_output_tokens`, and `deprecated` (all other fields `None`: aggregator prices and request rules differ). Return `None` if `inner_matches` is empty.
4. Fold: start from an empty `CapabilityOverlay()` and `overlay` each match in sorted order. Return the result, or `None` if there were no matches.

`resolve(provider, model, *, defaults, canonical_provider=None) -> ResolvedModel`: `found = lookup(...)`; `merged = defaults.overlay(found) if found else defaults`; build `ResolvedModel` with `known = found is not None`. `defaults` must have every non-informational field set (`structured_output`, `allow_structured_fallback`, `accepts_sampling_params`, `token_param`, `min_output_tokens`); `resolve` raises `ValueError` if any of them is `None` (programming error).

`price_for(model, *, provider=None)`: if `provider` is set, fold `_matching(provider, model)`; otherwise fold every entry (any provider) whose `matches(model)` is true, using the same sort key. Return `(input, output)` when both prices are set, else `None`.

`providers_for_model(model)`: sorted unique `provider` values of entries that match `model`, restricted to `{"anthropic", "openai", "google"}`.

### 4.4 Pricing compatibility (`core/models/pricing.py`)

```python
MODEL_PRICING: dict[str, tuple[float, float]]   # per 1K tokens, derived
def calculate_cost(model: str, usage: TokenUsage, catalog: ModelCatalog | None = None, *, provider: str | None = None) -> float
```

- `MODEL_PRICING` = for every built-in entry with `match_type == "exact"` and both prices set, `{entry.match: (in / 1000, out / 1000)}`; the first entry wins on duplicate `match`. Computed at import from `BUILTIN_MODEL_CAPABILITIES`.
- `calculate_cost`: `catalog = catalog or ModelCatalog.builtin()`; `price = catalog.price_for(model, provider=provider)`; return `0.0` if `None`; else `round((usage.input_tokens * in + usage.output_tokens * out) / 1_000_000, 6)`.
- Existing results are unchanged for every key in the old table (same prices, same rounding). Dated IDs that previously had no price but match a prefix still return `0.0` because prefix entries carry no prices.

`PipelineService` and `CoverLetterService` gain a keyword-only constructor argument `catalog: ModelCatalog | None = None` and call `calculate_cost(model, usage, self._catalog, provider=provider)` where they build stage metadata. The factory passes the loaded catalog.

## 5. Provider registry

### 5.1 `ProviderSpec` (`adapters/llm/provider_spec.py`)

Frozen Pydantic model:

| Field | Type | Default |
|---|---|---|
| `name` | `str` | |
| `kind` | `ProviderKind` | |
| `base_url` | `str \| None` | `None` |
| `api_key_env` | `tuple[str, ...]` | `()` |
| `api_key` | `str \| None` | `None` (literal key from config; discouraged) |
| `requires_api_key` | `bool` | `True` |
| `defaults` | `CapabilityOverlay` | `CapabilityOverlay()` (provider-level overlay on the kind defaults) |
| `builtin` | `bool` | `False` |

### 5.2 Built-in data (`adapters/llm/builtin_providers.py`)

`KIND_DEFAULTS: dict[ProviderKind, CapabilityOverlay]`:

| Field | anthropic | openai | google | openai-compatible | stub |
|---|---|---|---|---|---|
| `structured_output` | json_schema | json_schema | json_schema | json_schema | json_schema |
| `allow_structured_fallback` | false | false | false | true | false |
| `accepts_sampling_params` | false | false | false | true | true |
| `token_param` | max_tokens | max_completion_tokens | max_tokens | max_tokens | max_tokens |
| `min_output_tokens` | 16000 | 16000 | 16000 | 0 | 0 |

Rationale: unknown Anthropic, OpenAI, and Google models are most likely new models, which reject sampling parameters and think before answering; omitting `temperature` is always accepted.

`CANONICAL_PROVIDER: dict[ProviderKind, str | None]` = `{ANTHROPIC: "anthropic", OPENAI: "openai", GOOGLE: "google", OPENAI_COMPATIBLE: None, STUB: None}`.

`BUILTIN_PROVIDERS: dict[str, ProviderSpec]` (all `builtin=True`):

| name | kind | base_url | api_key_env | requires_api_key | defaults |
|---|---|---|---|---|---|
| `anthropic` | anthropic | None | `("ANTHROPIC_API_KEY",)` | true | |
| `openai` | openai | None | `("OPENAI_API_KEY",)` | true | |
| `google` | google | None | `("GEMINI_API_KEY", "GOOGLE_API_KEY")` | true | |
| `openrouter` | openai-compatible | `https://openrouter.ai/api/v1` | `("OPENROUTER_API_KEY",)` | true | |
| `ollama` | openai-compatible | `http://localhost:11434/v1` | `()` | false | `structured_output=json_object`, `input_price_per_mtok=0.0`, `output_price_per_mtok=0.0` |
| `stub` | stub | None | `()` | false | |

Ollama's `json_object` default preserves today's behaviour (`ollama.py` sends JSON mode). Its zero prices make local runs show `$0.00`.

### 5.3 User-defined providers (config)

```toml
[default.providers.groq]
type = "openai-compatible"            # required for a new provider name
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"          # string or list of strings
# api_key = "..."                     # literal key; prefer the env var
# requires_api_key = true
# Provider-level capability defaults (any CapabilityOverlay field):
structured_output = "json_object"
accepts_sampling_params = true
token_param = "max_tokens"
```

Rules (`ProviderRegistry.from_config(config)`):

1. Start from `BUILTIN_PROVIDERS`.
2. Read `config.get("providers", {})`. For each `name, section` (a mapping):
   - `type` given and `name` is built-in: if `ProviderKind(type) != builtin.kind` raise `ConfigurationError(f"Provider '{name}' is built in as '{builtin.kind}'; its type cannot be changed")`.
   - `name` not built-in and no `type`: raise `ConfigurationError(f"Provider '{name}' needs type = \"openai-compatible\" (or another provider kind) in [default.providers.{name}]")`.
   - `type` must be one of `anthropic`, `openai`, `google`, `openai-compatible`; `stub` is rejected for user providers.
   - A new `openai-compatible` provider without `base_url` raises `ConfigurationError(f"Provider '{name}' needs base_url")`.
   - Build the spec: `base_url`, `api_key_env` (a string becomes a one-item tuple), `api_key`, `requires_api_key` (default `True` for new providers), and `defaults` = a `CapabilityOverlay` built from the overlay field names present in the section. For built-ins, given values overlay the built-in spec (`defaults` overlays `builtin.defaults`).
   - Keys other than `type`, `base_url`, `api_key_env`, `api_key`, `requires_api_key`, and the overlay fields raise `ConfigurationError(f"Unknown key '{key}' in [default.providers.{name}]")`.
3. Provider names are matched case-sensitively as written.

Existing configs keep working: `[default.providers.anthropic] api_key = "..."` still takes precedence over the env var.

### 5.4 `ProviderRegistry` (`adapters/llm/provider_registry.py`)

```python
class ProviderRegistry:
    def __init__(self, specs: Mapping[str, ProviderSpec], catalog: ModelCatalog) -> None: ...
    @classmethod
    def from_config(cls, config: Configuration, catalog: ModelCatalog) -> ProviderRegistry: ...
    @property
    def catalog(self) -> ModelCatalog: ...
    def names(self) -> tuple[str, ...]: ...                     # sorted
    def get(self, name: str) -> ProviderSpec: ...                # ConfigurationError if unknown
    def resolve_api_key(self, name: str) -> str | None: ...
    def has_credentials(self, name: str) -> bool: ...
    def defaults_for(self, name: str) -> CapabilityOverlay: ... # KIND_DEFAULTS[kind].overlay(spec.defaults)
    def resolve_model(self, name: str, model: str) -> ResolvedModel: ...
    def create_adapter(self, name: str, *, with_retry: bool = True) -> LLMPort: ...
```

- `get` on an unknown name raises `ConfigurationError(f"Unknown LLM provider '{name}'. Known providers: {', '.join(names)}. Define new ones under [default.providers.<name>].")`.
- `resolve_api_key`: `spec.api_key` if truthy; else the first env var in `spec.api_key_env` with a non-empty value; else `None`.
- `has_credentials`: `True` if `not spec.requires_api_key` or a key resolves.
- `resolve_model`: `catalog.resolve(name, model, defaults=defaults_for(name), canonical_provider=CANONICAL_PROVIDER[spec.kind])`.
- `create_adapter`:
  1. `spec = get(name)`.
  2. If `spec.kind is STUB`, return `StubLLMAdapter()` (no retry wrapper, as today).
  3. `api_key = resolve_api_key(name)`. If `spec.requires_api_key` and no key: `logger.warning("No API key for provider '%s'; falling back to stub.", name)` and return `StubLLMAdapter()` (today's behaviour). For providers that do not require a key, pass `api_key = "not-needed"` to OpenAI-compatible clients.
  4. Dispatch through a module-level `_BUILDERS: dict[ProviderKind, Callable[[ProviderSpec, str, ProviderRegistry], LLMPort]]` — no `if/elif` chain over provider names. Builders import adapter modules lazily:
     - `ANTHROPIC` → `AnthropicAdapter(api_key, base_url=spec.base_url, resolver=registry.resolve_model, provider_name=spec.name)`
     - `OPENAI` → `OpenAIAdapter(api_key, base_url=spec.base_url, resolver=..., provider_name=spec.name)`
     - `OPENAI_COMPATIBLE` → `OpenAICompatibleAdapter(api_key, base_url=spec.base_url, resolver=..., provider_name=spec.name)`
     - `GOOGLE` → `GoogleGeminiAdapter(api_key, base_url=spec.base_url, resolver=..., provider_name=spec.name)` (added in P2; until then the `GOOGLE` builder raises `ConfigurationError("The google provider is not available yet")`)
  5. Wrap with `RetryingLLMAdapter` when `with_retry`.

`resolver` is typed `ModelResolver = Callable[[str, str], ResolvedModel]` taking `(provider_name, model)`; adapters call `self._resolver(self._provider_name, model)`. Adapters default `resolver` to a function that resolves against `ModelCatalog.builtin()` with that kind's `KIND_DEFAULTS`, so direct construction in tests keeps working.

Factory: `_create_llm_adapter(provider, config, *, with_retry=True)` keeps its signature and becomes `_registry(config).create_adapter(provider, with_retry=with_retry)`. `_registry(config)` builds `ProviderRegistry.from_config(config, load_model_catalog(config))`. Delete `_PROVIDER_ENV_KEYS` and `_resolve_api_key`; `workspace_manager._build_readme` iterates `BUILTIN_PROVIDERS` instead (skip `stub`; `ollama` last; add the hint `"# Google Gemini\nexport GEMINI_API_KEY=..."`).

### 5.5 Request adaptation (`adapters/llm/request_adaptation.py`)

Module functions:

```python
def rejected_parameter(message: str) -> Literal["temperature", "max_tokens"] | None
def is_structured_output_rejection(message: str) -> bool
```

- `rejected_parameter`: lowercase the message. Return `"temperature"` if it contains `"temperature"` and any of `"unsupported"`, `"not supported"`, `"does not support"`, `"only the default"`, `"not allowed"`, `"invalid"`. Return `"max_tokens"` if it contains `"max_tokens"` and `"max_completion_tokens"`. Else `None`.
- `is_structured_output_rejection`: lowercase; `True` if it contains any of `"response_format"`, `"json_schema"`, `"json_object"`, `"structured output"`, `"response schema"`, and `rejected_parameter(message)` is `None`.

Adapters keep a per-instance `dict[str, set[str]]` of adaptations per model (`"drop_temperature"`, `"use_max_completion_tokens"`, and for the compatible adapter the degraded mode). On a `BadRequestError` (OpenAI SDK), `anthropic.BadRequestError`, or `google.genai.errors.ClientError` with code 400 whose message yields a rejected parameter that the request actually contained, the adapter records the adaptation, logs `logger.warning("%s rejected '%s' for model %s; retrying without it", provider, param, model)`, and retries the same call once. A second rejection raises `ProviderError` as today.

## 6. Stage resolution

### 6.1 Stage requirements (`core/catalog/stage_requirements.py`)

`STAGE_REQUIREMENTS: dict[StageKey, StageRequirement]`:

| stage | config_path | default_temperature | min_tier | est_input_tokens | est_output_tokens | label |
|---|---|---|---|---|---|---|
| analyze | `pipeline.stages.analyze` | 0.2 | efficient | 4000 | 2000 | Analyze JD |
| select | `pipeline.stages.select` | 0.3 | strong | 12000 | 3000 | Select experience |
| tailor | `pipeline.stages.tailor` | 0.5 | strong | 15000 | 8000 | Tailor content |
| structure | `pipeline.stages.structure` | 0.1 | efficient | 10000 | 6000 | Structure YAML |
| review | `pipeline.stages.review` | 0.3 | strong | 12000 | 4000 | Review |
| cover_letter.generate | `cover_letter.stages.generate` | 0.6 | strong | 12000 | 3000 | Cover letter |
| cover_letter.review | `cover_letter.stages.review` | 0.2 | efficient | 5000 | 2000 | Cover letter review |
| kb | `kb` | 0.3 | strong | 30000 | 8000 | KB generation |
| validate | `validate` | 0.3 | efficient | 8000 | 3000 | Validate |

Token estimates are rough planning numbers including typical thinking output. `docs/models.md` says so, and the eval report prints measured medians that replace them once a run exists.

### 6.2 Built-in profiles (`core/catalog/builtin_model_profiles.py`)

`BUILTIN_MODEL_PROFILES: dict[str, ModelProfile]`, all `evidence="provisional"`:

| stage | anthropic | openai | google | local (provider `ollama`) |
|---|---|---|---|---|
| analyze | claude-haiku-5-5 | gpt-6-luna | gemini-3.5-flash-lite | llama3.1:8b |
| select | claude-opus-5-5 | gpt-6.1-sol | gemini-4-argon | llama3.1:8b |
| tailor | claude-opus-5-5 | gpt-6-astra | gemini-4-argon | llama3.1:8b |
| structure | claude-sonnet-5-5 | gpt-6.1-terra | gemini-3.8-flash | llama3.1:8b |
| review | claude-opus-5-5 | gpt-6.1-sol | gemini-4-argon | llama3.1:8b |
| cover_letter.generate | claude-opus-5-5 | gpt-6-astra | gemini-4-argon | llama3.1:8b |
| cover_letter.review | claude-haiku-5-5 | gpt-6-luna | gemini-3.5-flash-lite | llama3.1:8b |
| kb | claude-sonnet-5-5 | gpt-6.1-sol | gemini-3.8-flash | llama3.1:8b |
| validate | claude-sonnet-5-5 | gpt-6.1-terra | gemini-3.8-flash | llama3.1:8b |

Economy variants (`economy=True`, `extends=<base>`, five pipeline stages only):

| stage | anthropic-economy | openai-economy | google-economy |
|---|---|---|---|
| analyze | claude-haiku-5-5 | gpt-6-luna | gemini-3.5-flash-lite |
| select | claude-haiku-5-5 | gpt-6.1-terra | gemini-3.8-flash |
| tailor | claude-haiku-5-5 | gpt-6.1-terra | gemini-3.8-flash |
| structure | claude-haiku-5-5 | gpt-6-luna | gemini-3.5-flash-lite |
| review | claude-haiku-5-5 | gpt-6.1-terra | gemini-3.8-flash |

Descriptions:

- `anthropic`: "Recommended Claude mix: Haiku for extraction, Opus for decisions and writing, Sonnet for YAML."
- `anthropic-economy`: "Claude Haiku for every resume stage (fast, low cost)."
- `openai`: "Recommended OpenAI mix: Luna for extraction, Astra for writing, Sol for decisions, Terra for YAML."
- `openai-economy`: "Low-cost OpenAI mix: Luna and Terra."
- `google`: "Recommended Gemini mix: Flash-Lite for extraction, Argon for decisions and writing, Flash for YAML."
- `google-economy`: "Low-cost Gemini mix: Flash-Lite and Flash."
- `local`: "Local Ollama model for every stage (free, offline, lowest quality)."

The `anthropic` and `anthropic-economy` rows reproduce today's `standard`/`comprehensive` and `concise` presets and today's `settings.toml` cover-letter and KB models exactly. `local` reproduces the legacy `budget` preset.

Module helpers (functions, same file):

- `get_profile(name: str) -> ModelProfile | None`
- `profile_stage_model(profile: ModelProfile, stage: StageKey) -> str | None` — own stage, else the `extends` profile's stage, else `None`.
- `profile_for_provider(provider: str, *, economy: bool) -> ModelProfile | None` — the built-in profile with `profile.provider == provider` and `profile.economy == economy`; if `economy` and none exists, the non-economy one; else `None`.

### 6.3 Preset changes (`core/models/profile_preset.py`)

- `Preset` drops `stage_configs` and gains `economy: bool = False` and `provider: str | None = None`.
- `concise`: `economy=True`. `standard`, `comprehensive`: `economy=False`.
- Legacy `budget`: copy of `concise` with `name="budget"`, `description="Concise resume on local Ollama models (legacy name)"`, `provider="ollama"`. Legacy `premium`: `standard`.
- Delete the `_*_STAGE_CONFIGS` dicts. `VALID_PRESET_NAMES`, `VALID_PROFILES`, and `resolve_preset` keep their behaviour.
- `PipelineService` uses the preset only for density and `max_tokens` (unchanged).

### 6.4 `settings.toml` migration

Remove `provider` and `model` from `[default.pipeline.stages.*]`, `[default.cover_letter.stages.*]`, and `[default.kb]`; keep every `temperature`, `max_tokens`, and `chunk_threshold`. Add:

```toml
[default.pipeline]
from_stage = 1
auto_render = true
interactive = false
model_warnings = true
# provider = "anthropic"        # default provider when no model_profile is set
# model_profile = "anthropic"   # anthropic, anthropic-economy, openai, openai-economy,
#                               # google, google-economy, local

[default.validate]
temperature = 0.3
```

A unit test asserts that every `temperature` in `settings.toml` equals `STAGE_REQUIREMENTS[stage].default_temperature` (the two must not drift).

Users' existing `provider`/`model` keys stay valid and now count as explicit per-stage overrides (§6.5).

### 6.5 `StageResolver` (`adapters/llm/stage_resolver.py`)

```python
DEFAULT_PROVIDER = "anthropic"

class ResolutionRequest(BaseModel):          # in adapters/llm/resolution_request.py
    preset_name: str = "default"
    model_profile: str | None = None          # --model-profile
    provider_override: str | None = None      # --provider
    model_override: str | None = None         # kb --model only

class StageResolver:
    def __init__(self, config: Configuration, registry: ProviderRegistry) -> None: ...
    def resolve(self, stages: Sequence[StageKey], request: ResolutionRequest) -> ResolvedStages: ...
```

`ResolvedStages` (`adapters/llm/resolved_stages.py`, frozen Pydantic): `assignments: dict[StageKey, StageAssignment]`, `profile: ModelProfile | None`, `profile_source: Literal["cli", "config", "default", "preset"]`, `preset_name: str`. Method `pipeline_stage_configs() -> dict[int, StageConfig]` maps the five pipeline stages to 1..5 via `PIPELINE_STAGE_NUMBERS`.

Algorithm:

1. If `request.model_profile` and `request.provider_override` are both set: raise `ConfigurationError("--model-profile and --provider cannot be used together")`.
2. `preset = resolve_preset(request.preset_name)`; `economy = preset.economy if preset else False`.
3. `provider_override = request.provider_override or (preset.provider if preset else None)`. If set, `registry.get(provider_override)` (validates the name).
4. Choose the profile:
   - `request.model_profile` set: `profile = get_profile(name)`; unknown → `ConfigurationError(f"Unknown model profile '{name}'. Available: {sorted names}")`; `profile_source = "cli"`.
   - elif `provider_override`: `profile = profile_for_provider(provider_override, economy=economy)` (may be `None`); `profile_source = "cli"` if `request.provider_override` else `"preset"`.
   - elif `config.get("pipeline.model_profile")`: validate as above; if `economy` and the profile is not economy, use `profile_for_provider(profile.provider, economy=True)`; `profile_source = "config"`.
   - else: `provider = config.get("pipeline.provider") or DEFAULT_PROVIDER`; `registry.get(provider)`; `profile = profile_for_provider(provider, economy=economy)`; `profile_source = "default"` if `pipeline.provider` is unset, else `"config"`.
5. For each stage (in the order given), with `req = STAGE_REQUIREMENTS[stage]`, read `section = config.get(req.config_path)` (may be `None`), `cfg_provider = section.get("provider")`, `cfg_model = section.get("model")`, `temperature = float(section.get("temperature", req.default_temperature))`:
   - `stage is StageKey.KB and request.model_override` → model = `request.model_override`; provider = `request.provider_override or cfg_provider or (profile.provider if profile else DEFAULT_PROVIDER)`; source `"cli"`.
   - elif `request.model_profile` set → provider = `profile.provider`, model = `profile_stage_model(profile, stage)`, source `"cli"`.
   - elif `provider_override`:
     - if `cfg_model` and `cfg_provider == provider_override` → use config (source `"config"`);
     - elif `profile` and `profile_stage_model(profile, stage)` → that model with `provider_override` (source `"cli"` or `"profile"` when the override came from the preset);
     - else → missing.
   - elif `cfg_model`: provider = `cfg_provider`, or if unset: `candidates = catalog.providers_for_model(cfg_model)`; if exactly one candidate use it, else `profile.provider` if a profile exists, else `DEFAULT_PROVIDER`. Source `"config"`.
   - elif `cfg_provider`: `p = profile_for_provider(cfg_provider, economy=economy)`; model = `profile_stage_model(p, stage)` if `p` else missing. Source `"config"`.
   - elif `profile`: provider = `profile.provider`, model = `profile_stage_model(profile, stage)`, source `"profile"`.
   - else → missing.
   - Validate the provider with `registry.get(provider)`.
   - `provider_kind = registry.get(provider).kind`.
6. If any stage is missing, raise one `ConfigurationError` listing each: `f"No model for stage '{stage}' with provider '{provider}': set model in [default.{req.config_path}] or choose a --model-profile."` joined with newlines, prefixed by `"Cannot resolve models:\n"`.
7. Log each assignment at INFO: `"Stage %s: %s/%s (source=%s, temperature=%.2f)"`.

### 6.6 Factory rewiring

| Function | Stages | Notes |
|---|---|---|
| `create_pipeline_service(config, preset_name="default", *, provider_override=None, model_profile=None, theme="sb2nov")` | `PIPELINE_STAGES` | `stage_configs = resolved.pipeline_stage_configs()`; passes `catalog` |
| `create_cover_letter_service(config, *, provider_override=None, model_profile=None, preset_name="default")` | `COVER_LETTER_STAGES` | maps generate→1, review→2 |
| `create_validation_service(config)` | `(VALIDATE,)` | adapter for the validate provider; `ValidationService(..., model=assignment.model)` |
| `create_regeneration_service(config, preset_name="default", *, provider_override=None, model_profile=None)` | `(TAILOR,)` | |
| `create_kb_generation_service(config, *, provider_override=None, model_override=None)` | `(KB,)` | `max_tokens` and `chunk_threshold` still read from `[kb]` with today's defaults |
| `create_model_report(config, *, preset_name="default", model_profile=None, provider_override=None, include_pipeline=True, include_cover_letter=False, extra_stages=()) -> ModelReport` | pipeline (if `include_pipeline`), cover letter (if `include_cover_letter`), then `extra_stages` | §8 |
| `create_pipeline_service_for_stage_configs(config, stage_configs, *, preset_name="standard", theme="sb2nov")` | given | Used by evals; builds providers from the registry |

Delete `_resolve_preset`, `_resolve_stage_configs`, `_resolve_cl_stage_configs`, `_STAGE_CONFIG_KEYS`, `_CL_STAGE_CONFIG_KEYS`, and every `"anthropic"`/`"claude-sonnet-5-5"` literal in `factory.py`. `rg -n '"anthropic"|claude-' src/mkcv/adapters/factory.py` must return nothing.

`ValidationService.__init__` gains `model: str = DEFAULT_MODEL` (keyword-only); `validate(..., model: str | None = None)` uses `model or self._model`. Same for any other public method that takes `model` with `DEFAULT_MODEL`.

### 6.7 CLI flags

- `generate`: add `--model-profile` (`str | None`, help: "Model profile for all stages: anthropic, anthropic-economy, openai, openai-economy, google, google-economy, local. Run 'mkcv models --profiles'."). Update `--provider` help to "Run every stage on this provider with its recommended models (anthropic/openai/google/ollama/openrouter or a provider from your config)." Pass both through to every factory call. `--profile budget` keeps mapping to preset `concise` + provider `ollama`.
- `cover-letter`: add `--model-profile` likewise.
- `kb`: unchanged flags (`--provider`, `--model`).
- `ConfigurationError` reaches `meta_handler`, which already prints `Error:` and exits with `exc.exit_code` (3).

## 7. Request shaping per provider

All adapters implement `LLMPort` unchanged. In every adapter, `resolved = self._resolver(self._provider_name, model)` is computed once per call, and `limit = resolved.output_limit(max_tokens)`.

### 7.1 Anthropic (`AnthropicAdapter`)

Constructor: `AnthropicAdapter(api_key: str, *, base_url: str | None = None, resolver: ModelResolver | None = None, provider_name: str = "anthropic")`.

- Request: `model`, `messages` (system split out as today), `max_tokens=limit`, `temperature` only if `resolved.accepts_sampling_params` and `"drop_temperature"` not recorded for the model.
- Structured: `JSON_SCHEMA` → `output_config={"format": {"type": "json_schema", "schema": anthropic.transform_schema(response_model)}}` (today's 5.x path); `TOOL` → forced tool (today's 4.x path). `JSON_OBJECT`/`PROMPT` are treated as `TOOL`.
- Request adaptation (§5.5) on `anthropic.BadRequestError` naming `temperature`.
- `uses_strict_request_rules(model) -> bool` stays as a module function for compatibility: `return not _builtin_resolver("anthropic", model).accepts_sampling_params`. `CLAUDE_5_MIN_MAX_TOKENS = 16_000` stays. Delete `_STRICT_REQUEST_PREFIXES` (now catalog data).
- Result for today's models is byte-for-byte the same request: verify with the existing `tests/test_adapters/test_llm/test_anthropic.py` unchanged except constructor calls.

### 7.2 OpenAI-compatible (`OpenAICompatibleAdapter`)

Constructor: `OpenAICompatibleAdapter(api_key: str, *, base_url: str | None = None, resolver: ModelResolver | None = None, provider_name: str = "openai-compatible")`. Client: `openai.AsyncOpenAI(api_key=api_key, base_url=base_url)` (omit `base_url` when `None`).

Base request (`complete` and every structured attempt):

```python
request = {"model": model, "messages": messages}
param = TokenParam.MAX_COMPLETION_TOKENS if "use_max_completion_tokens" in adaptations else resolved.token_param
request[param.value] = limit
if resolved.accepts_sampling_params and "drop_temperature" not in adaptations:
    request["temperature"] = temperature
```

`complete`: `chat.completions.create(**request)`; record usage (`prompt_tokens`, `completion_tokens`); return `choices[0].message.content or ""`.

`complete_structured`: the fallback chain in §7.4.

Error mapping (both methods): `openai.RateLimitError` → `RateLimitError`; `openai.AuthenticationError` and `openai.PermissionDeniedError` → `AuthenticationError`; `openai.APIConnectionError` → `ProviderError(f"Cannot connect to {provider_name} at {client.base_url}: {e}")`; `openai.BadRequestError` / `openai.UnprocessableEntityError` → request adaptation, then structured degradation, then `ContextLengthError` if the message contains `"context"` or `"token"`, else `ProviderError`; other `openai.APIError` → `ProviderError`. Always `provider=self._provider_name`.

### 7.3 OpenAI native (`OpenAIAdapter(OpenAICompatibleAdapter)`)

Constructor: `OpenAIAdapter(api_key: str, *, base_url: str | None = None, resolver: ModelResolver | None = None, provider_name: str = "openai")`.

Differences from the parent, all driven by data or one override hook:

- `allow_structured_fallback` is `False` from the kind defaults, so the chain is `json_schema` only.
- `token_param` is `max_completion_tokens` (kind default).
- Refusal: if `choices[0].message.refusal` is non-empty → `ProviderError(f"Model refused the request: {refusal}")`.
- The schema is `to_strict_json_schema(response_model)` (§7.5) with `strict: true`.

The parent implements refusal and truncation checks too (they are harmless for compatible endpoints), so `OpenAIAdapter` needs no method overrides: it exists for a stable import path and a distinct default `provider_name`.

### 7.4 Structured-output fallback chain

```
modes = [JSON_SCHEMA, JSON_OBJECT, PROMPT]
start = resolved.structured_output (TOOL counts as JSON_SCHEMA),
        or the degraded mode recorded for this model in this adapter instance
chain = modes[modes.index(start):] if resolved.allow_structured_fallback else [start]

for mode in chain:
    request = base request + mode shaping
    try:
        response = await create(**request)
    except BadRequestError/UnprocessableEntityError as e:
        if rejected_parameter(...) → adapt once, retry same mode (§5.5)
        elif is_structured_output_rejection(str(e)) and mode is not chain[-1]:
            record degraded mode = next mode; log warning; continue
        else: map error (§7.2)
    return parse_with_repair(response, request, mode)
```

Mode shaping:

| Mode | Request additions | Messages |
|---|---|---|
| `JSON_SCHEMA` | `response_format={"type": "json_schema", "json_schema": {"name": _schema_name(response_model), "schema": to_strict_json_schema(response_model), "strict": True}}` | unchanged |
| `JSON_OBJECT` | `response_format={"type": "json_object"}` | schema instruction appended (below) |
| `PROMPT` | none | schema instruction appended |

`_schema_name(model)` = `re.sub(r"[^a-zA-Z0-9_-]", "_", model.__name__)[:64]`. Schema instruction = `_utils.build_schema_prompt(response_model)`, appended to the system message, or a system message `"You are a helpful assistant." + instruction` prepended when none exists (today's `_augment_with_schema`, moved into this module as a private function).

Degradation warning text: `logger.warning("%s rejected %s structured output for %s; falling back to %s", provider, mode, model, next_mode)`.

`parse_with_repair(response, request, mode)`:

1. Record usage. If `message.refusal` → `ProviderError(f"Model refused the request: {refusal}")`.
2. If `choices[0].finish_reason == "length"` → `ProviderError(f"{provider} output was truncated at {limit} tokens for {model}; increase max_tokens")`.
3. `content = message.content or ""`. Try `validate_structured_response(extract_json_from_text(content), response_model)`.
4. On `ValueError` or `mkcv.core.exceptions.validation.ValidationError`: one repair call with the same request plus two appended messages:
   - `{"role": "assistant", "content": content}`
   - `{"role": "user", "content": REPAIR_PROMPT.format(error=str(err)[:2000])}`

   `REPAIR_PROMPT = "Your previous reply was not valid JSON for the required schema. Error: {error}\nReply again with only the corrected JSON object. Do not add any other text."`

   Usage from the repair call is added to the first call's usage (`get_last_usage()` returns the sum). If the repair also fails, raise `ValidationError(f"{provider} returned invalid structured output for {response_model.__name__} after one repair attempt: {err}")`.

### 7.5 Strict schema (`adapters/llm/strict_schema.py`)

`to_strict_json_schema(response_model: type[BaseModel]) -> dict[str, Any]`:

1. `schema = resolve_schema_refs(response_model.model_json_schema())` (inline `$defs`; mkcv response models are not recursive).
2. Walk every node. For each dict node keep only these keys: `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, `anyOf`, `description`, `title`, `pattern`, `format`, `multipleOf`, `maximum`, `exclusiveMaximum`, `minimum`, `exclusiveMinimum`, `minItems`, `maxItems`. Drop every other key (`default`, `minLength`, `maxLength`, `examples`, `discriminator`, …).
3. For `format`, keep it only if the value is one of `date-time`, `time`, `date`, `duration`, `email`, `hostname`, `ipv4`, `ipv6`, `uuid`.
4. For every node with `"type": "object"` or a `properties` key: set `additionalProperties` to `False` and `required` to the list of all property names in declaration order.
5. A property that was not in the original `required` and whose schema does not already allow `null` becomes nullable: if it has `type` as a string, make it `[type, "null"]`; if it has `anyOf`, append `{"type": "null"}`; otherwise wrap as `{"anyOf": [schema, {"type": "null"}]}`.

Step 5 lets the model send `null` for a field that has a default. The same module defines `drop_nulls_for_defaulted_fields(data: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]`: it returns a copy without keys whose value is `None` where the Pydantic field is required-with-default and its annotation does not allow `None`; it recurses into values whose field annotation is a `BaseModel` subclass or `list[BaseModel]`. `OpenAICompatibleAdapter` applies it to the parsed JSON before `validate_structured_response` in `JSON_SCHEMA` mode only. `_utils.py` is not changed.

A parametrized unit test runs `to_strict_json_schema` over every response model used with `complete_structured` (`JDAnalysis`, `ExperienceSelection`, `TailoredContent`, `ReviewReport`, `JDFrontmatter`, `CoverLetter`, `CoverLetterReview`, `MissionStatement`, `SkillsSection`, `TailoredRole`, `EarlierExperienceSection`, `LanguagesSection`) and asserts: no `$ref`/`$defs`; every object has `additionalProperties: false` and `required == list(properties)`; nesting depth ≤ 10; total properties ≤ 5000; root is an object without `anyOf`. Implementers find the full list with `rg -n "response_model=" src/mkcv/core/services`.

### 7.6 Google Gemini (`GoogleGeminiAdapter`, `adapters/llm/google.py`)

Constructor: `GoogleGeminiAdapter(api_key: str, *, base_url: str | None = None, resolver: ModelResolver | None = None, provider_name: str = "google")`. Client: `genai.Client(api_key=api_key, http_options=types.HttpOptions(base_url=base_url) if base_url else None)`. Imports `from google import genai` and `from google.genai import errors, types` inside the module (the module itself is imported lazily by the registry builder).

Message conversion: system messages → `system_instruction` (joined with `"\n\n"`); `user` → `types.Content(role="user", parts=[types.Part.from_text(text=...)])`; `assistant` → role `"model"`.

Config: `types.GenerateContentConfig(system_instruction=..., max_output_tokens=limit, temperature=temperature if resolved.accepts_sampling_params and not dropped else None)`. Structured calls add `response_mime_type="application/json"` and `response_json_schema=resolve_schema_refs(response_model.model_json_schema())`. No `thinking_config` (model default).

Call: `await self._client.aio.models.generate_content(model=model, contents=contents, config=config)`.

Response handling:

- Usage: `meta = response.usage_metadata`; `input_tokens = meta.prompt_token_count or 0`; `output_tokens = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)` (Google bills thinking as output).
- `text = response.text or ""`. If empty: if `response.prompt_feedback` has a `block_reason` → `ProviderError(f"Gemini blocked the prompt: {block_reason}")`; if the first candidate's `finish_reason` is `MAX_TOKENS` → truncation `ProviderError` (same text as §7.4 step 2); else `ProviderError("Gemini returned no text")`.
- Structured: `validate_structured_response(extract_json_from_text(text), response_model)`; on failure, one repair call identical in spirit to §7.4 (append `model` and `user` turns); then `ValidationError`.

Errors: `errors.ClientError` with `code == 429` → `RateLimitError`; `code in (401, 403)` → `AuthenticationError`; `code == 400` → request adaptation (§5.5), else `ContextLengthError` if the message contains `"token"` or `"context"`, else `ProviderError`; other `errors.ClientError`, `errors.ServerError`, `errors.APIError` → `ProviderError`. `str(e)` is the message.

## 8. Warnings and `mkcv models`

### 8.1 `ModelAdvisor` (`core/services/model_advisor.py`)

```python
class ModelAdvisor:
    def __init__(self, catalog: ModelCatalog, requirements: Mapping[StageKey, StageRequirement] = STAGE_REQUIREMENTS, profiles: Mapping[str, ModelProfile] = BUILTIN_MODEL_PROFILES) -> None: ...
    def advise(self, assignments: Sequence[StageAssignment], *, profile: ModelProfile | None, profile_source: Literal["cli", "config", "default", "preset"], preset_name: str, provider_warnings: Sequence[ModelWarning] = (), provider_defaults: Mapping[str, CapabilityOverlay] | None = None) -> ModelReport: ...
```

Per assignment `a` with requirement `req`:

- `canonical = {"anthropic", "openai", "google"} ∩ {a.provider_kind.value}` (the kind value when it is one of those three).
- `entry = catalog.lookup(a.provider, a.model, canonical_provider=canonical or None)`; `known = entry is not None`; `tier = entry.tier if entry else None`.
- Recommended: `p = profile_for_provider(a.provider, economy=False)`; `recommended = profile_stage_model(p, a.stage)` with `recommended_provider = a.provider` if found; otherwise the `anthropic` profile's model with provider `anthropic`.
- Cost: price from `catalog.price_for(a.model, provider=a.provider)`, else from the `canonical` provider, else both prices from `provider_defaults[a.provider]` when both are set (this is how Ollama shows `$0.0000`; the factory passes `{p: registry.defaults_for(p)}` for every provider in the assignments); `cost = (req.est_input_tokens * in + req.est_output_tokens * out) / 1_000_000` rounded to 6 places, or `None`.
- Warnings (messages verbatim, `{s}` = stage value, `{m}` = model, `{p}` = provider):

| Kind | Condition | Message |
|---|---|---|
| `unknown_model` | `not known` | `"{s}: no capability data for {p}/{m}; mkcv will use conservative defaults. Describe it with a [[default.model_catalog]] entry."` |
| `tier_unknown` | `known`, `tier is None`, `a.source != "profile"` | `"{s}: quality tier of {p}/{m} is unknown; mkcv recommends at least '{min}' for this stage (recommended: {rec})."` |
| `below_recommended_tier` | `tier` set, `tier.rank() < req.min_tier.rank()`, `a.source != "profile"` | `"{s}: {p}/{m} is tier '{tier}'; mkcv recommends at least '{min}' for this stage (recommended: {rec})."` |
| `deprecated_model` | `entry.deprecated` | `"{s}: {p}/{m} is deprecated. {notes}"` (notes omitted when `None`) |

`{rec}` = `f"{recommended_provider}/{recommended}"`.

- `estimated_total_usd` = sum of known stage costs, `None` if every stage is unknown; `estimate_is_partial` = any stage cost is `None` while another is known.
- `warnings` = provider warnings first, then stage warnings in stage order.

### 8.2 Provider-level warnings (factory)

`create_model_report` builds one `ModelWarning(kind=MISSING_API_KEY, stage=None, provider=p, model=None, message=f"{p}: no API key found (set {' or '.join(spec.api_key_env)}); mkcv will use the offline stub and produce empty output.")` for each distinct provider in the assignments where `not registry.has_credentials(p)`. For a provider with an empty `api_key_env` that requires a key, the parenthetical reads `(set api_key in [default.providers.{p}])`.

### 8.3 Warning output in `generate` and `cover-letter`

New module `src/mkcv/cli/model_warnings.py`:

```python
def print_model_warnings(report: ModelReport, console: Console) -> None
```

Prints each warning as `[yellow]Warning:[/yellow] {message}` and, if any were printed, one dim line `Run 'mkcv models' for recommended models per stage.` Nothing else.

`generate_command`: after preset/provider resolution and before dispatching, if `settings.get("pipeline.model_warnings", True)` is truthy, call `create_model_report(settings, preset_name=effective_cv_preset, model_profile=model_profile, provider_override=resolved_provider, include_cover_letter=cover_letter)` and `print_model_warnings(report, console)`. A `ConfigurationError` raised here propagates (exit 3) before any LLM call. `cover_letter_command` does the same with `include_pipeline=False, include_cover_letter=True`. Warnings never block.

### 8.4 `mkcv models`

Register in `cli/app.py`: `app.command("mkcv.cli.commands.models:models_command", name="models")`.

```
mkcv models [--model-profile NAME] [--provider NAME] [--preset NAME]
            [--profiles] [--catalog] [--json]
```

- Default view: `create_model_report(settings, preset_name=preset or "standard", model_profile=..., provider_override=..., include_cover_letter=True, extra_stages=(StageKey.KB, StageKey.VALIDATE))`.
- `--profiles`: table of built-in profiles (name, provider, economy, evidence, description) and, per profile, the stage → model map.
- `--catalog`: table of catalog entries (provider, match, type, tier, structured output, sampling, price in/out, notes), filtered by `--provider` when given. User overrides are included.
- `--json`: prints `report.model_dump_json(indent=2)` (default view), or a JSON list of profiles / entries for the other views.
- Output goes to stdout (`output_console`); exit 0. `ConfigurationError` exits 3 via `meta_handler`.

Default view mock (Rich table; column headers exact):

```
Model profile: anthropic (provisional: not yet backed by an eval run)
Source: default (no --model-profile, no pipeline.model_profile)   Preset: standard

 Stage                  Provider   Model               Source    Recommended                 Tier       Est. cost
 analyze                anthropic  claude-haiku-5-5    profile   anthropic/claude-haiku-5-5  efficient  $0.0014
 select                 anthropic  claude-opus-5-5     profile   anthropic/claude-opus-5-5   frontier   $0.1080
 tailor                 openai     gpt-6.1-terra       config    openai/gpt-6-astra          efficient  $0.0550
 structure              anthropic  claude-sonnet-5-5   profile   anthropic/claude-sonnet-5-5 strong     $0.0800
 review                 anthropic  claude-opus-5-5     profile   anthropic/claude-opus-5-5   frontier   $0.1280
 cover_letter.generate  anthropic  claude-opus-5-5     profile   anthropic/claude-opus-5-5   frontier   $0.1080
 cover_letter.review    anthropic  claude-haiku-5-5    profile   anthropic/claude-haiku-5-5  efficient  $0.0015
 kb                     anthropic  claude-sonnet-5-5   profile   anthropic/claude-sonnet-5-5 strong     $0.1400
 validate               anthropic  claude-sonnet-5-5   profile   anthropic/claude-sonnet-5-5 strong     $0.0460

Estimated cost per resume run (5 stages): $0.37
Estimates use rough per-stage token counts; see docs/models.md.

Warnings:
  tailor: openai/gpt-6.1-terra is tier 'efficient'; mkcv recommends at least 'strong' for this stage (recommended: openai/gpt-6-astra).
  openai: no API key found (set OPENAI_API_KEY); mkcv will use the offline stub and produce empty output.
```

"Estimated cost per resume run" sums the five pipeline stages only; append ` (partial: some prices unknown)` when partial; print `n/a` when no price is known. Cost cells print `$` with 4 decimals, or `n/a`. The provisional header line reads `(eval-backed: <eval_run>)` when `evidence == "eval"`. When no profile applies, print `Model profile: none (all stages set explicitly)`.

## 9. Eval harness

### 9.1 Location and packaging (D15)

Top-level `evals/` package at the repository root. Not packaged (`[tool.hatch.build.targets.wheel] packages = ["src/mkcv"]` already excludes it). Add `pythonpath = ["."]` to `[tool.pytest.ini_options]` so `tests/test_evals/` can import `evals`. CI lint and format checks extend to `evals/`; mypy runs on `src/ evals/`.

### 9.2 Layout

```
evals/
  __init__.py
  __main__.py                      # from evals.cli import main; raise SystemExit(main())
  cli.py                           # argparse commands (§9.8)
  README.md                        # how to run, cost, keys, publishing
  config/matrix.toml               # default matrix (§9.3)
  models/                          # Pydantic models, one class per file
    eval_case.py  matrix_model.py  judge_config.py  run_settings.py
    matrix_config.py  grade.py  eval_record.py  stage_summary.py
    recommendation.py  run_manifest.py
    faithfulness_verdict.py  faithfulness_judgement.py
    criterion_score.py  rubric_judgement.py  defect_finding.py  defect_judgement.py
  harness/
    case_loader.py                 # load_cases(fixtures_dir) -> list[EvalCase]
    stop_after_stage.py            # StopAfterStage (StageCallbackPort)
    stage_run.py                   # StageRun (result of one stage execution)
    stage_runner.py                # StageRunner
    eval_runner.py                 # EvalRunner
    cost_estimator.py              # estimate_matrix_cost(...)
    reference_bootstrapper.py      # ReferenceBootstrapper
    judge_factory.py               # create_judge(config, judge_config) -> (LLMPort, model)
  graders/
    grader.py                      # Grader Protocol
    grading_context.py             # GradingContext
    schema_grader.py  jd_recall_grader.py  ats_rules_grader.py  structure_grader.py
    faithfulness_extraction_grader.py  faithfulness_judge_grader.py
    selection_judge_grader.py  tailoring_judge_grader.py  review_defect_grader.py
    stage_graders.py               # STAGE_GRADERS mapping + PRIMARY_METRIC
    text_normalization.py          # helper functions for extraction
    rubrics/faithfulness.md  selection.md  tailoring.md  review_defects.md
  report/
    aggregator.py                  # aggregate(records) -> list[StageSummary]
    recommender.py                 # recommend(summaries) -> list[Recommendation]
    markdown_report.py             # render_markdown(manifest, summaries, recs) -> str
  fixtures/
    cases.toml
    personas/backend-engineer.md  product-switcher.md  data-scientist.md
    jds/backend-platform-match.md  backend-ml-stretch.md
        product-pm-match.md  product-growth-stretch.md
        data-analytics-match.md  data-mlops-stretch.md
    reference/<case_id>/stage1_analysis.json ... stage4_structure.* (bootstrapped)
    reference/review-probe/...     # hand-written, seeded defects
  results/                         # gitignored except published/
tests/test_evals/
  conftest.py
  fixtures/recorded/<case_id>/...  # hand-written stage outputs for grader tests
  test_case_loader.py  test_stage_runner.py  test_eval_runner.py
  test_schema_grader.py  test_jd_recall_grader.py  test_ats_rules_grader.py
  test_structure_grader.py  test_faithfulness_extraction_grader.py
  test_judge_graders.py  test_aggregator.py  test_recommender.py
  test_markdown_report.py  test_cost_estimator.py  test_cli.py
```

### 9.3 Matrix config (`evals/config/matrix.toml`)

```toml
[run]
repeats = 1
concurrency = 2
stages = ["analyze", "select", "tailor", "structure", "review"]
cases = ["*"]                       # case IDs or "*"
preset = "standard"

[judge]
provider = "anthropic"
model = "claude-opus-5-5"

[reference]
provider = "anthropic"
model = "claude-opus-5-5"

[[models]]
provider = "anthropic"
model = "claude-opus-5-5"
[[models]]
provider = "anthropic"
model = "claude-sonnet-5-5"
[[models]]
provider = "anthropic"
model = "claude-haiku-5-5"
[[models]]
provider = "openai"
model = "gpt-6-astra"
[[models]]
provider = "openai"
model = "gpt-6.1-sol"
[[models]]
provider = "openai"
model = "gpt-6.1-terra"
[[models]]
provider = "openai"
model = "gpt-6-luna"
[[models]]
provider = "google"
model = "gemini-4-argon"
[[models]]
provider = "google"
model = "gemini-3.8-flash"
[[models]]
provider = "google"
model = "gemini-3.5-flash-lite"
```

`MatrixConfig` = `run: RunSettings`, `judge: JudgeConfig`, `reference: JudgeConfig` (same shape: `provider`, `model`), `models: list[MatrixModel]` (`provider`, `model`, optional `temperature: float | None`). Loaded with `tomllib`. Mkcv config (providers, keys, catalog overrides) comes from the normal `mkcv.config.settings`, so custom providers work in the matrix.

### 9.4 Fixtures

`fixtures/cases.toml`:

```toml
[[cases]]
id = "backend-platform-match"
persona = "personas/backend-engineer.md"
jd = "jds/backend-platform-match.md"
expected_keywords = ["Kubernetes", "Go", "PostgreSQL", "observability", "incident response", "Terraform"]
forbidden_claims = []
review_probe_defects = []
```

Six cases (persona × JD):

| Case ID | Persona | JD | Purpose |
|---|---|---|---|
| `backend-platform-match` | backend-engineer | backend-platform-match | Strong match, rich metrics |
| `backend-ml-stretch` | backend-engineer | backend-ml-stretch | Stretch: JD asks for ML ops and PyTorch the KB lacks → `forbidden_claims = ["PyTorch", "model training", "MLflow"]` |
| `product-pm-match` | product-switcher | product-pm-match | Career switcher into PM |
| `product-growth-stretch` | product-switcher | product-growth-stretch | Stretch: `forbidden_claims = ["SQL", "A/B testing platform", "Amplitude"]` |
| `data-analytics-match` | data-scientist | data-analytics-match | Early career, education heavy |
| `data-mlops-stretch` | data-scientist | data-mlops-stretch | Stretch: `forbidden_claims = ["Kubernetes", "Airflow", "team lead"]` |

`EvalCase` fields: `id: str`, `persona: str`, `jd: str` (paths relative to `evals/fixtures/`), `expected_keywords: list[str] = []`, `forbidden_claims: list[str] = []`, `review_probe_defects: list[str] = []`, `stages: list[StageKey] | None = None` (`None` = every stage in the matrix). Loader resolves paths and reads both files into `kb_text`/`jd_text` properties (computed, not serialized).

Plus `review-probe` (persona backend-engineer, JD backend-platform-match, `stages = ["review"]`) whose reference stage-4 artifacts (`stage4_structure` and `resume.yaml`) are hand-written in T14 with three seeded defects. `bootstrap-reference` fills `review-probe`'s stage 1–3 references by copying them from `backend-platform-match` and never overwrites its stage-4 files. The seeded defects are: `review_probe_defects = ["first-person pronoun in a bullet", "a metric (\"cut costs by 73%\") that is not in the knowledge base", "the JD keyword 'Terraform' is missing from the resume"]`.

Persona rules (all synthetic; no real people, employers, schools, or contact data):

- Format follows the workspace KB template headings (`## Personal Information`, `## Professional Summary`, `## Technical Skills -- Master List`, `## Career History -- Complete and Detailed` with `### Company -- Title` per role, `## Key Achievements`, `## Education` added).
- Names: `Alex Rivera` (backend-engineer), `Jordan Lee` (product-switcher), `Sam Patel` (data-scientist). Emails `@example.com`; phone `555-01xx`; city only.
- Employers are fictional TV/film companies: Initech, Globex, Hooli, Pied Piper, Vandelay Industries, Dunder Mifflin, Wonka Industries, Stark Industries. Schools: "State University", "Riverside Community College".
- `backend-engineer`: 4 roles over 10 years, each with 4–7 bullets, at least 12 distinct numeric metrics overall. 150–250 lines.
- `product-switcher`: 3 roles (2 design, 1 associate PM), few metrics (at most 5). 120–200 lines.
- `data-scientist`: 2 roles + 2 projects + education with coursework. 100–160 lines.
- JDs: 40–80 lines, fictional company names (Acme Corp, Umbrella Analytics, Cyberdyne Systems), realistic requirements; each stretch JD mentions every `forbidden_claims` term at least once.

Reference artifacts for stages 1–4 come from `bootstrap-reference` (§9.8), are reviewed by a human (no fabricated facts), and are committed. Until they exist, stage-isolated runs for `select`, `tailor`, `structure`, and `review` record `status="skipped"` with `error="no reference artifacts; run: uv run python -m evals bootstrap-reference"`.

### 9.5 Stage isolation (D16)

`StageRunner.run(case, stage, matrix_model, repeat, work_dir) -> StageRun` (`StageRun` holds the artifact payload, `StageMetadata`, status, error):

1. `stage_number = PIPELINE_STAGE_NUMBERS[stage]`.
2. Create `work_dir/.mkcv/`. For every upstream stage `< stage_number`, copy the case's reference artifact files into `work_dir/.mkcv/` under the pipeline's artifact names (`stage1_analysis`, `stage2_selection`, `stage3_content`, `stage4_structure`; the implementer confirms the file extensions the `FileSystemArtifactStore` writes by reading `src/mkcv/adapters/filesystem/artifact_store.py`). For stage 5, also copy the reference `resume.yaml` to `work_dir/` if the pipeline reads it (confirm in `pipeline.py` `_review`).
3. `stage_configs` = all five stages set to `StageConfig(provider, model, temperature)` where temperature is `matrix_model.temperature` or `STAGE_REQUIREMENTS[stage].default_temperature`.
4. `service = create_pipeline_service_for_stage_configs(settings, stage_configs, preset_name=run.preset)`.
5. `await service.generate(jd_path, kb_path, output_dir=work_dir, from_stage=stage_number, stage_callback=StopAfterStage(stage_number))`.
6. `StopAfterStage.on_stage_complete` stores the `StageMetadata` for `stage_number` and returns `False`; `on_stage_start` does nothing.
7. Read the produced artifact for `stage_number` from `work_dir/.mkcv/` (and `resume.yaml` for stage 4).
8. Catch `MkcvError` → `status="error"`, `error=str(exc)`; never let one failure abort the run.

`work_dir = results_dir / "raw" / case_id / stage / f"{_slug(provider)}__{_slug(model)}" / f"r{repeat}"`, `_slug` replaces every character outside `[A-Za-z0-9._-]` with `_`.

### 9.6 Graders

`Grader` Protocol: `name: str`; `async def grade(self, ctx: GradingContext) -> Grade`. `GradingContext`: `case: EvalCase`, `stage: StageKey`, `kb_text: str`, `jd_text: str`, `output: dict[str, Any] | str | None` (parsed artifact; YAML text for stage 4), `reference: dict[str, Any]` (upstream reference artifacts by name), `judge: LLMPort | None`, `judge_model: str | None`. `Grade`: `name: str`, `score: float | None` (0–1), `passed: bool | None`, `details: dict[str, Any]`.

`STAGE_GRADERS` and the primary quality metric per stage:

| Stage | Graders | Primary metric |
|---|---|---|
| analyze | `schema`, `jd_keyword_recall` | `jd_keyword_recall` |
| select | `schema`, `faithfulness_extraction`, `selection_judge` | `selection_judge` |
| tailor | `schema`, `faithfulness_extraction`, `faithfulness_judge`, `tailoring_judge` | `tailoring_judge` |
| structure | `schema`, `ats_rules`, `structure`, `faithfulness_extraction` | `ats_rules` |
| review | `schema`, `review_defect_recall` (probe case only) | `review_defect_recall` |

Deterministic graders:

- **schema**: stage 1–3 and 5 — the artifact validates against `JDAnalysis`, `ExperienceSelection`, `TailoredContent`, `ReviewReport` (score 1.0/0.0). Stage 4 — `resume.yaml` parses with `ruamel.yaml` (`YAML(typ="safe")`) and has `cv.name` (str) and `cv.sections` (mapping, non-empty).
- **jd_keyword_recall**: fraction of `case.expected_keywords` that appear case-insensitively anywhere in `json.dumps(output)`. `passed = score >= 0.8`.
- **ats_rules** (stage 4 YAML). Each rule is pass/fail; `score = passed_rules / 7`; `passed = all`; `details.failures` lists rule IDs with offending text:
  - R1 every key of `cv.sections`, lowercased with `_` → space, is in `{"summary", "experience", "work experience", "professional experience", "earlier experience", "education", "skills", "technical skills", "technologies", "projects", "certifications", "publications", "languages", "awards", "volunteer", "volunteering"}`.
  - R2 `cv.email` matches `^[^@\s]+@[^@\s]+\.[^@\s]+$`.
  - R3 no highlight matches `(?i)\b(i|me|my|mine|myself)\b`.
  - R4 every highlight ≤ 300 characters.
  - R5 every entry with highlights has 1–8 highlights.
  - R6 every `start_date`/`end_date` matches `^\d{4}(-\d{2})?$` or equals `present` (case-insensitive).
  - R7 no string contains `<` followed by a letter (HTML) or a Markdown table row (`^\s*\|.*\|\s*$`).
- **structure** (stage 4): every company in the reference `stage3_content` roles appears in the YAML text (normalized); `score` = fraction present.
- **faithfulness_extraction**: claims extracted from the output (bullets: `rewritten` in stage 3, `highlights` in stage 4; companies and titles in stages 2–4) are checked against the KB:
  - numbers: regex `(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s?(?:%|percent|x|k|m|b)?(?![\w])`, case-insensitive; normalize by removing `$`, `,` and spaces, lowercase, `percent` → `%`; a number is supported if its normalized form or its bare digits appear among the KB's normalized numbers. Years 1950–2100 inside date fields are skipped.
  - companies / titles: normalize (lowercase, strip punctuation, drop trailing `inc`, `llc`, `ltd`, `corp`, `co`); supported if a substring of the normalized KB.
  - forbidden claims: each `case.forbidden_claims` term found (word boundary, case-insensitive) in bullets or skills is a violation.
  - `score = 1 - violations / max(1, checked)`; `passed = violations == 0`; `details.violations` = list of `{type, text}`.

LLM-judge graders call `judge.complete_structured(messages, model=judge_model, response_model=..., temperature=0.0, max_tokens=8192)`. The judge LLM comes from `create_judge`, which uses the provider registry (so the judge's own request rules apply). Rubric files are read from `Path(__file__).parent / "rubrics" / name`.

- **faithfulness_judge** (stage 3): messages = system: rubric `faithfulness.md`; user: KB text, then numbered bullets. Response `FaithfulnessJudgement(items: list[FaithfulnessVerdict])`, `FaithfulnessVerdict(index: int, verdict: Literal["supported", "partial", "unsupported"], evidence: str)`. Score = `(supported + 0.5 * partial) / n`; `passed = score >= 0.9`.
- **selection_judge** (stage 2) and **tailoring_judge** (stage 3): response `RubricJudgement(criteria: list[CriterionScore], summary: str)`, `CriterionScore(name: str, score: int (1..5), rationale: str)`. Score = mean of criterion scores / 5. Criteria and anchors in §9.7.
- **review_defect_recall** (stage 5, probe case): user message lists the seeded defects and the review output. Response `DefectJudgement(findings: list[DefectFinding])`, `DefectFinding(defect: str, detected: bool, quote: str)`. Score = detected / defects.

Each judge grade records `details.judge = f"{provider}/{model}"` and `details.self_judged = judge provider == evaluated provider`.

### 9.7 Rubrics

`rubrics/tailoring.md` (tailor stage), scored 1–5 per criterion; anchors: 1 = poor, 3 = acceptable, 5 = excellent:

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| `relevance` | Bullets ignore the JD's main requirements | Most bullets map to some requirement | Every bullet supports a stated requirement, strongest first |
| `keyword_integration` | JD terms missing or stuffed | Key terms present but sometimes forced | Key terms woven in naturally, only where the KB supports them |
| `impact` | Duties, no outcomes | Some outcomes, few numbers | Outcome-first bullets using every KB-supported metric |
| `clarity` | Long, vague, or repetitive | Clear with some filler | Concise, specific, one idea per bullet, strong verbs |
| `prioritization` | Irrelevant roles and bullets lead | Order mostly sensible | Most relevant experience and bullets come first; weak ones dropped |

`rubrics/selection.md` (select stage) criteria: `role_relevance`, `requirement_coverage`, `omission_quality` (irrelevant experience left out), `ordering`, same anchor style.

`rubrics/faithfulness.md`: "Judge each bullet only against the knowledge base. `supported`: every fact (employer, title, tool, number, scope, outcome) is stated or directly implied by the KB. `partial`: the core claim is supported but a detail is embellished. `unsupported`: any fact is absent from or contradicts the KB. Rewording is fine; new facts are not. Quote the KB evidence."

`rubrics/review_defects.md`: "For each listed defect, decide whether the review identifies it (in any field). Quote the review text that does so, or an empty string."

Each rubric file starts with the instruction "Return only the JSON object for the requested schema." and the criteria table above.

### 9.8 Commands

| Command | Behaviour |
|---|---|
| `uv run python -m evals list-cases` | Prints case IDs, persona, JD, and whether reference artifacts exist |
| `uv run python -m evals estimate [--matrix PATH]` | Prints estimated cost per model and total: `cases × repeats × Σ_stage (est tokens × catalog price)` plus judge calls (estimate 6000 input / 1500 output tokens per judge call); unknown prices print `n/a` |
| `uv run python -m evals run [--matrix PATH] [--out DIR] [--stages ...] [--cases ...] [--models provider:model ...] [--judge provider:model] [--concurrency N] [--yes] [--strict]` | Prints the estimate; without `--yes` asks `Proceed? [y/N]` on a TTY and exits 2 when stdin is not a TTY. Skips models whose provider has no credentials (warning) unless `--strict` (then exits 2). Runs, grades, writes results, aggregates, renders the report. Exit 0 even when individual records failed |
| `uv run python -m evals report DIR [--publish]` | Recomputes `summary.json` and `report.md` from `results.jsonl`. `--publish` copies `results.jsonl`, `summary.json`, `report.md`, `run.json` (not `raw/`) to `evals/results/published/<run_id>/` |
| `uv run python -m evals bootstrap-reference [--cases ...] [--provider P --model M] [--yes]` | Runs stages 1–4 with the reference model per case and writes artifacts to `evals/fixtures/reference/<case_id>/`; prints a reminder to review them before committing |

The documented one-command live run is `uv run python -m evals run --yes` (after `bootstrap-reference` once).

Default `--out`: `evals/results/<UTC %Y%m%d-%H%M%S>-<git short sha or "nogit">/`. `.gitignore` gains `evals/results/*` and `!evals/results/published/`.

### 9.9 Results and report

- `results.jsonl`: one `EvalRecord` per `(case, stage, provider, model, repeat)`: `run_id`, `case_id`, `stage`, `provider`, `model`, `repeat`, `status` (`ok`|`error`|`skipped`), `error`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_s` (from `StageMetadata.duration_seconds`), `grades: list[Grade]`, `judge: str | None`.
- `run.json` (`RunManifest`): `run_id`, `started_at`, `finished_at`, `mkcv_version`, `git_sha`, `matrix` (as loaded), `judge`, `catalog_prices` (`{provider/model: [in, out]}` used for cost), `cases`.
- `summary.json`: list of `StageSummary` per `(stage, provider, model)`: `n`, `ok_rate`, `mean` per grade name, `primary_score`, `cost_mean_usd`, `latency_p50_s`, `latency_p90_s`, `median_input_tokens`, `median_output_tokens`, `eligible: bool`, `self_judged: bool`, `low_sample: bool` (`n < 6`).
- Eligibility: `ok_rate >= 0.95` and `schema >= 0.95` and, where the stage has them, `faithfulness_extraction >= 0.95` and `faithfulness_judge >= 0.90`.
- Recommendation per `(stage, provider)` (`Recommendation`: `stage`, `provider`, `best`, `recommended`, `economy`, `reason`):
  - `best` = eligible model with the highest `primary_score` (ties: lower cost, then lower p50 latency).
  - `recommended` = cheapest eligible model with `primary_score >= best.primary_score - 0.05`.
  - `economy` = cheapest eligible model with `primary_score >= 0.70`.
  - No eligible model → all `None`, `reason="no eligible model"`.
- Latency percentiles and token medians use `ok` records only; `skipped` records are excluded from `n`.
- `report.md` sections, in order (exact headings in `specs/eval-harness.md` REQ-EV-18): title `# mkcv eval report: <run_id>`; run metadata table; caveats (self-judged rows, low samples, skipped models, failed records count); cost summary per model; one table per stage with columns `Provider | Model | n | OK | Schema | Faithfulness (det) | Faithfulness (judge) | Quality | Cost/run | p50 latency | Eligible | Notes`; recommendations table per stage and provider; "Suggested profile changes" listing, per built-in profile and stage, the current model vs the recommended one where they differ; measured median tokens per stage next to the `STAGE_REQUIREMENTS` estimates.

Applying results is manual (D17): edit `core/catalog/builtin_model_profiles.py` (set `evidence="eval"`, `eval_run="<run_id>"`) and `docs/models.md`, citing `evals/results/published/<run_id>/report.md`.

### 9.10 CI

CI runs only unit tests: graders on recorded outputs in `tests/test_evals/fixtures/recorded/`, the runner with `StubLLMAdapter` providers and a stub judge, the aggregator, recommender, and report renderer on synthetic records. No test touches the network; `tests/conftest.py` already mocks providers, and `tests/test_evals/conftest.py` adds an autouse fixture that deletes `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `OPENROUTER_API_KEY` from the environment.

## 10. Configuration reference (after the change)

```toml
[default.pipeline]
provider = "openai"                 # default provider when no model_profile is set
model_profile = "openai"            # or a built-in profile name
model_warnings = true

[default.pipeline.stages.tailor]    # per-stage override (wins over the profile)
provider = "anthropic"
model = "claude-opus-5-5"
temperature = 0.5

[default.cover_letter.stages.generate]
model = "gpt-6-astra"               # provider inferred from the catalog

[default.kb]
provider = "google"

[default.validate]
model = "gpt-6.1-terra"

[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"

[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"
tier = "efficient"
structured_output = "json_object"
```

Env vars work through Dynaconf as today, e.g. `MKCV_PIPELINE__MODEL_PROFILE=google`.

## 11. Testing strategy

- **Provider SDK mocking** follows the existing pattern in `tests/test_adapters/test_llm/test_anthropic.py` and `test_openai.py`: patch the SDK client object on the adapter instance (`adapter._client = MagicMock()` with `AsyncMock` methods) and assert on the recorded call kwargs. Build fake responses with the SDK's own Pydantic types where practical (`openai.types.chat.ChatCompletion`, `google.genai.types.GenerateContentResponse`), else `SimpleNamespace`.
- Construct SDK errors for error-mapping tests the way the existing tests do (`openai.BadRequestError(message=..., response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)`); for Google, `errors.ClientError(400, {"error": {"message": "..."}})` (the implementer confirms the constructor with `inspect.signature(errors.ClientError.__init__)`).
- Registry, resolver, and loader tests use a real `Configuration`-like object: the existing `test_factory.py` pattern (a `MagicMock` or `Dynaconf` instance built from a temporary TOML file). Prefer `Dynaconf(settings_files=[tmp_toml], environments=True, default_env="default", merge_enabled=True)` so `config.get(...)` semantics are real.
- No test makes a network call. Tests never set real keys.

## 12. Verified model facts

Retrieved 2026-11-03 unless stated.

### 12.1 OpenAI

| Fact | Value | Source |
|---|---|---|
| Current models | `gpt-6-astra` (flagship), `gpt-6.1-sol` (balanced), `gpt-6.1-terra`, `gpt-6-luna` (most efficient) | https://developers.openai.com/api/docs/models (redirected from platform.openai.com/docs/models) |
| Limits | All four: context 1,050,000; max input 922,000; max output 128,000 | https://developers.openai.com/api/docs/models/gpt-6-astra , …/gpt-6.1-sol , …/gpt-6.1-terra , …/gpt-6-luna |
| Endpoints | Chat Completions and Responses supported for all four; structured outputs listed as supported for all four | same model pages |
| Reasoning effort | astra/sol: low–max; terra/luna: also `none`; default `medium` | same model pages; https://developers.openai.com/api/docs/guides/reasoning |
| Prices (standard, per 1M in/out) | astra $10/$50; sol $2/$10; terra $1/$5; luna $0.10/$0.50; prompts >272K: 2× input, 1.5× output | https://developers.openai.com/api/docs/pricing |
| GPT-5.x prices | 5.6-sol $4/$20; 5.6-terra $2/$12; 5.6-luna $0.20/$1.20; 5.5 $5/$30; 5.4 $2.50/$15; 5.4-mini $0.75/$4.50; 5.4-nano $0.20/$1.25; 5.2 $1.75/$14; 5.1 $1.25/$10; 5 $1.25/$10; 5-mini $0.25/$2; 5-nano $0.05/$0.40 | https://developers.openai.com/api/docs/pricing |
| Structured outputs schema rules | `additionalProperties: false` on every object; all fields in `required`; optional via `null` union; root must be an object, not `anyOf`; ≤5000 properties, ≤10 nesting levels; ≤1000 enum values; unsupported: `allOf`, `not`, `if/then/else`, `dependentRequired`, `dependentSchemas`; unsupported keywords with `strict: true` error; refusals arrive in a `refusal` field | https://developers.openai.com/api/docs/guides/structured-outputs |
| Chat Completions JSON schema shape | `response_format={"type": "json_schema", "json_schema": {"name", "description", "schema", "strict"}}` | Installed SDK `openai` 2.29.0: `openai.types.shared_params.response_format_json_schema` (`JSONSchema` keys `name`, `description`, `schema`, `strict`) |
| SDK parameters | `AsyncCompletions.create` accepts `max_completion_tokens`, `max_tokens`, `reasoning_effort`, `response_format`, `temperature`; `ChatCompletionMessage.refusal` exists | Installed SDK 2.29.0 (inspected locally) |

### 12.2 Google Gemini

| Fact | Value | Source |
|---|---|---|
| Current models | `gemini-4-argon` (pro tier), `gemini-3.8-flash` (new), `gemini-3.6-flash` (stable), `gemini-3.5-flash-lite` (stable), `gemini-3.1-flash-lite` (stable), `gemini-3.1-pro-preview` | https://aistudio.google.com/docs/models (redirected from ai.google.dev/gemini-api/docs/models) |
| Deprecations | `gemini-2.5-flash` and `gemini-2.5-pro` deprecated; from 2026-12-01 they route to `gemini-3.5-flash-lite` and `gemini-3.8-flash`; `gemini-2.5-flash-lite` limited to existing users; `gemini-3-pro-preview`, `gemini-3.1-flash-lite-preview` shut down | same |
| Prices (paid, per 1M in/out, output includes thinking) | argon $2/$10 through 2026-11-30, then $4/$20; 3.8-flash and 3.6-flash $0.75/$3.75 through 2026-12-31, then $1.50/$7.50; 3.5-flash-lite $0.30/$2.50; 3.1-flash-lite $0.25/$1.50; 3.1-pro-preview $2/$12 (≤200K), $4/$18 (>200K) | https://aistudio.google.com/docs/pricing |
| Structured output (JSON Schema subset) | Supports `type` incl. `null` in type arrays, `properties`, `required`, `additionalProperties`, `enum`, `format` (date-time, date, time), `minimum`/`maximum`, `items`, `prefixItems`, `minItems`/`maxItems`, `$ref`/`$defs`, `anyOf`; ignored keywords are stripped, not errors; very large or deep schemas → 400 `INVALID_ARGUMENT` | https://aistudio.google.com/docs/structured-output |
| Python SDK shape | `client.aio.models.generate_content(...)`; config `response_mime_type="application/json"`, `response_json_schema=Model.model_json_schema()`; keys via `api_key=` or `GEMINI_API_KEY`/`GOOGLE_API_KEY` (GOOGLE wins when both are set); `http_options=types.HttpOptions(base_url=...)`; errors `errors.APIError` with `.code` | https://pypi.org/project/google-genai/ and https://github.com/googleapis/python-genai/blob/main/README.md |
| SDK version | `google-genai` 2.34.0, released 2026-10-29, requires Python ≥3.11 | https://pypi.org/project/google-genai/ |
| SDK fields | `GenerateContentConfig` has `temperature`, `max_output_tokens`, `response_mime_type`, `response_json_schema`, `system_instruction`, `thinking_config`; usage metadata has `prompt_token_count`, `candidates_token_count`, `thoughts_token_count`; `ThinkingConfig` has `include_thoughts`, `thinking_budget`, `thinking_level`; errors module has `APIError`, `ClientError`, `ServerError`; `GenerateContentResponse` has `parsed` and `text`; `HttpOptions` has `base_url` | Installed `google-genai` 2.34.0 in an isolated env, inspected locally |

### 12.3 Anthropic

| Fact | Value | Source |
|---|---|---|
| Current models | `claude-fable-5-1` ($10/$50), `claude-opus-5-5` ($4/$20), `claude-sonnet-5-5` ($2/$10), `claude-haiku-5-5` ($0.10/$0.50 ≤100K prompt; $0.50/$2.50 beyond); all 1M context; 128K max output | claude-api skill model table (cached 2026-10-06), consistent with the brief and `pricing.py` |
| Sampling | Fable 5.x, Opus 5.5/5, Opus 4.8/4.7, Sonnet 5: sampling params removed (400); Sonnet 5.5 and Haiku 5.5: non-default values 400 | claude-api skill thinking table |
| Forced tool choice | 400 on Fable 5.1, Opus 5.5, Sonnet 5.5 | claude-api skill |
| Structured outputs | `output_config.format` (`type: json_schema`) | claude-api skill; `odd/tasks/claude-5-5-models.md` |
| API version `2026-10-21` | Any `temperature`/`top_p`/`top_k` returns 400 on every model | claude-api skill. The installed SDK (0.86.0) does not send this version today; §5.5 adaptation covers a future upgrade |

### 12.4 Not verified (and how the code avoids depending on it)

| Claim | Status | Safe implementation |
|---|---|---|
| GPT-6 models reject `temperature` | Not stated in OpenAI docs; GPT-5 and o-series reject non-default values per community reports | Catalog omits `temperature` for `gpt-6*`, `gpt-5*`, `o*`; §5.5 adaptation handles the opposite case for unknown models |
| Gemini 3.5+/4 accept `temperature` | Not verified | Catalog omits `temperature` for Google (kind default `accepts_sampling_params=false`) |
| Whether Gemini `max_output_tokens` includes thinking tokens | Not verified | Floor of 16000 output tokens for Google models |
| `gemini-4-argon` max output ("65K / 1M" on the models page is ambiguous) | Ambiguous | `max_output_tokens` left unset (no clamp) |
| Context windows for Gemini models other than argon | Not stated | Left unset (informational only) |
| Quality tiers for every non-Anthropic model | Judgement from price and vendor positioning | Profiles labelled `provisional`; evals replace them |
| OpenAI Chat Completions JSON-schema guide example for current models | The structured-outputs guide page shows the Responses shape; the Chat Completions shape is from SDK types | Shape taken from SDK types (verified locally) |
| Ollama's OpenAI-compatible endpoint support for `json_schema` | Not verified | Ollama defaults to `json_object` (today's behaviour); the chain degrades further on rejection |
| OpenRouter model IDs for current models | Not verified | No `openrouter` profile; users set per-stage models |
| GPT-4.x prices in the catalog | Carried from the existing table, not re-verified | Kept for backward compatibility of `calculate_cost` |

## 13. Dependencies

| Package | Change | Minimum | Why |
|---|---|---|---|
| `google-genai` | add to `[project] dependencies` | `>=2.34.0` | Verified API surface (§12.2) |
| `openai` | none | `>=1.50` (installed 2.29.0) | JSON-schema `response_format` and `max_completion_tokens` exist |
| `anthropic` | none | `>=0.40` (installed 0.86.0) | `output_config`, `transform_schema` already used |

If `uv run mypy src/` reports missing stubs for `google.genai`, add `"google", "google.*"` to the existing `[[tool.mypy.overrides]] ignore_missing_imports` list. Run `uv lock` after editing dependencies and commit `uv.lock` with the change.

## 14. Compatibility and migration

- Configs with `[default.pipeline.stages.*] provider/model`: still valid; now honoured by `generate` (behaviour fix, documented).
- Configs with `[default.providers.<builtin>] api_key`: unchanged.
- `--preset concise|standard|comprehensive|budget|premium|default`, `--profile budget|premium|default`: unchanged names; models identical when no other config is set.
- `--provider openrouter` and other providers without a profile now fail fast with exit code 3 instead of sending Claude model IDs (they could not have worked).
- Python imports kept: `mkcv.core.models.pricing.MODEL_PRICING`, `calculate_cost`; `mkcv.adapters.llm.anthropic.uses_strict_request_rules`, `CLAUDE_5_MIN_MAX_TOKENS`; `mkcv.adapters.llm.openai.OpenAIAdapter`; `mkcv.core.models.profile_preset.resolve_preset`, `VALID_PRESET_NAMES`, `VALID_PROFILES`, `BUILT_IN_PRESETS`, `ContentDensity`, `Preset` (minus `stage_configs`).
- Removed: `mkcv.adapters.llm.ollama.OllamaAdapter`, `Preset.stage_configs`, `factory._PROVIDER_ENV_KEYS`, `factory._resolve_api_key`, `factory._resolve_preset`, `factory._resolve_stage_configs`, `factory._resolve_cl_stage_configs`. Tests referencing them are rewritten in the tasks that remove them.
- `StageMetadata`, `RunMetadata`, and artifact formats are unchanged.

## 15. Decisions the brief did not settle

1. Eval harness location: top-level `evals/` (D15).
2. Catalog format: Python data module for built-ins, TOML array of tables for user overrides, field-level overlay ordered by match specificity then origin (D6, §4.2–4.3).
3. Prices per 1M tokens with a derived per-1K `MODEL_PRICING` (D7).
4. Presets and model profiles are separate axes; profile names avoid `budget` (D8, D9).
5. Per-stage config beats profile; CLI beats both; `--model-profile` and `--provider` are mutually exclusive (D11, D12).
6. OpenAI uses Chat Completions; `OpenAIAdapter` subclasses the compatible adapter (D3, D4).
7. Conservative unknown-model defaults omit sampling params for the three native providers and keep them for compatible endpoints (§5.2).
8. Request adaptation on 400s naming `temperature`/`max_tokens`, cached per model per adapter instance (D20).
9. Warnings skip profile-sourced assignments except deprecation and missing keys (D14).
10. `ConfigurationError` with exit code 3 (D19).
11. Validation gets its own `validate` stage instead of borrowing the analyze provider with a hardcoded Sonnet model.
12. Catalog Gemini prices are post-promotion rates.
13. Evals isolate stages with committed, human-reviewed reference artifacts; recommendations are applied by hand from the report (D16, D17).
14. Eligibility gates and the "within 0.05 of best, then cheapest" recommendation rule (§9.9).
15. Cover-letter, KB, and validate stages are not evaluated in this change.
