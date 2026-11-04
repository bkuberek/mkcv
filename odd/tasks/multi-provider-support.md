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
- [ ] T05: Provider registry, catalog overrides, and factory dispatch (route: delegated; registry, loader, factory, services, workspace README)

### P2: Google Gemini

- [ ] T06: Google Gemini adapter (route: delegated; dependency + adapter + registry)

### P3: Profiles, resolution, `mkcv models`, warnings, docs

- [ ] T07: Stage keys, stage requirements, and built-in model profiles (route: delegated; 6 new core modules)
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

Create `feat/multi-provider-support` from `main` and start T01.
