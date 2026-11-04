# Feature: Claude 5.5 model defaults

## Objective

Default mkcv to the latest Claude family (Opus 5.5, Sonnet 5.5, Haiku 5.5) while keeping user overrides working through the existing 5-layer config.

## Problem

Built-in defaults and presets reference retired dated IDs (`claude-*-4-20250514`). A half-finished bump to `claude-*-4-6` left `test_pricing.py` failing. Claude 5.5 models reject `temperature` (non-default) and forced `tool_choice` (`any`/`tool`) with HTTP 400, and the Anthropic adapter sends both on every call.

## Scope

- Anthropic adapter compatible with Claude 5.x: no sampling params for models that reject them; structured output without forced tool choice; tolerate thinking blocks; output budget large enough for always-on thinking.
- Defaults, presets, `settings.toml`, workspace template, pricing table, tests, and docs/README updated to `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`.
- Keep the stage 1-2 `max_tokens` fix from the WIP.

Out of scope: non-Anthropic providers, historical SDD docs under `docs/changes/`.

## Constraints

- Older Claude models (4.x) set by users must keep working, including temperature.
- `mypy --strict`, ruff, and full pytest must pass.

## Checklist

- [x] T1: Adapter supports Claude 5.x request rules (route: delegated, 2+ non-trivial files) — `7b16a44`
- [x] T2: Defaults, presets, pricing, tests, and docs move to 5.5 IDs (route: delegated with T1) — `3c2761a` (stage 1-2 `max_tokens` fix), `2018b09`
- [ ] T3: PR, merge, and release

## Acceptance criteria

- No `claude-*-4-20250514` or `claude-*-4-6` defaults remain in `src/`.
- Requests to `claude-*-5*` models omit `temperature` and never use forced `tool_choice`.
- Requests to 4.x models are unchanged.
- Full checks green.

## Progress

- 2026-11-03: PR #5 (KB generation) merged as 53e67fd. WIP moved to `feat/claude-5-5-models`.
- 2026-11-03: T1 and T2 done.
  - `7b16a44` feat(llm): `is_claude_5_family()` in `adapters/llm/anthropic.py` decides the request shape. 5.x: no `temperature`, `max_tokens` floor 16000, structured replies via `output_config.format` (`json_schema` from `anthropic.transform_schema`). 4.x: unchanged (temperature + forced tool). Text/JSON read from text blocks only, so thinking blocks are ignored.
  - `3c2761a` fix(pipeline): stages 1-2 pass the preset `max_tokens`.
  - `2018b09` feat(config): defaults, presets, template, settings, pricing, tests, and docs on `claude-{opus,sonnet,haiku}-5-5`. Pricing keeps the dated 4.x keys and adds `claude-haiku-4-5-20251001`.

## Decisions

- Structured outputs use the installed SDK (`anthropic` 0.86.0) directly: it already exposes `output_config` on `messages.stream` and `anthropic.transform_schema`, so no version bump and no `extra_body`.
- All seven `complete_structured` response models were checked against structured-output limits (no open `dict` objects, no recursion). JDFrontmatter is the largest: 13 optional properties, 12 `anyOf`.
- Test-first: the new adapter tests failed before implementation (ImportError, then 6 behavioral failures), then passed.

## Verification evidence (HEAD `2018b09`)

- `uv run ruff format src/ tests/`: 237 files left unchanged
- `uv run ruff check src/ tests/`: All checks passed
- `uv run mypy src/`: no issues in 130 source files
- `uv run pytest -q`: exit 0, 1583 passed (`7b16a44` and `3c2761a` each pass alone: 1575)
- `rg -n "20250514|claude-sonnet-4-6|claude-opus-4-6" src/`: only historical pricing keys

## Next step

T3: live smoke test against the API with a 5.5 model (structured outputs not yet exercised against the real API), then PR.
