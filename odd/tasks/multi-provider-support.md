# Feature: Multi-provider support

Blueprint: `docs/changes/multi-provider-support/` (`proposal.md`, `design.md`, `specs/*.md`, `tasks.md`). The design is authoritative for names, fields, constants, and messages; this document tracks progress.

## Objective

Make mkcv provider-agnostic: any stage can run on Anthropic, OpenAI, Google Gemini, or any OpenAI-compatible endpoint. Users see mkcv's recommended model per stage, get non-blocking warnings for weak or unknown models, and keep full per-stage control. An offline eval harness produces the evidence for the recommendations.

## Problem

- OpenAI uses JSON mode with no schema enforcement; Google is unsupported; Ollama and OpenRouter are special cases.
- `adapters/factory.py` dispatches providers with `if/elif` and hardcodes `"anthropic"` / `"claude-sonnet-5-5"` fallbacks in many places.
- `mkcv generate` always resolves a preset (`standard` by default) and the preset replaces per-stage `provider`/`model` from `mkcv.toml`, so documented per-stage overrides are ignored.
- `validate` sends a hardcoded Claude model to whichever provider the analyze stage uses.
- No data says which models are good enough per stage.

## Scope

In: provider registry; model capability catalog with config overrides and catalog-derived pricing; OpenAI strict structured outputs; generic OpenAI-compatible adapter with fallback chain; Google Gemini adapter (`google-genai`); model profiles and one stage resolver; `--model-profile`; `mkcv models`; generation warnings; docs; offline eval harness with fixtures, graders, and report.

Out: a live eval run; evals for cover-letter/KB/validate stages; OpenAI Responses API; per-stage reasoning-effort tuning; Vertex/Bedrock/Azure provider kinds; an OpenRouter profile; automatic application of eval results. Full list in `proposal.md`.

## Constraints

- Hexagonal rules: `core/` stays framework-free; provider quirks live in adapters and catalog data.
- Backward compatible: existing `mkcv.toml` stage `provider`/`model` keys and preset names keep working; with no user config, every stage resolves to today's model and temperature.
- `mypy --strict`, ruff, and full pytest green after every task; no network in tests.
- One PR for the feature (standing decision `single-pr`), one Conventional Commit per task on `feat/multi-provider-support`.
- `CLAUDE.md` is owner-maintained: do not edit it (its provider line goes stale; see follow-ups).

## Checklist

Route legend: `delegated` = one bounded writer (2+ non-trivial files, writer trigger); `inline` = parent edits directly.

### P1: Registry, capability data, OpenAI-compatible, OpenAI structured outputs

- [x] T01: Model capability catalog and catalog-derived pricing (route: delegated; 11 new core modules + pricing) - `dc5a0ad`
- [x] T02: OpenAI-compatible adapter with structured-output fallback chain (route: delegated; 6 new adapter modules) - `703caff`
- [x] T03: Native OpenAI adapter with strict structured outputs (route: delegated; adapter rewrite + test rewrite) - `baecd67`
- [x] T04: Capability-driven Anthropic request shaping (route: delegated; adapter + tests) - `9333892`
- [x] T05: Provider registry, catalog overrides, and factory dispatch (route: delegated; registry, loader, factory, services, workspace README) - `03914d0`

### P2: Google Gemini

- [x] T06: Google Gemini adapter (route: delegated; dependency + adapter + registry) - `1c550ce`

### P3: Profiles, resolution, `mkcv models`, warnings, docs

- [x] T07: Stage keys, stage requirements, and built-in model profiles (route: delegated; 6 new core modules) - `07f5a3b`
- [x] T08: Stage resolver, preset split, and settings migration (route: delegated; resolver, presets, settings, factory, validation) - `52e7c47`
- [x] T09: Model advisor, generation warnings, and `--model-profile` (route: delegated; core service + CLI) - `5cfb69e` (Rich markup fix first: `9d141c0`)
- [x] T10: `mkcv models` command (route: delegated; new command + app registration + tests) - `6044761`
- [x] T11: Provider and model documentation (route: delegated; 6+ docs files + template) - `4ba61b9` (advisor fix first: `bbd29b9`)

### P4: Eval harness

- [ ] T12: Eval package scaffolding, models, case loading, and cost estimate (route: delegated)
- [ ] T13: Stage-isolated runner and `run` / `bootstrap-reference` commands (route: delegated)
- [ ] T14: Synthetic eval fixtures (route: delegated)
- [ ] T15: Deterministic graders (route: delegated)
- [ ] T16: LLM-judge graders and rubrics (route: delegated)
- [ ] T17: Aggregation, recommendations, report, and eval docs (route: delegated)

## Acceptance criteria

- Every scenario in `docs/changes/multi-provider-support/specs/*.md` is covered by a passing test (or, for docs, satisfied by inspection).
- With no user config: `mkcv models` shows today's Anthropic models per stage and no warnings (with `ANTHROPIC_API_KEY` set).
- `[default.pipeline.stages.tailor] provider = "openai"` / `model = "gpt-6.1-sol"` is honoured by `mkcv generate`.
- `--model-profile openai|google|local` and `--provider <name>` switch all stages; unresolvable configs exit 3 before any LLM call.
- `rg -n '"anthropic"|claude-' src/mkcv/adapters/factory.py` returns nothing; `src/mkcv/adapters/llm/ollama.py` is gone.
- `uv run python -m evals run --yes` works offline (skips models without keys) and writes `results.jsonl`, `run.json`, `summary.json`, `report.md`.
- `docs/models.md` labels every profile provisional.
- Standard checks green on the final commit.

## Checks per task

```bash
uv run ruff check src/ tests/            # + evals/ from T12
uv run ruff format --check src/ tests/   # + evals/ from T12
uv run mypy src/                         # src/ evals/ from T12
uv run pytest -q
```

Plus the focused pytest command listed in each task of `tasks.md`.

## Delivery

- Strategy: `single-pr` (standing decision). Branch `feat/multi-provider-support` from `main`.
- Forecast: roughly 6,000–8,000 authored changed lines across 17 commits (tests included); one PR regardless of size.
- RDD: after each work-unit commit the parent runs `gentle-ai review assess` per the ODD protocol and records the tier/outcome below.

## Progress

- 2026-11-03: SDD artifacts written (proposal, design, 7 specs, tasks). Model facts verified against developers.openai.com, aistudio.google.com, PyPI, the `google-genai` README, locally installed SDKs (`openai` 2.29.0, `google-genai` 2.34.0 in an isolated env), and the claude-api skill. No source changes yet.

| Task | Commit | RED observed | GREEN observed | Review tier / outcome |
|---|---|---|---|---|
| T01 | `dc5a0ad` | `ModuleNotFoundError: No module named 'mkcv.core.models.capability_overlay'` | 269 focused, 1799 full | pending (parent runs `gentle-ai review assess`) |
| T02 | `703caff` | `ModuleNotFoundError: No module named 'mkcv.adapters.llm.strict_schema'` | 311 focused, 2110 full | pending (parent runs `gentle-ai review assess`) |
| T03 | `baecd67` | `KeyError: 'max_completion_tokens'` (request still sent json_object, temperature, max_tokens) | 82 focused (test_openai + test_factory), 2148 full | pending (parent runs `gentle-ai review assess`) |
| T04 | `9333892` | `TypeError: AnthropicAdapter.__init__() got an unexpected keyword argument 'resolver'` | 68 focused (test_anthropic), 2184 full | pending (parent runs `gentle-ai review assess`) |
| T05 | `03914d0` | `ModuleNotFoundError: No module named 'mkcv.adapters.llm.model_catalog_loader'` (registry test imports it first; `provider_registry` is missing too) | 866 focused (tests/test_adapters + pipeline + cover letter), 2289 full | pending (parent runs `gentle-ai review assess`) |
| T06 | `1c550ce` | `ModuleNotFoundError: No module named 'mkcv.adapters.llm.google'` (both new test files import it) | 156 focused (test_google + test_provider_registry), 2385 full | pending (parent runs `gentle-ai review assess`) |
| T07 | `07f5a3b` | `ModuleNotFoundError: No module named 'mkcv.core.models.stage_key'` (all four test files import it; `builtin_model_profiles` is reached after it) | 281 focused (test_core/test_catalog + stage_assignment + stage_key), 2580 full | pending (parent runs `gentle-ai review assess`) |
| T08 | `52e7c47` | `ModuleNotFoundError: No module named 'mkcv.adapters.llm.resolution_request'` (resolver tests); `AssertionError: assert 'claude-opus-5-5' == 'gpt-6.1-sol'` in `test_standard_preset_honours_a_tailor_override` (the preset beat per-stage config) | 702 focused (stage resolver, factory, config, presets, validation, cli), 2761 full | pending (parent runs `gentle-ai review assess`) |
| T09 | `5cfb69e` (+ `9d141c0`) | `ModuleNotFoundError: No module named 'mkcv.core.models.model_report'` (advisor/report/warnings tests); `AttributeError: module 'mkcv.cli.commands.generate' does not have the attribute 'create_model_report'` (95 CLI errors); markup fix: `assert '[default.pipeline.stages.select]' in "...set model in  or choose a --model-profile."` (15 failed) | 129 added over the fix commit (2787 to 2916 full); focused: 442 CLI + 156 factory/advisor | pending (parent runs `gentle-ai review assess`) |
| T10 | `6044761` | `ModuleNotFoundError: No module named 'mkcv.cli.commands.models'` (63 failed, incl. the subprocess help tests) | 66 focused (test_models_command), 2987 full | pending (parent runs `gentle-ai review assess`) |
| T11 | `4ba61b9` (+ `bbd29b9`) | `assert '# model_profile = "anthropic"' in <workspace mkcv.toml>` and the README assertions (14 failed in `test_workspace_manager.py`); advisor fix: `--model-profile anthropic-economy` produced tier warnings (2 failed against the previous advisor) | 70 focused (test_workspace_manager), 3010 full | pending (parent runs `gentle-ai review assess`) |

### Task notes

**T01** (route: delegated writer, trigger: 11 new core modules plus tests).

- Verification: `uv run pytest -q tests/test_core/test_models/test_model_catalog.py tests/test_core/test_catalog tests/test_core/test_models/test_pricing.py tests/test_core/test_exceptions.py`: 269 passed; `uv run ruff check src/ tests/`: clean; `uv run ruff format --check src/ tests/`: clean; `uv run mypy src/`: no issues (141 files); `uv run pytest -q`: 1799 passed, exit 0.
- `uv.lock` records mkcv 1.2.0 on `main`; committed as `6ae735e chore(deps): sync uv.lock with project version` before T01 because Phase 1 changes no dependency. T06 will lock `google-genai` on top of it.
- Decision: `core/catalog/__init__.py` imports `mkcv.core.models` first. `pricing.py` (imported by `core/models/__init__.py`) derives `MODEL_PRICING` from `core/catalog/builtin_models.py`, which imports from `mkcv.core.models`; importing the data module first in a fresh interpreter raised `ImportError ... partially initialized module`. `TestImportOrder` guards every entry order in a subprocess.
- Decision: `MODEL_PRICING` per-1K values are `round(price_per_mtok / 1000, 12)` so every legacy key stays bit-identical (plain division gave `0.00014000000000000001` for `deepseek/deepseek-chat-v3`). `calculate_cost` itself uses the per-1M prices.
- `docs/specs/cli-interface.md` exit-code row for `ConfigurationError` is left to T11 (its file list owns that doc).

**T02** (route: delegated writer, trigger: 6 new adapter modules plus 4 test files).

- Verification: `uv run pytest -q tests/test_adapters/test_llm/test_strict_schema.py tests/test_adapters/test_llm/test_request_adaptation.py tests/test_adapters/test_llm/test_openai_compatible.py tests/test_adapters/test_llm/test_builtin_providers.py`: 311 passed; ruff check/format, `uv run mypy src/` (147 files): clean; `uv run pytest -q`: 2110 passed, exit 0.
- Test strength: 21 one-line mutations of `openai_compatible.py`, `strict_schema.py`, and `request_adaptation.py` (adaptation, degradation, repair, usage summing, nullable rules, format whitelist) were all caught by the new tests.
- Decision: when `_make_nullable` widens a property that has an `enum`, it appends `None` to the enum. Design §7.5 step 5 only widens `type`; without the enum change `type: ["string", "null"]` plus an enum without `null` would still forbid `null`. Covered by `test_defaulted_enum_gains_a_null_value`.
- Decision: a response with `usage is None` records `TokenUsage()` (zero) instead of keeping the previous call's usage, so `get_last_usage()` always describes the latest call.
- Decision: the strict-schema walker treats `properties` as a name-to-schema mapping, so a property called `title`, `default`, or `format` is not mistaken for a keyword (`test_properties_named_like_keywords_are_not_filtered`).
- The parent adapter checks `message.refusal` with an `isinstance(str)` guard so a mocked message (truthy `MagicMock`) cannot masquerade as a refusal. `ollama.py` and its tests are untouched until T05.

**T03** (route: delegated writer, trigger: adapter rewrite plus test rewrite).

- Verification: `uv run pytest -q tests/test_adapters/test_llm/test_openai.py tests/test_adapters/test_llm/test_factory.py`: 82 passed; ruff check/format, `uv run mypy src/`: clean; `uv run pytest -q`: 2148 passed, exit 0.
- `OpenAIAdapter` has no method overrides, as the design predicted: refusal, truncation, adaptation, and repair live in the parent. The rewritten `test_openai.py` covers REQ-OAI-1 to 10 with SDK `ChatCompletion` objects; the max_tokens-to-max_completion_tokens adaptation (REQ-OAI-8) is exercised with a custom resolver whose `token_param` is `max_tokens`.
- `factory.py` still constructs `OpenAIAdapter(api_key=..., base_url=...)` for `openai` and `openrouter`; `test_factory.py` passes unchanged. Note that until T05 `openrouter` runs on `OpenAIAdapter`, so it now gets strict JSON-schema output with no degradation; T05 moves it to `OpenAICompatibleAdapter`.

**T04** (route: delegated writer, trigger: adapter refactor plus test additions).

- Verification: `uv run pytest -q tests/test_adapters/test_llm/test_anthropic.py`: 68 passed; ruff check/format, `uv run mypy src/`: clean; `uv run pytest -q`: 2184 passed, exit 0.
- Equivalence evidence: a scratch script loaded the pre-change `anthropic.py` from `c1f464b` and compared `_build_request` output with the new adapter for 30 Claude model IDs (every catalog entry plus dated and legacy variants) at 4 token limits: 0 mismatches. 9 one-line mutations of the new logic were all caught.
- All pre-existing Anthropic tests pass unchanged (no constructor edits were needed); new classes cover REQ-CAT-9, catalog-driven shaping (tool/temperature, output_config/no temperature, JSON_OBJECT and PROMPT treated as tool), and the one-shot temperature adaptation (complete, forced-tool, and output_config paths).
- Error mapping is deliberately unchanged (context-length mapping only in `complete`); only the `provider` label now comes from `provider_name`. The temperature retry loop is bounded because the retried request no longer contains `temperature`.
- Behaviour change (design D20): a Claude model unknown to the catalog now resolves to the strict defaults (no `temperature`, 16000 floor, `output_config`) where the old prefix check treated it as a 4.x model.

**T05** (route: delegated writer, trigger: registry, loader, factory, two services, README builder, two deletions).

- Verification: `uv run pytest -q tests/test_adapters tests/test_core/test_services/test_pipeline.py tests/test_core/test_services/test_cover_letter.py`: 866 passed; ruff check/format, `uv run mypy src/` (148 files): clean; `uv run pytest -q`: 2289 passed, exit 0. `rg -n "elif provider ==" src/mkcv/adapters/factory.py`: no matches; `fd ollama src tests`: no matches; `rg -n "OllamaAdapter|_PROVIDER_ENV_KEYS|_resolve_api_key" src tests`: only the assertions/docstrings that name them as gone. 21 one-line mutations of the registry, loader, factory, services, and README builder were all caught.
- Dynaconf behaviour verified empirically before writing the loader tests: with `merge_enabled=True`, `[[default.model_catalog]]` arrays from later layers (and from `load_file`) are appended after earlier layers' items, so workspace entries overlay global ones; tables deep-merge; `config.get("providers", {})` returns a `Box` (a `dict`), and `config.get("model_catalog", [])` a `BoxList` (a `list`).
- Tests that built `MagicMock` configs now need `config.get` to answer registry lookups; `test_factory.py` and `test_kb_factory.py` gained a `_blank_config`/`_make_config` that returns the caller's default for unset keys. The legacy attribute pattern (`config.pipeline.stages...`) is untouched and still goes away in T08.
- Costs are priced with the stage's provider (`calculate_cost(..., provider=provider)`), per design §4.4. A stage whose provider name has no catalog entries for its model prices at 0.0, where the old table matched on model name alone. A test (`test_price_is_looked_up_for_the_stage_provider`) pins this.
- `OllamaAdapter` behaviours were ported to `test_openai_compatible.py` (schema augmentation helper, connection error naming, parse and validation failures); its `model or default_model` fallback was dropped because every caller passes a model. `test_ollama.py` and `ollama.py` are deleted.
- The `GOOGLE` builder raises `ConfigurationError("The google provider is not available yet")` as planned; `test_google_is_not_available_before_its_adapter_lands` in `test_provider_registry.py` is replaced in T06.

**T06** (route: delegated writer, trigger: dependency, new adapter module, registry builder, two test files).

- Verification: `uv run pytest -q tests/test_adapters/test_llm/test_google.py tests/test_adapters/test_llm/test_provider_registry.py`: 156 passed; `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`: clean; `uv run mypy src/` (149 files): clean, so no `google`/`google.*` mypy override was added (the SDK ships types); `uv run pytest`: 2385 passed, exit 0; `uv lock --check`: consistent.
- Test strength: 25 one-line mutations of `google.py` (role mapping, system joining, thinking tokens, usage summing, temperature handling, adaptation guards, error codes, context-length words, block/finish reasons, array guard, transport mapping, base URL) were all caught. The first run of the mutation harness stripped indentation, so its "caught" results were syntax errors; it was fixed and rerun, and the one real survivor (the non-object JSON guard) gained `test_a_json_array_is_repaired_instead_of_crashing`.
- SDK facts confirmed locally against `google-genai` 2.34.0: `errors.ClientError(code, response_json)` sets `.code`, `.status`, and `.message` from `response_json["error"]`, while `str(error)` is `"<code> <STATUS>. {payload}"`; `GenerateContentResponse.usage_metadata` is `GenerateContentResponseUsageMetadata` (has `candidates_token_count`); `block_reason` and `finish_reason` are enums (`.name` gives `SAFETY`/`MAX_TOKENS`); `client.aio` is a stable attribute, so tests can assign `adapter._client.aio.models.generate_content`.
- Decision: error classification (rejected `temperature`, `token`/`context` in a 400) reads `error.message`, falling back to `str(error)`. `str(error)` carries the HTTP status name (`INVALID_ARGUMENT`), which contains `invalid` and would make any 400 that merely mentions temperature look like a rejection of it. The text put into the raised mkcv error is still `str(error)`, so users see code, status, and payload. Pinned by `test_the_status_name_alone_does_not_trigger_adaptation`.
- Decision: `complete` applies the same empty-reply handling as `complete_structured` (blocked prompt, truncation, no text raise `ProviderError`) rather than returning an empty string. Design §7.6 words the handling generically; an empty plain completion is never a usable stage result.
- Addition (not in the spec): `httpx.TransportError` maps to `ProviderError("Cannot connect to <provider>: ...")`, matching the OpenAI-compatible adapter and the Anthropic adapter's `APIError` catch; without it a network failure surfaced as a traceback. An empty reply whose first candidate finished for an unusual reason (e.g. `SAFETY`) reports `Gemini returned no text (finish reason: SAFETY)`; the plain `Gemini returned no text` text is kept when there is no such signal.
- Decision: `REPAIR_PROMPT` is defined again in `google.py` (identical text, guarded by `test_repair_prompt_matches_the_openai_compatible_adapter`) instead of importing it from `openai_compatible.py` (which would pull the OpenAI SDK into Google runs) or moving it into `_utils.py` (outside T06's file list). If a later cleanup moves it to `_utils.py`, delete the copy and the guard test.
- Truncation follows design §7.6 literally: the `MAX_TOKENS` error is raised only when the reply is empty. A truncated but non-empty reply goes through the repair path like any invalid JSON.
- Registry tests replaced the placeholder with `TestGoogleAdapterCreation` (builder, retry wrapping, `GEMINI_API_KEY` over `GOOGLE_API_KEY`, stub fallback, `base_url` from config reaching both a patched and the real SDK client, a user-defined `type = "google"` provider) and `TestLazyImports` (subprocess checks that importing the factory or registry, or creating a non-Google adapter, leaves `google.genai` out of `sys.modules`).

**T07** (route: delegated writer, trigger: 6 new core modules plus 4 test files).

- Verification: `uv run pytest -q tests/test_core/test_catalog tests/test_core/test_models/test_stage_assignment.py tests/test_core/test_models/test_stage_key.py`: 281 passed; ruff check/format and `uv run mypy src/` (155 files): clean; `uv run pytest`: 2580 passed, exit 0.
- Test strength: 23 one-line mutations of the helpers, profile cells, requirement cells, `StageAssignment.to_stage_config`, and the stage numbering were run; 22 were caught and the survivor is an equivalent mutation (a `None` base lookup also returns `None`).
- Extra file: `tests/test_core/test_models/test_stage_key.py` covers `StageKey` and its constants (the task lists no test for the new `stage_key.py` module; tests mirror source layout).
- Data-consistency tests beyond REQ-MP-1: every profile model has a price for its provider, none is deprecated, and every non-economy cloud profile meets each stage's `min_tier` according to the catalog (`local` and the economy profiles intentionally do not). They pass with the shipped data, so no profile cell was changed from the design table.
- `profile_stage_model` follows the `extends` link recursively through built-in profiles; the tests assert every `extends` target exists and is itself a base profile, so a chain cannot loop.
- `StageAssignment.temperature` is unconstrained (as in the design); `to_stage_config()` raises a Pydantic `ValidationError` for a value outside 0..2. T08 must turn a bad configured temperature into a `ConfigurationError` before it builds assignments.
- `core/models/__init__.py` now exports `ModelProfile`, `StageAssignment`, `StageKey`, and `StageRequirement`. `STAGE_REQUIREMENTS` and the profile helpers are imported from `mkcv.core.catalog.*` (same as `BUILTIN_MODEL_CAPABILITIES`). A subprocess test confirms the catalog modules import first in a fresh interpreter and pull in nothing from `adapters`, `config`, or `cli`.

**T08** (route: delegated writer, trigger: 3 new adapter modules, preset/settings/factory/validation edits, and a test rewrite across 8 files).

- Verification: `uv run pytest tests/test_adapters/test_llm/test_stage_resolver.py tests/test_adapters/test_llm/test_factory.py tests/test_config tests/test_core/test_models/test_profile_preset.py tests/test_core/test_services/test_validation.py tests/test_cli`: 702 passed; ruff check/format and `uv run mypy src/` (158 files): clean; `uv run pytest`: 2761 passed, exit 0. `rg -n '"anthropic"|claude-' src/mkcv/adapters/factory.py` and `rg -n "^\s*(provider|model)\s*=" src/mkcv/config/settings.toml`: no matches.
- Test strength: 41 one-line mutations of `stage_resolver.py`, `factory.py`, `validation.py`, `profile_preset.py`, and `resolved_stages.py` were all caught.
- Real-config smoke test (the real `Configuration` class, not temp TOML): defaults give exactly today's models and temperatures for `standard`, `concise`, `budget`, KB, validate, and cover letter; a workspace `mkcv.toml` tailor override and `MKCV_PIPELINE__MODEL_PROFILE=openai` are honoured; `MKCV_PIPELINE__MODEL_PROFILE=nope` makes `mkcv generate` print `Error: Unknown model profile 'nope'...` and exit 3 before any LLM call (REQ-SR-10).
- Rewritten tests (old precedence replaced, not deleted): `test_factory.py` (`TestResolvePreset`/`TestResolveStageConfigs` became resolver-based classes; `test_budget_preset_ignores_config_settings` became `test_budget_preset_still_yields_ollama_when_config_names_another_provider`; legacy MagicMock attribute stages became `config.get` dotted keys), `test_profile_preset.py` (REQ-MP-2), `test_kb_factory.py`, and `test_configuration.py` (see below).
- Decision (design gap): the `stub` provider has no profile, and the old `--provider stub` path worked because the preset still supplied a model. The resolver now gives a stub stage the model `stub-model` (`STUB_MODEL`) when nothing names one, instead of failing with `Cannot resolve models`. Explicit config still wins.
- Decision (design inconsistency): design §6.5 step 5 falls back to `profile.provider` else `DEFAULT_PROVIDER` for a stage that sets only an unknown `model`. With `pipeline.provider = "groq"` (no profile) that would send the model to Anthropic, contradicting the documented meaning of `pipeline.provider` ("default provider when no model_profile is set"). The resolver uses the plan's base provider instead (the profile's provider when a profile exists, so every spec scenario is unchanged; otherwise the configured/default provider).
- Decision (literal reading kept): under `--provider X`, a stage that sets only `model` (no `provider`) does not count as config for X, so the profile model is used (design §6.5 step 5 requires `cfg_provider == provider_override`). Pinned by `test_a_model_only_config_entry_is_not_config_for_the_overridden_provider`; T11 should document that a stage meant to survive `--provider` must name its provider.
- Addition: the resolver validates `temperature` (must be a number in 0..2) and string settings, and raises `ConfigurationError` instead of leaking a Pydantic error from `StageAssignment.to_stage_config()` (T07 note). `create_kb_generation_service` raises `ConfigurationError` for a non-integer `max_tokens`/`chunk_threshold`; it previously fell back silently to the defaults.
- Preset descriptions no longer name models ("economy models", "recommended models"), because the same preset now runs on any provider.
- `tests/test_config/test_configuration.py` was edited (outside the T08 file list) because `test_pipeline_analyze_stage_has_provider` asserted the removed `provider` key; it now asserts the temperature and checks that `config.get("validate")`, `config.get("kb")`, and dotted stage paths resolve on the real Dynaconf object, which the resolver depends on.
- Not done, by design: `generate.py` and `cover_letter.py` are unchanged. `generate.py` still calls `create_cover_letter_service(settings, provider_override=...)` without `preset_name`, so a `cl_preset` of `concise` does not yet pick the economy variant for cover letters (T09 passes it through).
- Known issue for T09 (not caused by T08): the CLI prints errors as `console.print(f"[red]Error:[/red] {exc}")`, and Rich treats `[default.pipeline.stages.select]` in the message as a markup tag and drops it. A user sees `set model in  or choose a --model-profile.` The same happens to T05's `Define new ones under [default.providers.<name>]`. Reproduce with `uv run mkcv generate --jd jd.txt --kb kb.md --provider openrouter`. Fix with `rich.markup.escape(str(exc))` at every `except MkcvError` print site: `cli/app.py:102`, `cli/commands/generate.py` (8 sites), `cover_letter.py` (4), `kb.py` (4), `validate.py` (1). A CLI test that asserts a bracketed message survives is the RED.
- `[default.validate] temperature` and `[default.pipeline] model_warnings` are in `settings.toml` per design, but `ValidationService` still hard-codes 0.2/0.3 and nothing reads `model_warnings` until T09.

**T09** (route: delegated writer, trigger: 5 new core modules, a service, a CLI module, factory and two command rewires, plus tests in 9 files).

- Commits: `9d141c0 fix(cli): escape Rich markup in printed error messages` (own commit, per the handoff), then `5cfb69e feat(cli): warn about weak or unknown stage models and add --model-profile`.
- Verification: `uv run pytest tests/test_core/test_services/test_model_advisor.py tests/test_core/test_models/test_model_report.py tests/test_cli tests/test_adapters/test_llm/test_factory.py tests/test_core/test_services/test_validation.py`: all passed; `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`: clean; `uv run mypy src/` (164 files): clean; `uv run pytest`: 2916 passed, exit 0 (with a clean `__pycache__`); `uv lock --check`: consistent.
- Rich markup fix: `rich.markup.escape(str(exc))` at 20 print sites (`app.py` 1, `generate.py` 8, `cover_letter.py` 4, `kb.py` 4, `validate.py` 1, `interactive/session.py` 2). `tests/test_cli/test_error_markup.py` has nine behavioural tests (one per command family) plus an AST guard that fails for any `print(f"...{exc}...")` in `src/mkcv/cli` without `escape`, so a new print site cannot reintroduce the bug. Real CLI check: `mkcv generate ... --provider openrouter` now prints `set model in [default.pipeline.stages.analyze] or choose a --model-profile.` and exits 3.
- Test strength: 31 one-line mutations of `model_advisor.py`, `model_report.py`, `model_warnings.py`, the factory, `validation.py`, `generate.py`, and `cover_letter.py`; 28 were caught at first, and the three survivors (cost rounding, an economy profile listed first, warning order) were killed by two new tests and a corrected mutation pattern, so 31 of 31 are caught. The mutation harness first hit stale bytecode (same-size mutation inside one second); it now deletes the module's `.pyc` after each restore.
- `[default.pipeline] model_warnings` is read by `generate` and `cover-letter`; `[default.validate] temperature` now reaches `ValidationService(temperature=)` through the factory. The JD analysis inside validation keeps its own 0.2, so defaults are unchanged.
- `generate` and the chained cover letter: `create_cover_letter_service(settings, provider_override=..., model_profile=..., preset_name=cl_preset)`; the `cover-letter` command passes `preset or "standard"`. The report step runs after preset resolution and before the app-dir, JD, or workspace work, so a bad flag exits 3 before any LLM call.
- Spec/data mismatch: REQ-MP-9 expects the deprecation note to contain `routes to gemini-3.5-flash-lite`, but design §4.1 and the T01 catalog data read `requests route to gemini-3.5-flash-lite`. The design is authoritative for messages, so the data stays and the tests assert `route to`. Fix the spec wording if it is ever edited.
- Decision (design gap): `estimated_total_usd` sums every stage in the report (design §8.1 verbatim), so `mkcv models`, which also lists cover letter, KB, and validate, cannot print "per resume run" from it. `ModelReport.resume_run_estimate()` sums only the five pipeline stages (shared helper `summarize_costs`); T10 uses it for the `Estimated cost per resume run (5 stages)` line.
- Decision (design gap): a tier or tier-unknown warning is skipped when the assigned model is the one mkcv recommends for that stage. Without it `--model-profile local` (source `cli`) printed five warnings that llama3.1:8b is tier minimal with "recommended: ollama/llama3.1:8b". Deprecation warnings are never skipped. T11 widened the rule (`bbd29b9`): the active profile's own model for the stage is exempt too, because `--model-profile anthropic-economy` is labelled `cli` yet is mkcv's choice.
- Decision (design gap): the offline `stub` provider is never warned about (it has no catalog data, so every `--provider stub` run would claim `stub/stub-model` is unknown).
- Decision: `_extract_jd_metadata` re-raises `ConfigurationError`. It used to swallow every `MkcvError` and `generate` then reported "Could not determine company/position" (exit 2) for a bad `--model-profile` in a workspace.
- Decision: `cover_letter_command` resolves the report (`_warn_about_models`) before the output directory is created, so an invalid setup leaves no empty directory behind.
- Known limitation: with `--cover-letter` and a `--cl-preset` that differs from `--cv-preset`, the single report (design §8.3) uses the CV preset for both document types. The cover letter factory uses `cl_preset`, so the two differ only if `--cl-preset budget` (provider ollama) is mixed with a non-budget CV preset.
- Known limitation: `--profile budget --model-profile X` fails with "`--model-profile` and `--provider` cannot be used together" because the deprecated `budget` value implies `--provider ollama`. The message names a flag the user did not type; the legacy flag is deprecated, so it is left as is.
- Not done by design: `kb --provider` help text still lists the old four providers (T11 touches the docs and help strings).

**T10** (route: delegated writer, trigger: new command module, app registration, factory accessor, and a 66-test file).

- Verification: `uv run pytest tests/test_cli/test_models_command.py tests/test_cli/test_app.py`: all passed; `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`: clean; `uv run mypy src/` (165 files): clean; `uv run pytest`: 2987 passed, exit 0; `uv lock --check`: consistent. `uv run mkcv models --help` exits 0; `uv run mkcv models --profiles` runs with no keys (also a subprocess test in `test_app.py`).
- Test strength: 27 one-line mutations of `models.py` and the `app.py` registration; 23 were caught at first, and the four survivors (an undefined catalog provider, a deprecated entry without notes, the unknown tier cell, the last stage row of a profile) were killed by five added tests, so 27 of 27 are caught.
- Real CLI check (temp directory, `ANTHROPIC_API_KEY` set, no `OPENAI_API_KEY`, tailor set to `openai/gpt-6.1-terra` through `MKCV_PIPELINE__STAGES__TAILOR__*`): the default view reproduces design §8.4's mock row for row, including `$0.0550` for tailor and `Estimated cost per resume run (5 stages): $0.37`. With no user config the same command prints today's Anthropic models, `$0.54` per resume run, and no `Warnings:` section.
- Decision (outside the task's file list): `factory.create_provider_registry(config)` is a public wrapper over `_registry`. The `--catalog` view needs the catalog with the user's overrides and the provider names, and the CLI must not import the private helper.
- Decision: `--catalog` rows show effective capabilities (the entry laid over its provider's defaults), so sampling and structured-output cells say what a request would really use. `--catalog --json` lists the raw entries (`ModelCapability.model_dump`), the form a user writes in `[[default.model_catalog]]`.
- Decision: `--catalog --provider X` validates `X` through the registry, so a typo exits 3 with the known providers instead of printing an empty table; a defined provider with no entries (`stub`) prints `No catalog entries for provider 'stub'.`
- Decision: `--profiles` together with `--catalog` exits 2 (usage error, like `generate --app-dir` conflicts); `--provider` and `--model-profile` are ignored by `--profiles`, which always lists all seven. The three view flags have no `--no-` forms.
- Decision: the `Source:` line is derived from the report plus the flags (`cli (--model-profile)`, `cli (--provider)`, `preset (budget)`, `config (pipeline.model_profile or pipeline.provider)`, `default (...)`). The report records where a choice came from but not which config key, so the config line names both.
- Decision: JSON goes through `console.print(..., markup=False, highlight=False, soft_wrap=True, emoji=False)`, because a narrow terminal would otherwise wrap it, and a catalog note such as `see [default.providers.groq] :rocket:` would lose its bracketed path and gain an emoji. Two tests pin this on a 40-column console.
- Known limitation: on a non-TTY or narrow terminal Rich wraps table cells at the console width (80 columns when piped). The tests use a 240-column console; scripts should use `--json`.

**T11** (route: delegated writer, trigger: 9 documentation files, the workspace template and README builder, and tests).

- Commits: `bbd29b9 fix(core): do not question the models of a profile the user chose`, then `4ba61b9 docs: document providers, model profiles, and mkcv models`.
- Verification: `uv run pytest tests/test_adapters/test_workspace_manager.py`: 70 passed; `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`: clean; `uv run mypy src/` (165 files): clean; `uv run pytest`: 3010 passed, exit 0 (clean `__pycache__`); `uv lock --check`: consistent. A fresh `mkcv init` workspace gets the new `mkcv.toml` and README, and `mkcv models` runs inside it.
- Template tests (RED first): the commented examples in the workspace `mkcv.toml` (model profile, `provider`, `model_warnings`, Google and Groq providers, `[[default.model_catalog]]`) are switched on by the test, parsed as TOML, and fed to `ProviderRegistry.from_config` and `load_model_catalog`, so a documented example cannot rot into an invalid one. README tests assert `--preset` (not `--profile`) and `--model-profile` usage, the `mkcv models` row, and that no command in the table has an empty description.
- Docs: new `docs/models.md` (providers, the four profiles plus three economy variants with provisional labels, stage requirements, estimated cost per profile, the four ways to choose, the numbered precedence list from design §6.5, warnings, custom providers and catalog entries, capability caveats, an Evidence section, the verified-facts tables with source links and the 2026-11-03 retrieval date, and the exit-code note). `README.md`, `docs/specs/cli-interface.md` (new `models` and `cover-letter` sections, exit code 3 row, env vars), `docs/specs/architecture.md`, `docs/specs/data-models.md`, and `AGENTS.md` describe the registry, catalog, resolver, advisor, and `ConfigurationError`. The behaviour change (per-stage config is now honoured by `generate`) is called out in the README, `models.md`, and the CLI spec. `CLAUDE.md` is untouched (owner-maintained).
- Corrections of claims the old docs made that were never true: (1) `mkcv.toml` section headers need the `default.` prefix, and README and `examples/mkcv.toml` used `[pipeline.stages.*]`, which is silently ignored (checked against `Configuration.load_workspace_config`); `examples/mkcv.toml` now uses the prefix. (2) `docs/specs/cli-interface.md` listed `MKCV_ANTHROPIC_API_KEY` and friends; the old factory and the registry both read `ANTHROPIC_API_KEY` and the other providers' own names, so the table was rewritten. (3) The exit-code 3 row promised "missing API key"; a missing key warns and falls back to the stub.
- Files outside T11's list, all inside the allowed surfaces: `docs/DEVELOPMENT.md` (stale "Adding an LLM Provider" steps and provider list), `examples/mkcv.toml`, `examples/mkcv-demo/README.md` (regenerated with `mkcv init --update-readme`, which changed only that file), and the `--provider` help text of `kb`.
- The workspace README builder gained descriptions for `cover-letter`, `kb`, and `models` (its table showed an empty description for `cover-letter`) and uses `--preset`; the old text told users to run `--profile concise|standard|comprehensive`, which was never valid.
- Acceptance note: the literal `rg -n "\-\-profile" README.md` also matches `mkcv models --profiles`; the only mention of the old `--profile` flag is the deprecation note.
- `docs/models.md` describes the eval harness as planned (its "Evidence" section). T17 adds "How recommendations are made" and should replace that paragraph with the real process.
- Follow-up (not in this feature): `[default.defaults] profile = "standard"` in the workspace template is read by nothing.

## Decisions (rationale in `design.md` §1 and §15)

- Eval harness in top-level `evals/` (not packaged), run with `uv run python -m evals`.
- Built-in catalog is a Python data module in `core/catalog/`; user overrides are `[[default.model_catalog]]` tables with field-level overlay.
- Presets (density) and model profiles (models) are separate axes; no new profile is named `budget`.
- Per-stage config beats profile; CLI beats both; `--model-profile` and `--provider` are mutually exclusive.
- OpenAI via Chat Completions; `OpenAIAdapter` subclasses `OpenAICompatibleAdapter`.
- Unknown Anthropic/OpenAI/Google models omit sampling params and get a 16000 output floor; adapters adapt once on a 400 that names `temperature`/`max_tokens`.
- `ConfigurationError` exit code 3.

## Risks to watch during implementation

- Strict-schema transform vs real response models (T02): the parametrized test over all twelve response models is the guard.
- T08 changes precedence: existing CLI and factory tests that encoded "preset beats config" must be rewritten to the new rule, not deleted. (Done in T08; the CLI tests needed no change because they patch the factory.)
- `uv.lock` on `main` records mkcv `1.2.0` while `pyproject.toml` says `1.3.0`; the first `uv run` rewrites it. Commit that one-line lock change with T06 (when `uv lock` runs anyway) or in T01 if a check needs it.

## Follow-ups (not in this feature)

- Owner: first live eval run and adoption of eval-backed profiles (steps at the end of `tasks.md`).
- Owner: update `CLAUDE.md` "LLM providers (Anthropic/OpenAI/Ollama/OpenRouter/Stub)" to include Google and OpenAI-compatible endpoints.
- Evaluate the OpenAI Responses API and per-stage reasoning effort once evals exist.

## Next step

T01-T11 are implemented and committed on `feat/multi-provider-support` (P1-P3 complete). Next: T12 (eval package scaffolding, models, case loading, and cost estimate); it builds on `STAGE_REQUIREMENTS`, `StageKey`, `load_model_catalog`, and the factory (`create_provider_registry` gives access to the catalog with the user's overrides). P4 (T12-T17) is the remaining work, then the owner actions at the end of `tasks.md`.
