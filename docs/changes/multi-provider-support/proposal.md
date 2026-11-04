# Proposal: Multi-Provider Support

## Intent

mkcv works well only with Anthropic today. OpenAI requests use JSON mode (`response_format={"type": "json_object"}`) with no schema enforcement, Google is not supported at all, Ollama and OpenRouter are hardcoded special cases, and the factory falls back to `"anthropic"` / `"claude-sonnet-5-5"` in a dozen places. Worse, `mkcv generate` always resolves a preset (`standard` when `--preset` is omitted) and a preset replaces every per-stage `provider`/`model` from `mkcv.toml`, so the per-stage overrides that the README and workspace template tell users to write are silently ignored by `generate`.

This change makes mkcv provider-agnostic. Users can run any stage on Anthropic, OpenAI, Google Gemini, or any OpenAI-compatible endpoint (Ollama, OpenRouter, Groq, vLLM, LM Studio, Together, and others). mkcv states clearly which model it recommends for each stage, warns when a stage runs on a weaker or unknown model, and keeps every per-stage setting under the user's control. An offline eval harness produces the evidence behind those recommendations.

## Scope

### In scope

1. **Provider registry.** One table of provider specs (built-in plus user-defined in config) replaces the `if/elif` dispatch in `adapters/factory.py`. Provider kinds: `anthropic`, `openai`, `google`, `openai-compatible`, `stub`. `ollama` and `openrouter` become built-in `openai-compatible` providers, so existing configs keep working.
2. **Model capability catalog.** Data, not code branches: per model or model prefix, the provider, structured-output mode, whether sampling parameters are accepted, the output-token floor, the token-limit parameter name, context window, prices, quality tier, and deprecation. Built-in data ships in the package; users extend or override it with `[[default.model_catalog]]` entries. Unknown models run with conservative defaults and a warning. `calculate_cost` and `MODEL_PRICING` derive from the catalog and keep their signatures and results.
3. **OpenAI native structured outputs.** The OpenAI adapter sends `response_format={"type": "json_schema", "json_schema": {..., "strict": true}}` with a strict schema, handles refusals and truncation, and omits sampling parameters for reasoning models.
4. **Generic OpenAI-compatible adapter.** Configured by `base_url` and an API-key env var name. Structured output degrades `json_schema` → `json_object` → prompt-instructed JSON, always validated with Pydantic, with one repair retry.
5. **Google Gemini adapter.** Uses the official `google-genai` SDK (`client.aio.models.generate_content`) with `response_mime_type="application/json"` and `response_json_schema`.
6. **Model profiles and stage resolution.** Recommended model profiles per provider (`anthropic`, `anthropic-economy`, `openai`, `openai-economy`, `google`, `google-economy`, `local`). One resolver owns precedence: CLI flags, then per-stage config keys, then the model profile. Existing preset names (`concise`, `standard`, `comprehensive`, legacy `budget`, `premium`, `default`) keep working and now control content density only, plus which profile variant applies.
7. **`mkcv models` command.** Shows, per stage, the configured model, the recommended model, where the setting came from, capability warnings, missing API keys, and an estimated cost per run. Also lists profiles and the catalog.
8. **Non-blocking warnings in `generate` and `cover-letter`** when a stage uses a model below the stage's minimum tier, a model with no catalog entry, a deprecated model, or a provider whose API key is missing.
9. **Eval harness** in a top-level `evals/` package: synthetic fixtures, per-stage runs across a model matrix, deterministic graders (schema, ATS rules, structure, faithfulness extraction), LLM-judge graders (faithfulness, tailoring, review defect recall) with a configurable judge model, cost and latency, machine-readable results, and a Markdown report. Live runs are manual (one documented command); CI runs only grader and runner unit tests against recorded or stub outputs.
10. **Docs.** New `docs/models.md`; README provider section; `docs/specs/*` updates; workspace template and workspace README. Recommendations without an eval run behind them are labelled provisional.

### Out of scope

- A live eval run and evidence-backed recommendations. The owner runs the first eval manually; until then every profile is `provisional`.
- Evals for the cover-letter, KB-generation, and validation stages. Their recommendations stay provisional.
- The OpenAI Responses API. The adapter uses Chat Completions, which every current OpenAI model supports with structured outputs (see design §12). Migrating to Responses is a follow-up the evals can justify.
- Reasoning-effort or thinking-level tuning per stage. Provider defaults apply.
- Prompt caching, batch APIs, and streaming for non-Anthropic providers.
- Vertex AI, Bedrock, and Azure OpenAI as distinct provider kinds. An OpenAI-compatible gateway can still reach them.
- An `openrouter` model profile. OpenRouter model IDs for current models are unverified; users set per-stage models or a custom profile.
- Automatic rewriting of built-in recommendations from eval output. The report suggests profile changes; a human applies them.

## Behaviour changes users will notice

| Change | Before | After |
|---|---|---|
| Per-stage `provider`/`model` in `mkcv.toml` with `generate` | Ignored (preset `standard` replaced them) | Honoured. Per-stage keys override the model profile. |
| `--provider openai` | Kept the Claude model names and sent them to OpenAI | Uses the recommended OpenAI model for each stage, unless the stage's config already names a model for that provider |
| `--provider X` for a provider with no profile (for example `openrouter`, `groq`) | Sent Claude model names to X | Exits with code 3 and lists the stages that need `pipeline.stages.<stage>.model` |
| OpenAI structured calls | JSON mode, schema in the prompt | Strict JSON-schema structured outputs |
| `validate` model | Hardcoded `claude-sonnet-5-5` sent to the analyze stage's provider | Resolved `validate` stage (profile default `claude-sonnet-5-5` for Anthropic) |
| Unknown or below-tier model | Silent | Yellow warning before the run; never blocks |
| Built-in `settings.toml` | Sets `provider`/`model` for every stage | Sets only temperatures; models come from the profile |

With no user config and no flags, every stage resolves to exactly the same provider, model, and temperature as today.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unverified sampling-parameter rules for GPT-6 and Gemini 3.x/4 | Medium | Request fails with HTTP 400 | Catalog omits `temperature` for these models (omitting is always accepted). Adapters also catch a 400 that names `temperature` or `max_tokens`, adapt the request once, and cache the adaptation per model. |
| Anthropic API version `2026-10-21` rejects `temperature` on every model | Medium (on a future SDK upgrade) | Claude 4.x requests fail | The same request adaptation in the Anthropic adapter drops `temperature` and retries once. |
| OpenAI strict schema rejects a response model | Low | Structured calls fail | The strict-schema transformer whitelists supported keywords, inlines `$defs`, and sets `additionalProperties: false` and full `required`. Every `complete_structured` response model gets a unit test that the transformed schema satisfies the documented rules. |
| Precedence change surprises users whose `mkcv.toml` had stale per-stage models | Medium | Different models than the user expected | `generate` prints the resolved model per stage with `--verbose`, `mkcv models` shows source per stage, and the change is called out in the changelog and `docs/models.md`. |
| Provisional recommendations are wrong for non-Anthropic providers | Medium | Lower quality output | Profiles are labelled provisional in `mkcv models` and docs. The eval harness exists to replace them. |
| Gemini promotional prices end 2026-12-01 / 2027-01-01 | Certain | Cost estimates differ from bills during the promo | The catalog records the post-promo price (conservative). `docs/models.md` notes the promotion. |
| `google-genai` adds install weight | Low | Larger install | The adapter imports the SDK lazily, so startup time is unchanged. |
| Eval judge favours its own provider | Medium | Biased recommendations | The judge is configurable, and the report flags self-judged rows. |

## Rollback

Each phase is its own set of Conventional Commits on `feat/multi-provider-support` and can be reverted independently in reverse order:

- **P4** (evals) touches only `evals/`, `tests/test_evals/`, `pyproject.toml` pytest `pythonpath`, `.gitignore`, CI lint paths, and docs. Revert freely.
- **P3** (profiles, resolver, `mkcv models`, warnings, docs). Reverting restores preset-driven model selection; `settings.toml` regains its per-stage `provider`/`model` keys in the same revert.
- **P2** (Google) removes the adapter, the registry entry, and the `google-genai` dependency. Catalog entries for Gemini stay harmless.
- **P1** (registry, catalog, OpenAI-compatible, OpenAI strict outputs). Reverting restores the `if/elif` factory and `ollama.py`.

No data migration is needed. Run metadata written by the new code has the same schema.

## Dependencies

- New runtime dependency: `google-genai>=2.34.0` (P2).
- No version bump for `openai` (installed 2.29.0; `response_format` JSON schema and `max_completion_tokens` exist since well before the declared minimum `>=1.50`) or `anthropic` (0.86.0).
