# Spec: Model Profiles, Presets, `mkcv models`, and Warnings

Design references: §6.2–§6.7 (profiles, presets, CLI flags), §8 (advisor, warnings, command).

CLI scenarios run through `cyclopts` the way `tests/test_cli/test_generate.py` does, with factory functions patched where a scenario must not run the pipeline. No scenario makes a network call.

## Profiles

### REQ-MP-1: Built-in profiles

- `BUILTIN_MODEL_PROFILES` MUST contain exactly `anthropic`, `anthropic-economy`, `openai`, `openai-economy`, `google`, `google-economy`, `local`, with the stage models of design §6.2, all with `evidence == "provisional"`.
- Every model named in a profile MUST have an exact catalog entry for the profile's provider, except `llama3.1:8b`, which matches the `ollama` prefix entry `llama3.1`.
- **When** `profile_stage_model(get_profile("openai-economy"), StageKey.COVER_LETTER_GENERATE)` is called, **then** it returns `gpt-6-astra` (inherited from `openai`).
- **When** `profile_for_provider("ollama", economy=True)` is called, **then** it returns `local`.
- **When** `profile_for_provider("openrouter", economy=False)` is called, **then** it returns `None`.

### REQ-MP-2: Presets keep names and gain the economy flag

- `resolve_preset` MUST still resolve `concise`, `standard`, `comprehensive`, `budget`, `premium`, and return `None` for `default` and unknown names.
- `concise.economy is True`; `standard.economy is False`; `comprehensive.economy is False`; `budget.provider == "ollama"` and `budget.density == "concise"`; `premium` equals `standard` apart from its lookup name.
- `Preset` MUST NOT have a `stage_configs` field.

## CLI flags

### REQ-MP-3: `generate --model-profile`

- **When** `mkcv generate --jd jd.txt --kb kb.md --model-profile google` runs (pipeline patched), **then** `create_pipeline_service` is called with `model_profile="google"`.
- **When** `mkcv generate ... --model-profile google --provider openai` runs, **then** the process exits with code 3 and prints `cannot be used together`.
- **When** `mkcv generate ... --model-profile nope` runs, **then** the process exits with code 3 and prints `Unknown model profile 'nope'`.

### REQ-MP-4: `cover-letter --model-profile`

- **When** `mkcv cover-letter ... --model-profile openai` runs (service patched), **then** `create_cover_letter_service` receives `model_profile="openai"`.

## Advisor and warnings

### REQ-MP-5: No warnings for profile assignments

- **Given** an empty user config and keys for Anthropic, **when** `create_model_report(config, preset_name="standard")` runs, **then** `report.warnings == []`.
- **Given** `preset_name="concise"` (all Haiku), **then** `report.warnings == []` even though Haiku is below the `strong` minimum for select/tailor/review.

### REQ-MP-6: Below recommended tier

- **Given** `[default.pipeline.stages.tailor] provider = "openai"`, `model = "gpt-6.1-terra"` and `OPENAI_API_KEY` set, **then** the report has exactly one warning of kind `below_recommended_tier` for stage `tailor`, whose message is `tailor: openai/gpt-6.1-terra is tier 'efficient'; mkcv recommends at least 'strong' for this stage (recommended: openai/gpt-6-astra).`

### REQ-MP-7: Unknown model

- **Given** `[default.pipeline.stages.analyze] provider = "openai"`, `model = "gpt-7-nova"`, **then** the report has a warning of kind `unknown_model` for `analyze` whose message starts with `analyze: no capability data for openai/gpt-7-nova`.

### REQ-MP-8: Tier unknown

- **Given** a catalog override `{provider="groq", match="m"}` with no tier, provider `groq` defined, and `[default.pipeline.stages.select] provider = "groq"`, `model = "m"`, **then** the report has a `tier_unknown` warning for `select`.

### REQ-MP-9: Deprecated model

- **Given** `[default.pipeline.stages.analyze] provider = "google"`, `model = "gemini-2.5-flash"`, **then** the report has a `deprecated_model` warning for `analyze` containing `routes to gemini-3.5-flash-lite`.

### REQ-MP-10: Missing API key

- **Given** `model_profile="openai"` and no `OPENAI_API_KEY`, **then** the report has exactly one `missing_api_key` warning (not one per stage), with `stage is None` and message `openai: no API key found (set OPENAI_API_KEY); mkcv will use the offline stub and produce empty output.`
- **Given** `model_profile="local"`, **then** no `missing_api_key` warning is produced.

### REQ-MP-11: Recommended model and cost

- **Given** `[default.pipeline.stages.tailor] provider = "openai"`, `model = "gpt-6.1-terra"`, **then** the tailor `StageAdvice` has `recommended_provider == "openai"`, `recommended_model == "gpt-6-astra"`, and `estimated_cost_usd == round((15000 * 1.0 + 8000 * 5.0) / 1_000_000, 6)`.
- **Given** an empty user config, **then** `estimated_total_usd` equals the sum of the five pipeline stage costs computed from `STAGE_REQUIREMENTS` and catalog prices, and `estimate_is_partial is False`.
- **Given** a stage on an unknown model, **then** that stage's cost is `None` and `estimate_is_partial is True`.
- **Given** `model_profile="local"`, **then** every stage cost is `0.0` (from the Ollama provider defaults).

### REQ-MP-12: Warnings in `generate`

- **Given** REQ-MP-6's config, **when** `mkcv generate` runs (pipeline patched), **then** stdout/stderr contain `Warning: tailor: openai/gpt-6.1-terra is tier 'efficient'` and `Run 'mkcv models' for recommended models per stage.`, and the pipeline still runs.
- **Given** `[default.pipeline] model_warnings = false` and the same config, **then** no warning is printed.
- **Given** an empty user config with keys set, **then** no warning line is printed.

## `mkcv models`

### REQ-MP-13: Default view

- **Given** an empty user config and `ANTHROPIC_API_KEY` set, **when** `mkcv models` runs, **then** it exits 0 and the output contains:
  - `Model profile: anthropic (provisional: not yet backed by an eval run)`;
  - one row per stage in this order: `analyze`, `select`, `tailor`, `structure`, `review`, `cover_letter.generate`, `cover_letter.review`, `kb`, `validate`;
  - the column headers `Stage`, `Provider`, `Model`, `Source`, `Recommended`, `Tier`, `Est. cost`;
  - a line starting `Estimated cost per resume run (5 stages): $`.
- No `Warnings:` section is printed.

### REQ-MP-14: Flags

- **When** `mkcv models --model-profile openai` runs, **then** the header names `openai` and rows show OpenAI models with source `cli`.
- **When** `mkcv models --preset concise` runs, **then** the header names `anthropic-economy`.
- **When** `mkcv models --profiles` runs, **then** the output lists all seven profiles with provider, economy flag, evidence, and description.
- **When** `mkcv models --catalog --provider google` runs, **then** only `google` entries are listed, including `gemini-4-argon` with prices `4.00` / `20.00`.
- **When** `mkcv models --json` runs, **then** stdout parses as JSON and validates as `ModelReport`.
- **When** `mkcv models --profiles --json` runs, **then** stdout is a JSON list of seven profile objects.

### REQ-MP-15: Errors

- **Given** `[default.pipeline] model_profile = "nope"`, **when** `mkcv models` runs, **then** it exits 3.
- **Given** `[default.pipeline] provider = "openrouter"` and no per-stage models, **when** `mkcv models` runs, **then** it exits 3 with `Cannot resolve models:`.

## Documentation

### REQ-MP-16: Docs

- `docs/models.md` exists and contains: a per-stage recommendation table for each profile; how to override (`--model-profile`, `--provider`, `pipeline.model_profile`, `pipeline.provider`, per-stage keys, `[[default.model_catalog]]`, `[default.providers.<name>]`); the precedence order; capability caveats (sampling parameters, output-token floor, structured-output fallback for compatible endpoints, Gemini promotional prices, Haiku long-prompt pricing); the word `provisional` next to every profile not backed by an eval run; how evals produce recommendations.
- `README.md` provider section lists Anthropic, OpenAI, Google Gemini, and OpenAI-compatible endpoints (Ollama, OpenRouter, Groq, others), shows the `GEMINI_API_KEY` setup, links `docs/models.md`, and no longer documents `--profile` as current usage.
- `docs/specs/cli-interface.md` documents `mkcv models`, `--model-profile`, the updated `--provider` help, and exit code 3.
