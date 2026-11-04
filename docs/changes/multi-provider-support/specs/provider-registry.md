# Spec: Provider Registry and Stage Resolution

Design references: §5 (registry), §6 (stage resolution), §6.4 (`settings.toml` migration).

Unless a scenario says otherwise, "config" is a Dynaconf object built from the bundled `settings.toml` plus the TOML shown, and no `MKCV_*` or provider API-key environment variables are set.

## Provider registry

### REQ-PR-1: Built-in providers

The registry MUST contain exactly the built-in providers `anthropic`, `openai`, `google`, `openrouter`, `ollama`, and `stub` with the kinds, base URLs, and key env vars of design §5.2.

- **Given** an empty user config, **when** `ProviderRegistry.from_config(config, catalog).names()` is called, **then** it returns `("anthropic", "google", "ollama", "openai", "openrouter", "stub")`.
- **Given** an empty user config, **when** `registry.get("ollama")` is called, **then** the spec has kind `openai-compatible`, `base_url == "http://localhost:11434/v1"`, `requires_api_key is False`, and `defaults.structured_output == "json_object"`.

### REQ-PR-2: Unknown provider

- **Given** an empty user config, **when** `registry.get("groq")` is called, **then** `ConfigurationError` is raised, its `exit_code` is 3, and its message contains `Unknown LLM provider 'groq'` and every known provider name.

### REQ-PR-3: User-defined OpenAI-compatible provider

- **Given** config
  ```toml
  [default.providers.groq]
  type = "openai-compatible"
  base_url = "https://api.groq.com/openai/v1"
  api_key_env = "GROQ_API_KEY"
  structured_output = "json_object"
  ```
  **when** the registry is built, **then** `get("groq")` returns kind `openai-compatible`, `base_url` as given, `api_key_env == ("GROQ_API_KEY",)`, `requires_api_key is True`, and `defaults.structured_output == "json_object"`.
- **Given** the same config and `GROQ_API_KEY=gk-test`, **when** `create_adapter("groq", with_retry=False)` is called, **then** the result is an `OpenAICompatibleAdapter` whose client `base_url` starts with `https://api.groq.com/openai/v1`.

### REQ-PR-4: Invalid provider config

- **Given** `[default.providers.groq] base_url = "https://x"` with no `type`, **when** the registry is built, **then** `ConfigurationError` mentions `needs type`.
- **Given** `[default.providers.groq] type = "openai-compatible"` with no `base_url`, **then** `ConfigurationError` mentions `needs base_url`.
- **Given** `[default.providers.anthropic] type = "openai"`, **then** `ConfigurationError` mentions `cannot be changed`.
- **Given** `[default.providers.groq] type = "stub"`, **then** `ConfigurationError` is raised.
- **Given** `[default.providers.groq] type = "openai-compatible"`, `base_url = "https://x"`, `colour = "red"`, **then** `ConfigurationError` mentions `Unknown key 'colour'`.

### REQ-PR-5: API key resolution

- **Given** `[default.providers.anthropic] api_key = "from-config"` and `ANTHROPIC_API_KEY=from-env`, **when** `resolve_api_key("anthropic")` is called, **then** it returns `from-config`.
- **Given** no config key and `ANTHROPIC_API_KEY=from-env`, **then** it returns `from-env`.
- **Given** `GEMINI_API_KEY=g1` and `GOOGLE_API_KEY=g2`, **when** `resolve_api_key("google")` is called, **then** it returns `g1`.
- **Given** only `GOOGLE_API_KEY=g2`, **then** it returns `g2`.
- **Given** no keys at all, **then** `has_credentials("ollama")` is `True` and `has_credentials("openai")` is `False`.

### REQ-PR-6: Adapter creation without `if/elif` on names

- **Given** `OPENAI_API_KEY=sk-test`, **when** `create_adapter("openai")` is called, **then** it returns a `RetryingLLMAdapter` wrapping an `OpenAIAdapter`.
- **Given** `OPENAI_API_KEY=sk-test`, **when** `create_adapter("openai", with_retry=False)` is called, **then** it returns an `OpenAIAdapter`.
- **Given** no `OPENROUTER_API_KEY`, **when** `create_adapter("openrouter")` is called, **then** it returns a `StubLLMAdapter` and logs a warning containing `No API key for provider 'openrouter'`.
- **Given** no keys, **when** `create_adapter("ollama", with_retry=False)` is called, **then** it returns an `OpenAICompatibleAdapter` (no key needed).
- **When** `create_adapter("stub")` is called, **then** it returns an unwrapped `StubLLMAdapter`.
- `factory._create_llm_adapter(provider, config, with_retry=...)` MUST return the same types as `create_adapter` for the same inputs (existing factory tests keep passing after renaming expectations from `OllamaAdapter` to `OpenAICompatibleAdapter`).

### REQ-PR-7: Workspace README credentials block

- **When** a workspace is initialised, **then** its README credentials block lists Anthropic, OpenAI, Google Gemini (`export GEMINI_API_KEY=...`), and OpenRouter, with Ollama last, and never lists `stub`.

## Stage resolution

### REQ-SR-1: Defaults reproduce today's models

- **Given** an empty user config, **when** pipeline stages resolve with `preset_name="standard"`, **then** analyze/select/tailor/structure/review are `anthropic` with `claude-haiku-5-5`, `claude-opus-5-5`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, temperatures 0.2, 0.3, 0.5, 0.1, 0.3, and every source is `profile`.
- **Given** an empty user config and `preset_name="concise"`, **then** all five pipeline stages are `anthropic/claude-haiku-5-5`.
- **Given** an empty user config, **when** cover-letter stages resolve, **then** generate is `anthropic/claude-opus-5-5` at 0.6 and review is `anthropic/claude-haiku-5-5` at 0.2.
- **Given** an empty user config, **then** `kb` resolves to `anthropic/claude-sonnet-5-5` at 0.3 and `validate` to `anthropic/claude-sonnet-5-5` at 0.3.

### REQ-SR-2: Per-stage config wins over the profile

- **Given** `[default.pipeline.stages.tailor] provider = "openai"`, `model = "gpt-6.1-sol"`, **when** pipeline stages resolve with `preset_name="standard"`, **then** tailor is `openai/gpt-6.1-sol` with source `config` and the other four stages are unchanged from REQ-SR-1.
- **Given** `[default.pipeline.stages.tailor] model = "gpt-6.1-sol"` (no provider), **then** tailor's provider is `openai` (inferred from the catalog).
- **Given** `[default.pipeline.stages.tailor] model = "my-finetune"` (no provider, unknown to the catalog), **then** tailor's provider is the active profile's provider (`anthropic`).
- **Given** `[default.pipeline.stages.select] provider = "google"` (no model), **then** select is `google/gemini-4-argon` with source `config`.

### REQ-SR-3: Config-level profile and provider

- **Given** `[default.pipeline] model_profile = "openai"`, **then** the pipeline stages are `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6.1-terra`, `gpt-6.1-sol` on `openai`, and `profile_source == "config"`.
- **Given** `[default.pipeline] model_profile = "openai"` and `preset_name="concise"`, **then** the profile used is `openai-economy`.
- **Given** `[default.pipeline] provider = "google"`, **then** the profile used is `google` and `profile_source == "config"`.
- **Given** `[default.pipeline] model_profile = "nope"`, **then** `ConfigurationError` mentions `Unknown model profile 'nope'`.

### REQ-SR-4: CLI `--model-profile`

- **Given** `[default.pipeline.stages.tailor] provider = "openai"`, `model = "gpt-6.1-sol"`, **when** resolving with `model_profile="google"`, **then** every pipeline stage uses the `google` profile model (the per-stage config is ignored) and every source is `cli`.
- **When** resolving with `model_profile="google"` and `provider_override="openai"`, **then** `ConfigurationError` mentions `cannot be used together`.

### REQ-SR-5: CLI `--provider`

- **Given** an empty user config, **when** resolving pipeline stages with `provider_override="openai"`, **then** every stage uses the `openai` profile model on `openai` with source `cli`.
- **Given** `[default.pipeline.stages.tailor] provider = "openai"`, `model = "gpt-6-luna"`, **when** resolving with `provider_override="openai"`, **then** tailor is `openai/gpt-6-luna` with source `config`.
- **Given** `[default.pipeline.stages.tailor] provider = "anthropic"`, `model = "claude-sonnet-5-5"`, **when** resolving with `provider_override="openai"`, **then** tailor is `openai/gpt-6-astra` (config for another provider is ignored).
- **Given** an empty user config, **when** resolving with `provider_override="openrouter"`, **then** `ConfigurationError` starts with `Cannot resolve models:` and lists all five pipeline stages, each naming `[default.pipeline.stages.<stage>]`.
- **Given** `[default.providers.groq]` defined and `[default.pipeline.stages.*] provider = "groq"`, `model = "llama-3.3-70b-versatile"` for all five stages, **when** resolving with `provider_override="groq"`, **then** all five stages resolve from config.

### REQ-SR-6: Legacy presets and profiles

- **Given** an empty user config, **when** resolving pipeline stages with `preset_name="budget"`, **then** all five stages are `ollama/llama3.1:8b` and `profile_source == "preset"`.
- **Given** `preset_name="premium"`, **then** stages equal the `standard` result of REQ-SR-1.
- **Given** `preset_name="default"`, **then** stages equal the `standard` result of REQ-SR-1 (no preset; density context is empty).
- The `generate` CLI mapping `--profile budget` → preset `concise` + provider `ollama` MUST still produce all-`ollama/llama3.1:8b` stages.

### REQ-SR-7: KB overrides

- **When** the `kb` stage resolves with `model_override="gpt-6.1-sol"` and `provider_override="openai"`, **then** kb is `openai/gpt-6.1-sol` with source `cli`.
- **When** the `kb` stage resolves with `provider_override="google"` only, **then** kb is `google/gemini-3.8-flash`.

### REQ-SR-8: No hidden defaults

- `rg -n '"anthropic"|claude-' src/mkcv/adapters/factory.py` MUST return no matches.
- `DEFAULT_PROVIDER = "anthropic"` MUST be defined only in `src/mkcv/adapters/llm/stage_resolver.py`.
- The bundled `settings.toml` MUST NOT contain `provider =` or `model =` keys outside comments.
- Every `temperature` in the bundled `settings.toml` MUST equal `STAGE_REQUIREMENTS[stage].default_temperature`.

### REQ-SR-9: Validation uses its own stage

- **Given** `[default.validate] provider = "openai"`, `model = "gpt-6.1-terra"`, `OPENAI_API_KEY=sk-test`, **when** `create_validation_service(config)` runs, **then** the service's LLM wraps an `OpenAIAdapter` and its default model is `gpt-6.1-terra`.

### REQ-SR-10: Exit code

- **Given** an unresolvable configuration, **when** `mkcv generate` runs, **then** the process exits with code 3 and prints `Error:` followed by the `ConfigurationError` message, before any LLM call.
