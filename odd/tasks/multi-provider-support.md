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

- [ ] T01: Model capability catalog and catalog-derived pricing (route: delegated; 11 new core modules + pricing)
- [ ] T02: OpenAI-compatible adapter with structured-output fallback chain (route: delegated; 6 new adapter modules)
- [ ] T03: Native OpenAI adapter with strict structured outputs (route: delegated; adapter rewrite + test rewrite)
- [ ] T04: Capability-driven Anthropic request shaping (route: delegated; adapter + tests)
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
| | | | | |

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
