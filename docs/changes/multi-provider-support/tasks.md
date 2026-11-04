# Tasks: Multi-Provider Support

Implement on branch `feat/multi-provider-support` (create it from `main`). Delivery is one pull request for the whole feature. Each task is one Conventional Commit with its tests and docs. Read `design.md` and the `specs/*.md` named in a task before starting it; the design is authoritative for names, fields, constants, and messages.

## Ground rules for every task

- Test first: write the listed tests, run them, and observe the stated RED before implementing. Record the RED and GREEN output in the commit body (one line each) and in `odd/tasks/multi-provider-support.md`.
- One class per file, absolute imports, full type hints, `mypy --strict` clean, no `print()`, never catch bare `Exception` in new code.
- Never call a real provider. Mock SDK clients as described in design §11.
- Do not touch files outside a task's list unless a check proves it is required; if so, add the file to the commit and note why in the feature document.
- About 400 changed lines per task is an advisory planning size only. Do not split, minify, or skip tests to fit it.
- Standard checks (run all four at the end of every task; all must pass):

  ```bash
  uv run ruff check src/ tests/
  uv run ruff format --check src/ tests/
  uv run mypy src/
  uv run pytest -q
  ```

  From T12 on, the lint and type checks also cover `evals/`:

  ```bash
  uv run ruff check src/ tests/ evals/
  uv run ruff format --check src/ tests/ evals/
  uv run mypy src/ evals/
  uv run pytest -q
  ```

## Dependency graph

```
T01 ─ T02 ─┬─ T03 ─┬─ T05 ─ T06
           └─ T04 ─┘    │
T01 ─ T07 ──────────────┴─ T08 ─ T09 ─ T10 ─ T11
                           T08 ─ T12 ─ T13 ─ T14 ─ T15 ─ T16 ─ T17
```

T05 needs T03 and T04. T06 (Google) needs T05. T07 needs only T01. T08 needs T05 and T07. T12 needs T08 (it uses the factory and stage keys). Execution order is the ID order T01 → T17 with one writer: T11 after T10 so the docs describe the final CLI, and P4 after T11.

---

## Phase 1: Registry, capability data, OpenAI-compatible, OpenAI structured outputs

### T01: Model capability catalog and catalog-derived pricing

- **Depends on**: none
- **Specs**: capability-registry.md REQ-CAT-1, 2, 3, 5, and the pricing parts of 7 (REQ-CAT-4 lookup logic is unit-tested here with hand-built catalogs; REQ-CAT-9 belongs to T04)
- **Design**: §3.1 (the four enums `ProviderKind`, `StructuredOutputMode`, `ModelTier`, `TokenParam`), §3.2–3.5, §3.7, §4.1, §4.3, §4.4
- **Files**:
  - Create: `src/mkcv/core/models/provider_kind.py`, `src/mkcv/core/models/structured_output_mode.py`, `src/mkcv/core/models/model_tier.py`, `src/mkcv/core/models/token_param.py`, `src/mkcv/core/models/capability_overlay.py`, `src/mkcv/core/models/model_capability.py`, `src/mkcv/core/models/resolved_model.py`, `src/mkcv/core/models/model_catalog.py`, `src/mkcv/core/catalog/__init__.py`, `src/mkcv/core/catalog/builtin_models.py`, `src/mkcv/core/exceptions/configuration.py`
  - Modify: `src/mkcv/core/models/pricing.py`, `src/mkcv/core/models/__init__.py` (export the new models following the file's existing pattern), `src/mkcv/core/exceptions/__init__.py`
  - Tests (create): `tests/test_core/test_models/test_model_catalog.py`, `tests/test_core/test_catalog/__init__.py`, `tests/test_core/test_catalog/test_builtin_models.py`
  - Tests (modify): `tests/test_core/test_models/test_pricing.py` (add new cases only; existing tests stay unchanged), `tests/test_core/test_exceptions.py` (ConfigurationError exit code 3)
- **Test first**: write `test_model_catalog.py` (overlay order, unknown model, canonical and vendor fallback, `output_limit`, `price_for`, `providers_for_model`, `resolve` raising `ValueError` on incomplete defaults) and the builtin data tests. RED: `ModuleNotFoundError: No module named 'mkcv.core.models.model_catalog'`.
- **Implementation notes**:
  - `ModelCatalog.builtin()` caches with `functools.cache` on a module-level function.
  - `MODEL_PRICING` is computed once at import from `BUILTIN_MODEL_CAPABILITIES` (design §4.4). Keep its type `dict[str, tuple[float, float]]`.
  - `calculate_cost(model, usage, catalog=None, *, provider=None)`; formula and rounding per §4.4.
  - `ModelCatalog.lookup`'s canonical/vendor fallback is implemented here even though providers arrive in T05.
  - `KIND_DEFAULTS` arrives in T02. For REQ-CAT-3 here, build the defaults overlay in the test from the design §5.2 table; T02's `test_builtin_providers.py` repeats REQ-CAT-3 with the real constant.
- **Acceptance**: REQ-CAT-1, 2, 3, 5 pass; `tests/test_core/test_models/test_pricing.py` passes unchanged plus new GPT-6/Gemini cost cases; `ConfigurationError("x").exit_code == 3`.
- **Verify**: `uv run pytest -q tests/test_core/test_models/test_model_catalog.py tests/test_core/test_catalog tests/test_core/test_models/test_pricing.py tests/test_core/test_exceptions.py` then the standard checks.
- **Commit**: `feat(core): add model capability catalog and derive pricing from it`

### T02: OpenAI-compatible adapter with structured-output fallback chain

- **Depends on**: T01
- **Specs**: openai-compatible-adapter.md REQ-OC-1 to OC-9; openai-adapter.md REQ-OAI-11 (strict schema)
- **Design**: §5.1, §5.2 (data only: `ProviderSpec`, `KIND_DEFAULTS`, `CANONICAL_PROVIDER`, `BUILTIN_PROVIDERS`), §5.4 (`ModelResolver`), §5.5, §7.2, §7.4, §7.5
- **Files**:
  - Create: `src/mkcv/adapters/llm/provider_spec.py`, `src/mkcv/adapters/llm/builtin_providers.py`, `src/mkcv/adapters/llm/model_resolver.py`, `src/mkcv/adapters/llm/request_adaptation.py`, `src/mkcv/adapters/llm/strict_schema.py`, `src/mkcv/adapters/llm/openai_compatible.py`
  - Tests (create): `tests/test_adapters/test_llm/test_builtin_providers.py`, `tests/test_adapters/test_llm/test_request_adaptation.py`, `tests/test_adapters/test_llm/test_strict_schema.py`, `tests/test_adapters/test_llm/test_openai_compatible.py`
- **Test first**: strict-schema tests parametrized over every response model in design §7.5 (find them with `rg -n "response_model=" src/mkcv/core/services`), request-adaptation message tests, and the compatible-adapter chain tests (mock `adapter._client.chat.completions.create` with `AsyncMock`; build SDK errors as in design §11). RED: `ModuleNotFoundError` for `mkcv.adapters.llm.strict_schema`, then behavioural failures.
- **Implementation notes**:
  - `model_resolver.py`: `type ModelResolver = Callable[[str, str], ResolvedModel]`; `def builtin_resolver(kind: ProviderKind) -> ModelResolver` resolving against `ModelCatalog.builtin()` with `KIND_DEFAULTS[kind]` and `CANONICAL_PROVIDER[kind]`.
  - `OpenAICompatibleAdapter.__init__` default `resolver=None` → `builtin_resolver(ProviderKind.OPENAI_COMPATIBLE)`.
  - Adaptation and degraded-mode state are per adapter instance (`dict[str, set[str]]` and `dict[str, StructuredOutputMode]`), not module globals.
  - Move `_augment_with_schema` logic (from `ollama.py`) into `openai_compatible.py` as a private function; do not delete `ollama.py` yet (T05 does).
  - Usage across a repair retry is summed (design §7.4).
- **Acceptance**: REQ-OC-1 to OC-9 and REQ-OAI-11 pass; no existing test changes.
- **Verify**: `uv run pytest -q tests/test_adapters/test_llm/test_strict_schema.py tests/test_adapters/test_llm/test_request_adaptation.py tests/test_adapters/test_llm/test_openai_compatible.py tests/test_adapters/test_llm/test_builtin_providers.py` then the standard checks.
- **Commit**: `feat(llm): add OpenAI-compatible adapter with structured-output fallback`

### T03: Native OpenAI adapter with strict structured outputs

- **Depends on**: T02
- **Specs**: openai-adapter.md REQ-OAI-1 to OAI-10
- **Design**: §7.3, §7.4, §7.5
- **Files**:
  - Rewrite: `src/mkcv/adapters/llm/openai.py` (`OpenAIAdapter(OpenAICompatibleAdapter)`, constructor `OpenAIAdapter(api_key, *, base_url=None, resolver=None, provider_name="openai")`, default resolver `builtin_resolver(ProviderKind.OPENAI)`)
  - Rewrite: `tests/test_adapters/test_llm/test_openai.py`
- **Test first**: rewrite `test_openai.py` per REQ-OAI-1 to 10. RED: request has `response_format={"type": "json_object"}` and `temperature`/`max_tokens` instead of the strict schema and `max_completion_tokens`.
- **Implementation notes**: the subclass needs no method overrides if the parent already implements refusal and truncation handling (design §7.3). `factory.py` still constructs `OpenAIAdapter(api_key=..., base_url=...)` for `openai` and `openrouter` until T05; keep those keyword arguments working.
- **Acceptance**: REQ-OAI-1 to 10 pass; `tests/test_adapters/test_llm/test_factory.py` still passes.
- **Verify**: `uv run pytest -q tests/test_adapters/test_llm/test_openai.py tests/test_adapters/test_llm/test_factory.py` then the standard checks.
- **Commit**: `feat(llm): use strict JSON-schema structured outputs for OpenAI`

### T04: Capability-driven Anthropic request shaping

- **Depends on**: T02 (uses `request_adaptation.py` and `model_resolver.py`)
- **Specs**: capability-registry.md REQ-CAT-9
- **Design**: §7.1, §5.5
- **Files**:
  - Modify: `src/mkcv/adapters/llm/anthropic.py`
  - Modify: `tests/test_adapters/test_llm/test_anthropic.py`
- **Test first**: add tests: (a) `uses_strict_request_rules` table from REQ-CAT-9; (b) a resolver returning `structured_output=TOOL`, `accepts_sampling_params=True` for a fictional model `claude-test-1` produces a forced-tool request with `temperature`; (c) a resolver returning `JSON_SCHEMA`, `accepts_sampling_params=False`, `min_output_tokens=16000` produces an `output_config` request without `temperature` and with `max_tokens=16000`; (d) a first `anthropic.BadRequestError` naming `temperature` on a 4.x model triggers one retry without `temperature`. RED: `TypeError: __init__() got an unexpected keyword argument 'resolver'`.
- **Implementation notes**: delete `_STRICT_REQUEST_PREFIXES`; keep `uses_strict_request_rules` and `CLAUDE_5_MIN_MAX_TOKENS` exported. Existing request-shape tests for 5.x and 4.x models must pass without changing their expected payloads.
- **Acceptance**: REQ-CAT-9 passes; all pre-existing Anthropic tests pass with only constructor-call edits where needed.
- **Verify**: `uv run pytest -q tests/test_adapters/test_llm/test_anthropic.py` then the standard checks.
- **Commit**: `refactor(llm): drive Anthropic request rules from the capability catalog`

### T05: Provider registry, catalog overrides, and factory dispatch

- **Depends on**: T03, T04
- **Specs**: provider-registry.md REQ-PR-1 to PR-7; capability-registry.md REQ-CAT-4 (registry use), REQ-CAT-6, REQ-CAT-8; openai-compatible-adapter.md REQ-OC-10
- **Design**: §4.2, §5.3, §5.4, §4.4 (service catalog injection)
- **Files**:
  - Create: `src/mkcv/adapters/llm/provider_registry.py`, `src/mkcv/adapters/llm/model_catalog_loader.py`
  - Modify: `src/mkcv/adapters/factory.py` (`_create_llm_adapter` delegates to the registry; delete `_PROVIDER_ENV_KEYS` and `_resolve_api_key`; pass `catalog=` to `PipelineService` and `CoverLetterService`), `src/mkcv/core/services/pipeline.py`, `src/mkcv/core/services/cover_letter.py` (keyword-only `catalog` argument; `calculate_cost(..., self._catalog, provider=...)`), `src/mkcv/adapters/filesystem/workspace_manager.py` (`_build_readme` iterates `BUILTIN_PROVIDERS`; Google hint)
  - Delete: `src/mkcv/adapters/llm/ollama.py`, `tests/test_adapters/test_llm/test_ollama.py` (port any behaviour not already covered to `test_openai_compatible.py`, e.g. the connection-error message and the no-system-message case)
  - Tests (create): `tests/test_adapters/test_llm/test_provider_registry.py`, `tests/test_adapters/test_llm/test_model_catalog_loader.py`
  - Tests (modify): `tests/test_adapters/test_llm/test_factory.py` (expect `OpenAICompatibleAdapter` for `ollama`), `tests/test_adapters/test_workspace_manager.py` (README hints), `tests/test_core/test_services/test_pipeline.py` and `tests/test_core/test_services/test_cover_letter.py` (catalog injection, REQ-CAT-8), plus any test that `rg -n "OllamaAdapter|_PROVIDER_ENV_KEYS|_resolve_api_key" tests` finds
- **Test first**: registry tests using a real `Dynaconf` built from a temporary TOML (design §11); loader tests for overlay and validation errors; factory test for `ollama` → `OpenAICompatibleAdapter`. RED: `ModuleNotFoundError: No module named 'mkcv.adapters.llm.provider_registry'`.
- **Implementation notes**:
  - `_BUILDERS` maps `ProviderKind` → builder function; the `GOOGLE` builder raises `ConfigurationError("The google provider is not available yet")` until T06.
  - `factory._registry(config)` builds the registry per call; no module-level cache (config can change between commands in tests).
  - Unknown provider names now raise `ConfigurationError` instead of `AuthenticationError`; update the affected factory test.
- **Acceptance**: REQ-PR-1 to 7, REQ-CAT-6, REQ-CAT-8, REQ-OC-10 pass; `rg -n "elif provider ==" src/mkcv/adapters/factory.py` returns nothing; `src/mkcv/adapters/llm/ollama.py` is gone.
- **Verify**: `uv run pytest -q tests/test_adapters tests/test_core/test_services/test_pipeline.py tests/test_core/test_services/test_cover_letter.py` then the standard checks.
- **Commit**: `feat(llm): add provider registry with config-defined providers and catalog overrides`

---

## Phase 2: Google Gemini

### T06: Google Gemini adapter

- **Depends on**: T05
- **Specs**: google-adapter.md REQ-GG-1 to GG-10
- **Design**: §7.6, §12.2, §13
- **Files**:
  - Modify: `pyproject.toml` (add `"google-genai>=2.34.0"` to `[project] dependencies`; add `"google", "google.*"` to the mypy `ignore_missing_imports` override only if `mypy` reports missing stubs), `uv.lock` (run `uv lock`)
  - Create: `src/mkcv/adapters/llm/google.py`
  - Modify: `src/mkcv/adapters/llm/provider_registry.py` (real `GOOGLE` builder)
  - Tests (create): `tests/test_adapters/test_llm/test_google.py`
  - Tests (modify): `tests/test_adapters/test_llm/test_provider_registry.py` (REQ-GG-9)
- **Test first**: after `uv add`/`uv lock`, write `test_google.py` with `AsyncMock` on `adapter._client.aio.models.generate_content`. Confirm the `errors.ClientError` constructor with `uv run python -c "import inspect; from google.genai import errors; print(inspect.signature(errors.ClientError.__init__))"` before writing error tests. RED: `ModuleNotFoundError: No module named 'mkcv.adapters.llm.google'`.
- **Implementation notes**: default `resolver=None` → `builtin_resolver(ProviderKind.GOOGLE)`; convert messages per REQ-GG-2; the lazy-import test (REQ-GG-9) runs a subprocess with `sys.executable`.
- **Acceptance**: REQ-GG-1 to 10 pass.
- **Verify**: `uv run pytest -q tests/test_adapters/test_llm/test_google.py tests/test_adapters/test_llm/test_provider_registry.py` then the standard checks.
- **Commit**: `feat(llm): add Google Gemini adapter using google-genai structured output`

---

## Phase 3: Profiles, stage resolution, `mkcv models`, warnings, docs

### T07: Stage keys, stage requirements, and built-in model profiles

- **Depends on**: T01
- **Specs**: presets-models-command.md REQ-MP-1
- **Design**: §3.1 (`StageKey` and its constants), §3.6 (`StageRequirement`, `ModelProfile`, `StageAssignment`), §6.1, §6.2
- **Files**:
  - Create: `src/mkcv/core/models/stage_key.py`, `src/mkcv/core/models/stage_requirement.py`, `src/mkcv/core/models/model_profile.py`, `src/mkcv/core/models/stage_assignment.py`, `src/mkcv/core/catalog/stage_requirements.py`, `src/mkcv/core/catalog/builtin_model_profiles.py`
  - Modify: `src/mkcv/core/models/__init__.py` (exports)
  - Tests (create): `tests/test_core/test_catalog/test_stage_requirements.py`, `tests/test_core/test_catalog/test_builtin_model_profiles.py`, `tests/test_core/test_models/test_stage_assignment.py`
- **Test first**: profile table tests (REQ-MP-1, including "every profile model has a catalog entry"), helper function tests, `StageAssignment.to_stage_config()`. RED: `ModuleNotFoundError` for `mkcv.core.catalog.builtin_model_profiles`.
- **Acceptance**: REQ-MP-1 passes. No behaviour change elsewhere.
- **Verify**: `uv run pytest -q tests/test_core/test_catalog tests/test_core/test_models/test_stage_assignment.py` then the standard checks.
- **Commit**: `feat(core): add stage requirements and recommended model profiles`

### T08: Stage resolver, preset split, and settings migration

- **Depends on**: T05, T07
- **Specs**: provider-registry.md REQ-SR-1 to SR-10; presets-models-command.md REQ-MP-2
- **Design**: §6.3–§6.6, §3.7
- **Files**:
  - Create: `src/mkcv/adapters/llm/resolution_request.py`, `src/mkcv/adapters/llm/resolved_stages.py`, `src/mkcv/adapters/llm/stage_resolver.py`
  - Modify: `src/mkcv/core/models/profile_preset.py` (drop `stage_configs`, add `economy`, `provider`), `src/mkcv/config/settings.toml` (§6.4), `src/mkcv/adapters/factory.py` (§6.6: rewire every `create_*`; add `model_profile` parameters; delete `_resolve_preset`, `_resolve_stage_configs`, `_resolve_cl_stage_configs`, `_STAGE_CONFIG_KEYS`, `_CL_STAGE_CONFIG_KEYS`, all `"anthropic"`/`claude-` literals), `src/mkcv/core/services/validation.py` (constructor `model`), `src/mkcv/core/services/pipeline.py` only if it references `preset.stage_configs` (check with `rg -n "stage_configs" src/mkcv/core/services/pipeline.py`)
  - Tests (create): `tests/test_adapters/test_llm/test_stage_resolver.py`, `tests/test_config/test_settings_defaults.py` (REQ-SR-8 temperature equality and no `provider =`/`model =` keys)
  - Tests (modify): `tests/test_adapters/test_llm/test_factory.py` (replace `_resolve_preset`/`_resolve_stage_configs` tests with resolver-based expectations; `test_budget_preset_ignores_config_settings` now asserts the budget preset still yields all-Ollama stages when config sets stages for another provider), `tests/test_core/test_models/test_profile_preset.py`, `tests/test_core/test_services/test_validation.py`, `tests/test_core/test_services/test_workspace_service.py` if it references removed symbols, and anything `rg -n "stage_configs|_resolve_stage_configs|_resolve_preset" tests` finds that refers to presets
- **Test first**: `test_stage_resolver.py` covering every REQ-SR scenario with a real `Dynaconf` from temporary TOML files; RED: `ModuleNotFoundError: No module named 'mkcv.adapters.llm.stage_resolver'`. Then a factory test proving REQ-SR-2 end to end: `create_pipeline_service(config, preset_name="standard")` with a tailor override yields `stage_configs[3].model == "gpt-6.1-sol"` (RED today because the preset wins).
- **Implementation notes**:
  - Read config with `config.get("<dotted.path>")` so missing sections return `None`.
  - `generate.py` and `cover_letter.py` CLI do not change in this task (new factory parameters default to `None`).
  - `ConfigurationError` raised during factory calls propagates to `meta_handler` (exit 3).
- **Acceptance**: REQ-SR-1 to 10 and REQ-MP-2 pass; `rg -n '"anthropic"|claude-' src/mkcv/adapters/factory.py` returns nothing; `rg -n "^\s*(provider|model)\s*=" src/mkcv/config/settings.toml` returns nothing.
- **Verify**: `uv run pytest -q tests/test_adapters/test_llm/test_stage_resolver.py tests/test_adapters/test_llm/test_factory.py tests/test_config tests/test_core/test_models/test_profile_preset.py tests/test_core/test_services/test_validation.py tests/test_cli` then the standard checks.
- **Commit**: `feat(config): resolve stage models from profiles with per-stage overrides`

### T09: Model advisor, generation warnings, and `--model-profile`

- **Depends on**: T08
- **Specs**: presets-models-command.md REQ-MP-3 to MP-12
- **Design**: §3.1 (`ModelWarningKind`), §3.6 (`ModelWarning`, `StageAdvice`, `ModelReport`), §6.7, §8.1–§8.3
- **Files**:
  - Create: `src/mkcv/core/models/model_warning_kind.py`, `src/mkcv/core/models/model_warning.py`, `src/mkcv/core/models/stage_advice.py`, `src/mkcv/core/models/model_report.py`, `src/mkcv/core/services/model_advisor.py`, `src/mkcv/cli/model_warnings.py`
  - Modify: `src/mkcv/adapters/factory.py` (`create_model_report`), `src/mkcv/cli/commands/generate.py` (`--model-profile`, `--provider` help, warnings, pass-through to every factory call), `src/mkcv/cli/commands/cover_letter.py` (same), `src/mkcv/core/models/__init__.py` (exports)
  - Tests (create): `tests/test_core/test_services/test_model_advisor.py`, `tests/test_cli/test_model_warnings.py`
  - Tests (modify): `tests/test_cli/test_generate.py`, `tests/test_cli/test_cover_letter_command.py`, `tests/test_adapters/test_llm/test_factory.py` (`create_model_report`)
- **Test first**: advisor unit tests for every warning kind and cost rule (pure core, no config), then CLI tests with factory functions patched. RED: `ModuleNotFoundError: No module named 'mkcv.core.services.model_advisor'`.
- **Implementation notes**: `generate.py` is large; add only the flag, the pass-through, and one call to `print_model_warnings` right after `_resolve_preset_and_provider`. Keep warning text in `ModelAdvisor` and the factory, not in the CLI.
- **Acceptance**: REQ-MP-3 to 12 pass.
- **Verify**: `uv run pytest -q tests/test_core/test_services/test_model_advisor.py tests/test_cli/test_model_warnings.py tests/test_cli/test_generate.py tests/test_cli/test_cover_letter_command.py tests/test_adapters/test_llm/test_factory.py` then the standard checks.
- **Commit**: `feat(cli): warn about weak or unknown stage models and add --model-profile`

### T10: `mkcv models` command

- **Depends on**: T09
- **Specs**: presets-models-command.md REQ-MP-13 to MP-15
- **Design**: §8.4
- **Files**:
  - Create: `src/mkcv/cli/commands/models.py`
  - Modify: `src/mkcv/cli/app.py` (register `models`; update the module docstring's command list)
  - Tests (create): `tests/test_cli/test_models_command.py`
- **Test first**: CLI tests for the default view, each flag, JSON outputs, and exit code 3. RED: `mkcv models` is an unknown command.
- **Implementation notes**: render with Rich `Table` on the module's stdout console (follow `themes.py`/`status.py` patterns); set a wide console in tests (`Console(width=200)`) so rows are not wrapped when asserting text.
- **Acceptance**: REQ-MP-13 to 15 pass; `uv run mkcv models --help` exits 0.
- **Verify**: `uv run pytest -q tests/test_cli/test_models_command.py tests/test_cli/test_app.py`; `uv run mkcv models --profiles` (manual smoke, no keys needed); then the standard checks.
- **Commit**: `feat(cli): add mkcv models command`

### T11: Provider and model documentation

- **Depends on**: T10
- **Specs**: presets-models-command.md REQ-MP-16
- **Design**: §10, §14, §12
- **Files**:
  - Create: `docs/models.md`
  - Modify: `README.md` (feature bullet, setup, provider section, presets/profiles section, per-stage config example), `docs/specs/cli-interface.md` (`mkcv models`, `--model-profile`, `--provider`, exit code 3, env vars `GEMINI_API_KEY`/`GOOGLE_API_KEY`), `docs/specs/architecture.md` (registry, catalog, resolver, advisor), `docs/specs/data-models.md` (catalog, profile, stage, report models), `AGENTS.md` (providers line; `models` command row), `src/mkcv/adapters/filesystem/workspace_manager.py` (workspace `mkcv.toml` template: `pipeline.model_profile`/`provider` comments, Google and custom-provider examples, `[[default.model_catalog]]` example; workspace README presets section uses `--preset` and `--model-profile`, not `--profile`; OpenRouter example uses `--model-profile`-free per-stage models)
  - Tests (modify): `tests/test_adapters/test_workspace_manager.py` only where it asserts template text
- **Test first**: passive documentation is exempt from RED; for the template change, update or add a workspace-manager test asserting the template contains `model_profile` and `[default.providers.google]`, and observe it fail first.
- **Implementation notes**: label every profile "provisional" in `docs/models.md`; include the precedence order from design §6.5 as a numbered list; include the verified facts table (copy §12 rows that users need: model IDs, prices, promo dates) with source links and the retrieval date 2026-11-03. Do not edit `CLAUDE.md` (owner-maintained); list the stale provider line there in the feature document as a follow-up.
- **Acceptance**: REQ-MP-16; `rg -n "\-\-profile" README.md` returns only a deprecation note, if anything.
- **Verify**: `uv run pytest -q tests/test_adapters/test_workspace_manager.py` then the standard checks; read `docs/models.md` rendered in a Markdown viewer or `bat` for structure.
- **Commit**: `docs: document providers, model profiles, and mkcv models`

---

## Phase 4: Eval harness

### T12: Eval package scaffolding, models, case loading, and cost estimate

- **Depends on**: T08
- **Specs**: eval-harness.md REQ-EV-1, REQ-EV-21
- **Design**: §9.1–§9.3, §9.8 (`list-cases`, `estimate`)
- **Files**:
  - Create: `evals/__init__.py`, `evals/__main__.py`, `evals/cli.py`, `evals/config/matrix.toml`, `evals/models/__init__.py`, `evals/models/eval_case.py`, `evals/models/matrix_model.py`, `evals/models/judge_config.py`, `evals/models/run_settings.py`, `evals/models/matrix_config.py`, `evals/models/grade.py`, `evals/models/eval_record.py`, `evals/models/run_manifest.py`, `evals/harness/__init__.py`, `evals/harness/case_loader.py`, `evals/harness/cost_estimator.py`
  - Modify: `pyproject.toml` (`[tool.pytest.ini_options] pythonpath = ["."]`), `.gitignore` (`evals/results/*`, `!evals/results/published/`), `.github/workflows/ci.yml` (ruff check/format on `src/ tests/ evals/`; mypy on `src/ evals/`)
  - Tests (create): `tests/test_evals/__init__.py`, `tests/test_evals/conftest.py` (autouse env scrub per design §9.10; a `tmp_fixtures` fixture writing a two-case `cases.toml` with tiny persona/JD files), `tests/test_evals/test_case_loader.py`, `tests/test_evals/test_cost_estimator.py`, `tests/test_evals/test_cli.py`
- **Test first**: loader, matrix parsing, estimate (REQ-EV-21), and `python -m evals --help` (subprocess). RED: `ModuleNotFoundError: No module named 'evals'`.
- **Implementation notes**: use `argparse` with subcommands; `main(argv: list[str] | None = None) -> int`. Commands not yet implemented (`run`, `report`, `bootstrap-reference`) are registered and print `not implemented yet` with exit 2 until T13/T17 replace them. Estimate uses `mkcv.config.settings` → `load_model_catalog` so user catalog overrides apply.
- **Acceptance**: REQ-EV-1 (help and CI parts), REQ-EV-21 pass; `uv build --wheel` output contains no `evals/` paths (check with `uv run python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); assert not [n for n in z.namelist() if n.startswith('evals/')]"`, then delete `dist/`).
- **Verify**: `uv run pytest -q tests/test_evals` then the P4 standard checks.
- **Commit**: `feat(evals): scaffold offline eval harness with case loading and cost estimate`

### T13: Stage-isolated runner and `run` / `bootstrap-reference` commands

- **Depends on**: T12
- **Specs**: eval-harness.md REQ-EV-3 to EV-6, REQ-EV-19 (files written by the runner), REQ-EV-20
- **Design**: §9.5, §9.8, §6.6 (`create_pipeline_service_for_stage_configs`)
- **Files**:
  - Modify: `src/mkcv/adapters/factory.py` (add `create_pipeline_service_for_stage_configs`), `evals/cli.py` (`run`, `bootstrap-reference`)
  - Create: `evals/harness/stop_after_stage.py`, `evals/harness/stage_runner.py`, `evals/harness/eval_runner.py`, `evals/harness/reference_bootstrapper.py`, `evals/harness/stage_run.py` (the `StageRun` result model)
  - Tests (create): `tests/test_evals/fixtures/recorded/backend-platform-match/` (hand-written valid `stage1_analysis`, `stage2_selection`, `stage3_content`, `stage4_structure` artifacts and `resume.yaml`, using the exact file names and formats `FileSystemArtifactStore` writes), `tests/test_evals/test_stage_runner.py`, `tests/test_evals/test_eval_runner.py`, `tests/test_adapters/test_llm/test_factory.py` (new factory function)
- **Test first**: stage runner with a `StubLLMAdapter` configured with canned responses, injected by patching `ProviderRegistry.create_adapter` to return the stub; RED: `ModuleNotFoundError` for `evals.harness.stage_runner`.
- **Implementation notes**:
  - Read `src/mkcv/adapters/filesystem/artifact_store.py` and `PipelineService._review` to confirm artifact file names/extensions and whether stage 5 reads `resume.yaml`; copy references accordingly.
  - `EvalRunner` writes `results.jsonl` incrementally (append + flush per record) and `run.json`; graders are looked up from a `STAGE_GRADERS` mapping that is empty until T15 (records carry `grades=[]`).
  - Concurrency via `asyncio.Semaphore(run.concurrency)`.
  - Exit code 2 paths per REQ-EV-20.
- **Acceptance**: REQ-EV-3 to 6 and REQ-EV-20 pass; REQ-EV-19's `results.jsonl` and `run.json` are written (summary/report arrive in T17).
- **Verify**: `uv run pytest -q tests/test_evals tests/test_adapters/test_llm/test_factory.py` then the P4 standard checks.
- **Commit**: `feat(evals): run pipeline stages in isolation across a model matrix`

### T14: Synthetic eval fixtures

- **Depends on**: T13
- **Specs**: eval-harness.md REQ-EV-2
- **Design**: §9.4
- **Files**:
  - Create: `evals/fixtures/cases.toml`, `evals/fixtures/personas/backend-engineer.md`, `evals/fixtures/personas/product-switcher.md`, `evals/fixtures/personas/data-scientist.md`, `evals/fixtures/jds/backend-platform-match.md`, `evals/fixtures/jds/backend-ml-stretch.md`, `evals/fixtures/jds/product-pm-match.md`, `evals/fixtures/jds/product-growth-stretch.md`, `evals/fixtures/jds/data-analytics-match.md`, `evals/fixtures/jds/data-mlops-stretch.md`, `evals/fixtures/reference/review-probe/` (hand-written `stage4_structure` artifact and `resume.yaml` with the three seeded defects)
  - Tests (create): `tests/test_evals/test_fixtures.py`
- **Test first**: `test_fixtures.py` encoding REQ-EV-2 (seven cases, files exist, line-count ranges, forbidden-claim placement, no real contact data). RED: `FileNotFoundError` for `evals/fixtures/cases.toml`.
- **Implementation notes**: follow the persona rules in design §9.4 exactly (names, fictional employers, `example.com`, `555-01xx`). Make the backend persona's metrics varied (percentages, currency, counts, latency) so number extraction is exercised. The probe YAML must otherwise be clean and valid for RenderCV.
- **Acceptance**: REQ-EV-2 passes.
- **Verify**: `uv run pytest -q tests/test_evals/test_fixtures.py` then the P4 standard checks.
- **Commit**: `test(evals): add synthetic personas, job descriptions, and review probe`

### T15: Deterministic graders

- **Depends on**: T14
- **Specs**: eval-harness.md REQ-EV-7 to EV-11
- **Design**: §9.6 (deterministic graders)
- **Files**:
  - Create: `evals/graders/__init__.py`, `evals/graders/grader.py`, `evals/graders/grading_context.py`, `evals/graders/text_normalization.py`, `evals/graders/schema_grader.py`, `evals/graders/jd_recall_grader.py`, `evals/graders/ats_rules_grader.py`, `evals/graders/structure_grader.py`, `evals/graders/faithfulness_extraction_grader.py`, `evals/graders/stage_graders.py`
  - Modify: `evals/harness/eval_runner.py` (call the graders from `STAGE_GRADERS` for `ok` records)
  - Tests (create): `tests/test_evals/test_schema_grader.py`, `tests/test_evals/test_jd_recall_grader.py`, `tests/test_evals/test_ats_rules_grader.py`, `tests/test_evals/test_structure_grader.py`, `tests/test_evals/test_faithfulness_extraction_grader.py`; recorded failing variants under `tests/test_evals/fixtures/recorded/` (one YAML per ATS rule failure; a stage-3 artifact with a fabricated `$2.4M` and a forbidden claim)
- **Test first**: grader tests on recorded outputs. RED: `ModuleNotFoundError` for `evals.graders.schema_grader`.
- **Implementation notes**: `STAGE_GRADERS` lists judge graders too, but they are added in T16; here register only deterministic ones and keep `PRIMARY_METRIC` per design §9.6.
- **Acceptance**: REQ-EV-7 to 11 pass; `test_eval_runner.py` gains one assertion that an `ok` tailor record carries `schema` and `faithfulness_extraction` grades.
- **Verify**: `uv run pytest -q tests/test_evals` then the P4 standard checks.
- **Commit**: `feat(evals): add schema, ATS, structure, and faithfulness extraction graders`

### T16: LLM-judge graders and rubrics

- **Depends on**: T15
- **Specs**: eval-harness.md REQ-EV-12 to EV-15
- **Design**: §9.6 (judge graders), §9.7
- **Files**:
  - Create: `evals/models/faithfulness_verdict.py`, `evals/models/faithfulness_judgement.py`, `evals/models/criterion_score.py`, `evals/models/rubric_judgement.py`, `evals/models/defect_finding.py`, `evals/models/defect_judgement.py`, `evals/harness/judge_factory.py`, `evals/graders/faithfulness_judge_grader.py`, `evals/graders/selection_judge_grader.py`, `evals/graders/tailoring_judge_grader.py`, `evals/graders/review_defect_grader.py`, `evals/graders/rubrics/faithfulness.md`, `evals/graders/rubrics/selection.md`, `evals/graders/rubrics/tailoring.md`, `evals/graders/rubrics/review_defects.md`
  - Modify: `evals/graders/stage_graders.py` (register judge graders), `evals/harness/eval_runner.py` (create the judge once per run; `--judge` override), `evals/cli.py` (`--judge` parsing)
  - Tests (create): `tests/test_evals/test_judge_graders.py`
- **Test first**: judge graders with a `StubLLMAdapter` judge returning canned judgements. RED: `ModuleNotFoundError` for `evals.graders.faithfulness_judge_grader`.
- **Implementation notes**: the judge's own request rules come from the registry (so `temperature=0.0` is dropped for judges that reject sampling). Rubric text per design §9.7; each rubric starts with "Return only the JSON object for the requested schema."
- **Acceptance**: REQ-EV-12 to 15 pass.
- **Verify**: `uv run pytest -q tests/test_evals` then the P4 standard checks.
- **Commit**: `feat(evals): add LLM-judge graders for faithfulness, tailoring, and review`

### T17: Aggregation, recommendations, report, and eval docs

- **Depends on**: T16
- **Specs**: eval-harness.md REQ-EV-16 to EV-19, REQ-EV-22
- **Design**: §9.8 (`report`, `--publish`), §9.9
- **Files**:
  - Create: `evals/models/stage_summary.py`, `evals/models/recommendation.py`, `evals/report/__init__.py`, `evals/report/aggregator.py`, `evals/report/recommender.py`, `evals/report/markdown_report.py`, `evals/README.md`, `evals/results/published/.gitkeep`
  - Modify: `evals/cli.py` (`report` command, `--publish`; `run` calls aggregation and report at the end), `evals/harness/eval_runner.py` (write `summary.json` and `report.md`), `docs/models.md` ("How recommendations are made" section), `docs/DEVELOPMENT.md` (one short section pointing to `evals/README.md`)
  - Tests (create): `tests/test_evals/test_aggregator.py`, `tests/test_evals/test_recommender.py`, `tests/test_evals/test_markdown_report.py`
  - Tests (modify): `tests/test_evals/test_cli.py` (`report --publish`), `tests/test_evals/test_eval_runner.py` (four output files)
- **Test first**: aggregator, recommender, and report tests on synthetic `EvalRecord` lists. RED: `ModuleNotFoundError` for `evals.report.aggregator`.
- **Implementation notes**: "Suggested profile changes" compares recommendations with `BUILTIN_MODEL_PROFILES` (stage models for the matching provider; non-economy profile vs `recommended`, economy profile vs `economy`). The token-estimate table compares median tokens per stage with `STAGE_REQUIREMENTS`.
- **Acceptance**: REQ-EV-16 to 19 and REQ-EV-22 pass; the full offline flow works: `uv run python -m evals run --yes` with every provider key absent exits 0, skips every model with warnings, and still writes the four files (report shows no rows).
- **Verify**: `uv run pytest -q tests/test_evals`; `uv run python -m evals estimate`; then the P4 standard checks.
- **Commit**: `feat(evals): aggregate results, recommend models, and render the eval report`

---

## After T17 (owner action, not part of autonomous implementation)

1. Export keys for the providers to evaluate.
2. `uv run python -m evals bootstrap-reference --yes`; review every file under `evals/fixtures/reference/` for fabricated facts; commit.
3. `uv run python -m evals run --yes`; read `report.md`; `uv run python -m evals report <dir> --publish`.
4. Apply "Suggested profile changes" to `src/mkcv/core/catalog/builtin_model_profiles.py` (set `evidence="eval"`, `eval_run`) and `docs/models.md`; commit as `feat(catalog): adopt eval-backed model recommendations`.
