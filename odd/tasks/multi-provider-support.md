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
- [ ] T08: Stage resolver, preset split, and settings migration (route: delegated; resolver, presets, settings, factory, validation)
- [ ] T09: Model advisor, generation warnings, and `--model-profile` (route: delegated; core service + CLI)
- [ ] T10: `mkcv models` command (route: delegated; new command + app registration + tests)
- [ ] T11: Provider and model documentation (route: delegated; 6+ docs files + template)

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
- Test strength: 24 one-line mutations of the helpers, profile cells, requirement cells, `StageAssignment.to_stage_config`, and the stage numbering were caught; the only survivors were an equivalent mutation (a `None` base lookup also returns `None`) and a no-op placeholder row.
- Extra file: `tests/test_core/test_models/test_stage_key.py` covers `StageKey` and its constants (the task lists no test for the new `stage_key.py` module; tests mirror source layout).
- Data-consistency tests beyond REQ-MP-1: every profile model has a price for its provider, none is deprecated, and every non-economy cloud profile meets each stage's `min_tier` according to the catalog (`local` and the economy profiles intentionally do not). They pass with the shipped data, so no profile cell was changed from the design table.
- `profile_stage_model` follows the `extends` link recursively through built-in profiles; the tests assert every `extends` target exists and is itself a base profile, so a chain cannot loop.
- `StageAssignment.temperature` is unconstrained (as in the design); `to_stage_config()` raises a Pydantic `ValidationError` for a value outside 0..2. T08 must turn a bad configured temperature into a `ConfigurationError` before it builds assignments.
- `core/models/__init__.py` now exports `ModelProfile`, `StageAssignment`, `StageKey`, and `StageRequirement`. `STAGE_REQUIREMENTS` and the profile helpers are imported from `mkcv.core.catalog.*` (same as `BUILTIN_MODEL_CAPABILITIES`). A subprocess test confirms the catalog modules import first in a fresh interpreter and pull in nothing from `adapters`, `config`, or `cli`.

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
- T08 changes precedence: existing CLI and factory tests that encoded "preset beats config" must be rewritten to the new rule, not deleted.
- `uv.lock` on `main` records mkcv `1.2.0` while `pyproject.toml` says `1.3.0`; the first `uv run` rewrites it. Commit that one-line lock change with T06 (when `uv lock` runs anyway) or in T01 if a check needs it.

## Follow-ups (not in this feature)

- Owner: first live eval run and adoption of eval-backed profiles (steps at the end of `tasks.md`).
- Owner: update `CLAUDE.md` "LLM providers (Anthropic/OpenAI/Ollama/OpenRouter/Stub)" to include Google and OpenAI-compatible endpoints.
- Evaluate the OpenAI Responses API and per-stage reasoning effort once evals exist.

## Next step

T01-T07 are implemented and committed on `feat/multi-provider-support`. Next: T08 (stage resolver, preset split, settings migration), then T09-T11.
