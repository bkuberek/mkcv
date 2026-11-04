# Models and Providers

mkcv runs each AI stage on a provider and model you can choose. This page
explains what mkcv recommends, how to override it, what happens when two
settings disagree, and the model facts behind the defaults.

Run `mkcv models` at any time to see which model every stage will use, its
quality tier, and an estimated cost. Nothing in this page needs a network call
or an API key to check.

> **Every recommendation here is provisional.** The model choices come from
> vendors' published positioning and prices (retrieved 2026-11-03), not from
> measurements on mkcv's own pipeline. `mkcv models` says so in its header:
> `provisional: not yet backed by an eval run`. See [How recommendations are made](#how-recommendations-are-made).

## Providers

| Provider | Kind | API key | Notes |
|----------|------|---------|-------|
| `anthropic` | Anthropic | `ANTHROPIC_API_KEY` | Default. Claude models. |
| `openai` | OpenAI | `OPENAI_API_KEY` | GPT models through the Chat Completions API with strict JSON-schema output. |
| `google` | Google Gemini | `GEMINI_API_KEY`, else `GOOGLE_API_KEY` | Gemini models through the `google-genai` SDK. |
| `openrouter` | OpenAI-compatible | `OPENROUTER_API_KEY` | One key for many vendors. No model profile: name a model for each stage. |
| `ollama` | OpenAI-compatible | none | Local models at `http://localhost:11434/v1`. |
| `stub` | offline | none | Deterministic placeholder for tests and dry runs. |

If a provider needs a key and none is found, mkcv falls back to the offline
stub and warns you first (`openai: no API key found ...`). The run then
produces empty output instead of failing.

When both `GEMINI_API_KEY` and `GOOGLE_API_KEY` are set, mkcv uses
`GEMINI_API_KEY`. The Google SDK on its own prefers `GOOGLE_API_KEY`, but mkcv
passes the key it chose explicitly.

Any other OpenAI-compatible endpoint (Groq, Together, vLLM, LM Studio, a
company gateway) becomes a provider with a few lines of configuration. See
[Define your own provider](#define-your-own-provider).

## Model profiles

A model profile names one model per stage, all on one provider. The default
profile is `anthropic`.

| Stage | `anthropic` | `openai` | `google` | `local` |
|-------|-------------|----------|----------|---------|
| `analyze` | `claude-haiku-5-5` | `gpt-6-luna` | `gemini-3.5-flash-lite` | `llama3.1:8b` |
| `select` | `claude-opus-5-5` | `gpt-6.1-sol` | `gemini-4-argon` | `llama3.1:8b` |
| `tailor` | `claude-opus-5-5` | `gpt-6-astra` | `gemini-4-argon` | `llama3.1:8b` |
| `structure` | `claude-sonnet-5-5` | `gpt-6.1-terra` | `gemini-3.8-flash` | `llama3.1:8b` |
| `review` | `claude-opus-5-5` | `gpt-6.1-sol` | `gemini-4-argon` | `llama3.1:8b` |
| `cover_letter.generate` | `claude-opus-5-5` | `gpt-6-astra` | `gemini-4-argon` | `llama3.1:8b` |
| `cover_letter.review` | `claude-haiku-5-5` | `gpt-6-luna` | `gemini-3.5-flash-lite` | `llama3.1:8b` |
| `kb` | `claude-sonnet-5-5` | `gpt-6.1-sol` | `gemini-3.8-flash` | `llama3.1:8b` |
| `validate` | `claude-sonnet-5-5` | `gpt-6.1-terra` | `gemini-3.8-flash` | `llama3.1:8b` |

All four profiles are **provisional**. `local` is free and offline, and the
lowest quality: expect weaker tailoring than the cloud profiles.

The economy profiles change only the five resume pipeline stages. Every other
stage uses the model of the profile each one extends.

| Stage | `anthropic-economy` | `openai-economy` | `google-economy` |
|-------|---------------------|------------------|------------------|
| `analyze` | `claude-haiku-5-5` | `gpt-6-luna` | `gemini-3.5-flash-lite` |
| `select` | `claude-haiku-5-5` | `gpt-6.1-terra` | `gemini-3.8-flash` |
| `tailor` | `claude-haiku-5-5` | `gpt-6.1-terra` | `gemini-3.8-flash` |
| `structure` | `claude-haiku-5-5` | `gpt-6-luna` | `gemini-3.5-flash-lite` |
| `review` | `claude-haiku-5-5` | `gpt-6.1-terra` | `gemini-3.8-flash` |

`anthropic-economy` extends `anthropic`, `openai-economy` extends `openai`, and
`google-economy` extends `google`. All three are **provisional**.

### What a stage needs

Each stage has a minimum model tier. mkcv warns when a model you chose is
below it (see [Warnings](#warnings)). The token counts are rough planning
numbers, including typical thinking output, that feed the cost estimate.

| Stage | Config section | Minimum tier | Temperature | Est. tokens in / out |
|-------|----------------|--------------|-------------|----------------------|
| `analyze` | `pipeline.stages.analyze` | efficient | 0.2 | 4,000 / 2,000 |
| `select` | `pipeline.stages.select` | strong | 0.3 | 12,000 / 3,000 |
| `tailor` | `pipeline.stages.tailor` | strong | 0.5 | 15,000 / 8,000 |
| `structure` | `pipeline.stages.structure` | efficient | 0.1 | 10,000 / 6,000 |
| `review` | `pipeline.stages.review` | strong | 0.3 | 12,000 / 4,000 |
| `cover_letter.generate` | `cover_letter.stages.generate` | strong | 0.6 | 12,000 / 3,000 |
| `cover_letter.review` | `cover_letter.stages.review` | efficient | 0.2 | 5,000 / 2,000 |
| `kb` | `kb` | strong | 0.3 | 30,000 / 8,000 |
| `validate` | `validate` | efficient | 0.3 | 8,000 / 3,000 |

Tiers run `minimal`, `efficient`, `strong`, `frontier`. A model's tier is a
judgement from its price and the vendor's positioning, so treat it as a
starting point.

### Estimated cost per resume run

`mkcv models` prints this for the five resume stages. With the shipped prices
and token estimates, a run costs about:

| Profile | Estimate |
|---------|----------|
| `anthropic` | $0.54 |
| `anthropic-economy` | $0.02 |
| `openai` | $0.71 |
| `openai-economy` | $0.12 |
| `google` | $0.52 |
| `google-economy` | $0.20 |
| `local` | $0.00 |

These are estimates from rough token counts and list prices, not a quote.
Run `mkcv models --model-profile <name>` for the current figure.

## Choosing models

There are four ways to choose, from broadest to narrowest.

### Switch every stage with a flag

```bash
mkcv generate --jd job.txt --model-profile google
mkcv generate --jd job.txt --model-profile openai-economy
mkcv generate --jd job.txt --provider openai
mkcv cover-letter --jd job.txt --kb career.md --model-profile openai
```

`--model-profile` takes any profile name. `--provider` runs every stage on that
provider with its recommended models, and it also accepts providers that have
no profile (see below). The two flags cannot be combined: mkcv exits with code
3 and the message `--model-profile and --provider cannot be used together`.

### Set a default in `mkcv.toml`

```toml
[default.pipeline]
model_profile = "google"      # a profile name
# provider = "openai"         # used when model_profile is not set
```

Without `model_profile`, `pipeline.provider` picks that provider's profile, and
with neither, mkcv uses `anthropic`. Every `mkcv.toml` section header needs
the `default.` prefix. Without it the setting is silently ignored.

Environment variables work too, with double underscores for nesting:

```bash
export MKCV_PIPELINE__MODEL_PROFILE=google
export MKCV_PIPELINE__STAGES__TAILOR__MODEL=gpt-6-astra
```

### Override one stage

```toml
[default.pipeline.stages.tailor]
provider = "anthropic"
model = "claude-opus-5-5"
temperature = 0.5

[default.cover_letter.stages.generate]
model = "gpt-6-astra"         # provider inferred from the catalog

[default.kb]
provider = "google"           # model from the google profile

[default.validate]
model = "gpt-6.1-terra"
```

A stage that sets only `model` runs on the one provider that offers it. If
several providers offer it, or none does, mkcv uses the active profile's
provider, else `pipeline.provider`, else `anthropic`. A stage that sets only
`provider` uses that provider's recommended model for the stage.

These settings are **honoured by `mkcv generate`**. Earlier versions replaced
them with the preset's models, so per-stage `provider` and `model` keys in
`mkcv.toml` were ignored for resume generation. If you have such keys, they now
take effect, and `mkcv models` shows which stages they change.

### Presets

A preset (`--preset concise|standard|comprehensive`) sets how much the resume
says. It does not choose models, with two exceptions: `concise` asks for the
economy variant of the profile that `pipeline.model_profile`, `pipeline.provider`,
or `--provider` selects, and the legacy `budget` preset pins the `ollama`
provider. A profile you name with `--model-profile` is used as it is, so
`--preset concise --model-profile openai` runs the full `openai` profile; pass
`--model-profile openai-economy` for the economy mix.
`--profile budget|premium|default` still works as a deprecated alias.

## Precedence

When settings disagree, mkcv picks a stage's model in this order, first match
wins:

1. `kb --model` (the `kb` command only), on `kb --provider` if given, else the
   provider the stage is configured for.
2. `--model-profile` on the command line: every stage uses that profile.
3. `--provider` on the command line, or the provider of the `budget` preset.
   A stage keeps its own `[default...]` entry only when that entry names a
   `model` and the same `provider`. Every other stage uses the provider's
   recommended model. A stage that sets only `model` does not count, so give
   a stage both keys when it must survive `--provider`.
4. A per-stage `model` in `mkcv.toml` (or an environment variable).
5. A per-stage `provider` in `mkcv.toml`: that provider's recommended model.
6. `pipeline.model_profile`, or the profile of `pipeline.provider`, or the
   `anthropic` profile.

A provider with no profile (`openrouter`, or a provider you define) cannot
supply models. If a stage reaches the end of this list without a model, mkcv
exits with code 3 before any call, listing every stage that needs a
`model` and the config path to set it.

The `stub` provider needs no model: it uses `stub-model` unless a stage names
one.

## Warnings

Before `generate` and `cover-letter` run, mkcv prints non-blocking warnings
about the models it is about to use, then a pointer to `mkcv models`. A warning
never stops a run.

| Warning | When |
|---------|------|
| Below recommended tier | You chose a model whose tier is under the stage's minimum. |
| Tier unknown | You chose a model that is in the catalog without a tier. |
| Unknown model | The catalog has no data for the model. mkcv uses conservative defaults. |
| Deprecated model | The provider has deprecated the model; the note says where requests go. |
| Missing API key | A provider's key is not set (reported once per provider). |

mkcv does not question models it picked itself. A profile's own assignments
(including `--model-profile anthropic-economy`) never get tier warnings, and
neither does the offline stub. Deprecation and missing-key warnings always
apply.

Turn the warnings off with:

```toml
[default.pipeline]
model_warnings = false
```

## Define your own provider

Any endpoint that speaks the OpenAI Chat Completions API is a provider:

```toml
[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"      # a name or a list of names
# api_key = "..."                 # a literal key; prefer the environment
# requires_api_key = true
```

Use it per stage (`provider = "groq"`), with `--provider groq`, or with
`pipeline.provider = "groq"`. Because it has no profile, name a `model` for
each stage that uses it.

The same table overlays a built-in provider (for example a different
`base_url` for `openai`). A built-in provider's `type` cannot be changed. The
valid types for a new provider are `anthropic`, `openai`, `google`, and
`openai-compatible`. `base_url` is required for `openai-compatible`.

### Describe a model mkcv does not know

mkcv keeps a catalog of what it knows about each model: tier, prices, and how
a request must be shaped. Add or correct an entry with an array-of-tables
`[[default.model_catalog]]`:

```toml
[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"   # a model ID, or a prefix with match_type = "prefix"
tier = "efficient"                  # minimal, efficient, strong, frontier
structured_output = "json_object"   # json_schema, tool, json_object, prompt
input_price_per_mtok = 0.59         # USD per 1M tokens
output_price_per_mtok = 0.79
```

Fields you leave out inherit from the provider. A user entry with the same
`provider`, `match`, and `match_type` as a built-in one overlays it field by
field. `mkcv models --catalog` lists everything, overrides included, and
`mkcv models --catalog --provider groq` filters by provider.

## What the catalog changes about a request

These rules live in the catalog and the provider defaults, not in code, so
you can correct them for a model that behaves differently.

- **Sampling parameters.** Claude 5.x, GPT-5.x and GPT-6.x, the o-series, and
  Gemini models are treated as not accepting `temperature`, so mkcv omits it.
  The configured `temperature` still applies to Claude 4.x and to
  OpenAI-compatible endpoints. If a provider rejects `temperature` for a model
  mkcv thought accepted it, mkcv retries once without it and leaves it out for the rest of the run.
- **Output-token floor.** Reasoning models spend output tokens thinking before
  they answer, so mkcv asks for at least 16,000 output tokens for the models
  that think. A model's `max_output_tokens` caps the request.
- **Structured output.** Anthropic, OpenAI, and Google always use their native
  schema-constrained output. An OpenAI-compatible endpoint starts at the mode
  its entry names and, if the endpoint rejects it, steps down: JSON schema,
  then JSON object, then a schema written into the prompt. Every provider gets
  one repair retry when a reply is not valid for the schema. Ollama starts at
  JSON object mode.
- **Unknown models.** The three native providers assume a model that is not in
  the catalog is new: no `temperature`, a 16,000-token floor, and schema
  output. OpenAI-compatible endpoints keep `temperature` and may degrade.
- **Prices.** Costs use list prices per 1M tokens. Two caveats apply:
  Gemini 4 and Gemini 3.8/3.6 Flash have promotional prices through the dates
  below, while mkcv's catalog carries the later standard prices, so the
  estimate is high until then. Claude Haiku 5.5 bills prompts over 100,000
  tokens at the higher $0.50/$2.50 rate, which a long knowledge base can hit.

## How recommendations are made

A profile is **provisional** until an eval run backs it, and every profile in
this document is provisional today. The recommendations above follow vendor
positioning and price. They do not come from scoring the models on mkcv's own
pipeline, and quality tiers outside Anthropic are judgements.

The eval harness in the repository's top-level `evals/` directory (not shipped
with the package; see [evals/README.md](../evals/README.md)) replaces judgement
with measurement. It runs each of the five resume pipeline stages on its own,
with the same reference input for every model, across a matrix of models on
synthetic personas and job descriptions. Each output is graded by rules
(schema, ATS rules, keyword recall, and whether every number, employer, title,
and skill traces back to the knowledge base) and, for the subjective parts, by
a judge model. Faithfulness, meaning no fact that is absent from the knowledge
base, is the metric that matters most for a resume.

A model is **eligible** for a stage only if at least 95% of its runs completed,
at least 95% of its outputs had the stage's shape, and, where the stage has
them, its deterministic faithfulness score is at least 0.95 and its judged one
at least 0.90. For each stage and provider the report then names:

- **best**: the eligible model with the highest quality score on the stage's
  primary metric (ties go to the cheaper model, then the faster one).
- **recommended**: the cheapest eligible model whose score is within 0.05 of the
  best.
- **economy**: the cheapest eligible model scoring at least 0.70.

The report ends with the profile changes those results suggest. They are never
applied automatically: the maintainer edits
`src/mkcv/core/catalog/builtin_model_profiles.py` (setting `evidence="eval"` and
the run's ID) and this document, citing the published report under
`evals/results/published/<run id>/`. A profile that has been updated this way
reports `eval-backed: <run>` in `mkcv models` instead of `provisional`.

Read an eval-backed row with its caveats in mind: a judge from the same provider
as the evaluated model may favour it (the report marks those rows as
self-judged), and a row with fewer than six runs is a low sample. Until the
first run, treat every recommendation here as a reasonable default, not a
benchmark result.

## Verified facts

Retrieved 2026-11-03. Prices are USD per 1M input / output tokens.

### OpenAI

| Fact | Value | Source |
|------|-------|--------|
| Models | `gpt-6-astra` (flagship), `gpt-6.1-sol` (balanced), `gpt-6.1-terra`, `gpt-6-luna` (most efficient) | [OpenAI models](https://developers.openai.com/api/docs/models) |
| Limits | All four: 1,050,000 context, 128,000 max output | [`gpt-6-astra`](https://developers.openai.com/api/docs/models/gpt-6-astra) and the other three model pages |
| Prices | astra $10 / $50; sol $2 / $10; terra $1 / $5; luna $0.10 / $0.50; prompts over 272K tokens bill 2x input and 1.5x output | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| Structured outputs | Supported on all four; strict mode needs `additionalProperties: false` and every field required | [Structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) |

### Google Gemini

| Fact | Value | Source |
|------|-------|--------|
| Models | `gemini-4-argon` (pro tier), `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview` | [Gemini models](https://aistudio.google.com/docs/models) |
| Prices | argon $2 / $10 through 2026-11-30, then $4 / $20; 3.8-flash and 3.6-flash $0.75 / $3.75 through 2026-12-31, then $1.50 / $7.50; 3.5-flash-lite $0.30 / $2.50; 3.1-flash-lite $0.25 / $1.50; 3.1-pro-preview $2 / $12 up to 200K tokens, $4 / $18 above | [Gemini pricing](https://aistudio.google.com/docs/pricing) |
| Deprecations | `gemini-2.5-flash` and `gemini-2.5-pro` are deprecated; from 2026-12-01 they route to `gemini-3.5-flash-lite` and `gemini-3.8-flash` | [Gemini models](https://aistudio.google.com/docs/models) |
| Structured output | A JSON Schema subset; unsupported keywords are dropped, and a very large schema returns a 400 | [Structured output](https://aistudio.google.com/docs/structured-output) |
| SDK | `google-genai` 2.34.0 (2026-10-29), Python 3.11 or newer | [PyPI](https://pypi.org/project/google-genai/) |

### Anthropic

| Fact | Value | Source |
|------|-------|--------|
| Models | `claude-fable-5-1` $10 / $50; `claude-opus-5-5` $4 / $20; `claude-sonnet-5-5` $2 / $10; `claude-haiku-5-5` $0.10 / $0.50 up to 100K tokens, $0.50 / $2.50 above. All have a 1M context window and 128K max output. | Anthropic model documentation |
| Sampling | Claude 5.x models reject `temperature`, `top_p`, and `top_k`; mkcv omits them | Anthropic model documentation |
| Structured output | `output_config.format` with a JSON schema; a forced tool call returns 400 on Opus 5.5 and Sonnet 5.5, so mkcv uses schema output for them | Anthropic model documentation |

### Not verified

mkcv's defaults avoid depending on these, and the catalog lets you correct them.

| Claim | Status |
|-------|--------|
| GPT-6 models reject `temperature` | Not stated in OpenAI's documentation. GPT-5 and the o-series reject non-default values, so mkcv omits it for the whole family. |
| Gemini 3.5 and later accept `temperature` | Not verified, so mkcv omits it for Google. |
| Gemini `max_output_tokens` includes thinking tokens | Not verified, so mkcv asks for at least 16,000. |
| Quality tiers for every non-Anthropic model | A judgement from price and positioning. |
| Ollama supports JSON-schema output | Not verified, so Ollama starts at JSON object mode. |
| OpenRouter model IDs for current models | Not verified, so there is no `openrouter` profile. |
| GPT-4.x prices in the catalog | Kept from earlier versions for backward compatibility, not re-verified. |

## Exit codes

A configuration problem exits with **code 3** before any model is called:
an unknown provider or model profile, `--model-profile` combined with
`--provider`, a stage with no model, or an invalid `[default.providers.*]` or
`[[default.model_catalog]]` entry. A missing API key is a warning, not an
error. See the [CLI reference](specs/cli-interface.md#exit-codes).
