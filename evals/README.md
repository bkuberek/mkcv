# mkcv eval harness

An offline harness that finds the best model for each stage of mkcv's resume
and cover letter pipelines. Its report suggests changes to the model profiles
in `src/mkcv/core/catalog/builtin_model_profiles.py` and a cross-provider
`recommended` profile; the maintainer applies them by hand. Nothing here ships
in the mkcv package.

Run everything from the repository root:

```bash
uv run python -m evals --help
```

## What it does

For every combination of **model**, **case** (a synthetic persona plus a job
description), and **stage**, the harness runs that one stage on its own. Stage
inputs come from reference artifacts, so every model sees the same input
whatever earlier stages would have produced for it. It evaluates seven stages:
the five resume stages (`analyze`, `select`, `tailor`, `structure`, `review`)
and the two cover letter stages (`cover_letter.generate`,
`cover_letter.review`). The `kb` and `validate` stages are not evaluated: the
harness has no fixtures or graders for them yet, and the report lists them as
not evaluated.

Each output is graded:

| Kind | Grades |
|------|--------|
| By rule | `schema`, `jd_keyword_recall`, `ats_rules` (seven ATS rules), `structure`, `cover_letter_rules` (word bounds, paragraphs, no first-person plural or placeholders, the company, role, and candidate named correctly), and `faithfulness_extraction` (numbers, employers, titles, names, and forbidden claims traced to the knowledge base) |
| By the judge panel | `faithfulness_judge`, `selection_judge`, `tailoring_judge`, `cover_letter_judge`, `review_defect_recall`, and `cover_letter_defect_recall` (the last two on probe cases with planted defects) |

Analyze and structure are graded by rule only. Add them to `[run]
judged_stages` in `config/matrix.toml` to judge them too (structure then gets a
faithfulness judge; analyze has no judge rubric).

Numbers match by value: `9,800` matches `9.8k`, `$1.2M` matches `$1,200,000`,
and `40 percent` matches `40%`.

The commands:

| Command | What it does |
|---------|--------------|
| `list-cases` | Lists the cases and whether their reference artifacts exist |
| `estimate` | Prints what a run would cost, by round and by provider; `--bootstrap` prices `bootstrap-reference` instead |
| `bootstrap-reference` | Produces the reference artifacts: stages 1 to 4 and the cover letter |
| `check-reference` | Lists every reference claim the knowledge base does not support |
| `run` | Runs the tournament, grades, and writes `results.jsonl`, `run.json`, `usage.jsonl`, `summary.json`, and `report.md` |
| `report DIR` | Rebuilds `summary.json` and `report.md` from a run directory; `--publish` shares the run |

## Fixtures

Every person, employer, school, city, and number in `fixtures/` is invented.
`cases.toml` pairs 13 personas with 23 job descriptions in 26 cases:

- **Personas** span new graduate to executive and nine fields beyond software
  (healthcare, education, security, accounting, operations, customer success,
  design, research, and marketing). Each one carries a hard situation: a career
  switch, a three-year gap, three short tenures, a freelancer with eleven
  clients, a thirty-year career, a non-US career, a messy notes-style
  knowledge base, or a verbose one with far more material than fits.
- **Match and stretch.** Most personas have a strong match and a stretch job.
  `forbidden_claims` lists what the job asks for and the knowledge base lacks,
  so a faithful resume must not claim it. The "overreach" jobs pile on keyword
  bait. For the newer cases every `expected_keywords` term appears in both the
  job description and the knowledge base.
- **Review probes.** `review-probe` seeds three defects; `review-probe-clinical`
  and `review-probe-customer-success` seed six each (an invented metric, a
  first-person bullet, a missing requirement the knowledge base supports, a
  contradicted date, a vague bullet, and an unsupported skill).
- **Cover letters.** `fixtures/cover_letter_cases.md` lists the 13 cases suited
  to cover letter evaluation and what each letter must and must not say; their
  `[cases.cover_letter]` tables in `cases.toml` carry those rules.

`tests/test_evals/test_fixtures.py` checks these rules.

## Cases

`fixtures/cases.toml` defines the cases. A case runs every resume stage. It
runs the cover letter stages only when it has a `[cases.cover_letter]` table,
which says what the letter must and must not do:

```toml
[[cases]]
id = "customer-success-ae-overreach"
persona = "personas/customer-success-manager.md"
jd = "jds/customer-success-ae-overreach.md"
forbidden_claims = ["MEDDICC", "quota", "new logo", "Gong"]

[cases.cover_letter]
must = ["present the move from customer success to sales honestly"]
should_connect = ["her procurement software domain knowledge to the spend management product"]
must_not_claim = ["quota attainment", "President's Club"]
must_not = ["describe her as an account executive"]
```

| Field | Meaning |
|-------|---------|
| `company`, `role` | The company and role the letter must name; by default, those of the case's reference JD analysis |
| `must_not_claim` | Literal terms the letter must not claim, checked by rule and by the faithfulness judge. The case's `forbidden_claims` apply to the letter too. A sentence that states a gap ("I have not used ...") is not a claim. |
| `must`, `should_connect`, `must_not` | Rules only a judge can check; the judges see them as guidance |
| `min_words`, `max_words` | The letter's word bounds (250 to 400 by default, as the prompt asks) |
| `review_defects` | Makes the case a cover letter review probe: its `reference/<case>/cover_letter_content.json` is written by hand with these defects planted, and `cover_letter.review` is graded by how many the review catches. Set `stages = ["cover_letter.review"]` on such a case. |

No case is a cover letter review probe yet, so `cover_letter.review` gets no
quality score until one is added.

## How a model is chosen

The rule is **quality first**.

1. **Hard gates.** A model is eligible for a stage only if at least 95% of its
   runs completed, its `schema` mean is at least 0.95, and, where the stage
   has faithfulness grades, no run contains a fabricated claim
   (`[recommendation] max_fabrication_rate`, 0 by default), its deterministic
   faithfulness mean is at least 0.95, and its judged one at least 0.90. A
   faithfulness grade fails a run on any unsupported claim: one fabrication
   in twenty claims is enough. A model that misses a gate is never
   recommended, however well it writes.
2. **Highest quality wins.** Among eligible models, the one with the highest
   primary score wins, across all providers and within each one.
3. **Cost only breaks ties.** Models within `[recommendation] tie_epsilon`
   (0.01) of the best score count as tied, and the cheapest of them wins. The
   report says when cost decided.
4. **Too close to call.** When the winner's lead over another model is smaller
   than the noise of that lead (the standard error of their per-case
   differences), the report marks the call too close and lists the
   runners-up. Run more repeats or cases to separate them.

The primary score of each stage:

| Stage | Primary score |
|-------|---------------|
| `analyze` | `jd_keyword_recall` |
| `select` | `selection_judge` |
| `tailor` | `tailoring_judge` |
| `structure` | `ats_rules` |
| `review` | `review_defect_recall` (review probes) |
| `cover_letter.generate` | `cover_letter_judge` |
| `cover_letter.review` | `cover_letter_defect_recall` (cover letter probes) |

### The judge panel

Every judged output is scored by each judge of `[[judges]]`: by default the
top catalog tier of each provider, `anthropic/claude-opus-5-5`,
`openai/gpt-6-astra`, and `google/gemini-4-argon`. The grade is their mean, and
each judge's score is kept. A judge whose provider has no credentials is
skipped with a warning, and `run.json` records which judges ran. One `[judge]`
table still works, as a panel of one.

Judges may favour their own provider's models. A model's quality score
therefore leaves out the judge from its own provider whenever another judge
scored the output. A row is **self-judged** only when its own provider's judge
was the only one; the report flags it. The report also shows how often the
judges agree (within 0.1) and the mean score each judge gave per stage.

### The tournament

A run has two rounds (`[tournament]`):

1. **Screening.** Every model runs every stage on eight representative cases
   (`screening_cases`) and every review probe, once, graded by one judge from
   another provider (the cheapest).
2. **Elimination.** Per stage, a model is eliminated only when it fails a hard
   gate or trails the leader by more than `margin` (0.05) plus the noise of
   that lead. The top `keep_top` (3) models of each stage and the best of each
   provider always go on, so every provider profile can be filled.
3. **Finals.** The survivors run on every case with the whole panel and
   `[run] repeats` (2). The recommendations come from the finals; the report's
   Tournament section says why each model went on or not.

`run --single-round` skips the tournament and runs every model on every case.

### Batching and caching

Stage and judge calls go out as provider batches (`[batch]`), at the 50%
batch discount the three providers publish: Anthropic Message Batches, the
OpenAI Batch API, and Vertex AI batch prediction. Each call still goes through
mkcv's own adapter, so a batch carries the same request an online call would.
Vertex AI batches need a Cloud Storage bucket (`google_gcs_bucket`, by default
`gs://destinyventures-mkcv-evals`; each run writes under `runs/<run id>/`).
Without Vertex AI or a bucket, Google calls go online with a warning.
`--no-batch` sends every call online.

Judge requests lead with what every output of a case shares, byte for byte:
the rubric, the job description, the knowledge base, and the case's guidance.
With `[caching]` enabled, Anthropic requests mark that prefix for the prompt
cache; OpenAI and Gemini cache it on their own. `--no-cache` turns the markers
off. Stage prompts are mkcv's own templates and are not cached.

Every call's tokens, cache reads, and whether it was batched go to
`usage.jsonl`, and the report's Cost section sets what the run cost as sent
beside its online price.

## Prerequisites

Export an API key for every provider you want to evaluate, and for every
judge:

| Provider | Variable |
|----------|----------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), or Vertex AI with Application Default Credentials, configured through `MKCV_PROVIDERS__GOOGLE__*` |

A model whose provider has no credentials is skipped with a warning, and the
report lists it. `run --strict` turns a missing model or judge into an error
before any call is made. Google batches need Vertex AI.

## Step by step

1. **Check the cost.**

   ```bash
   uv run python -m evals estimate
   uv run python -m evals estimate --bootstrap
   ```

   The estimate prices screening for every model, the finals for the dearest
   model of each provider (the survivors are unknown until screening ends),
   and a worst case with no model eliminated, each by provider and with the
   online price beside the batched one. For the shipped matrix and fixtures it
   is about $177 (worst case about $361), against about $703 for the same
   panel and repeats run online in a single round
   (`estimate --single-round --no-batch --no-cache`). These are planning token
   counts, not measurements; `report.md` shows what the run used.

2. **Bootstrap the reference artifacts** (once, until the fixtures change):

   ```bash
   uv run python -m evals bootstrap-reference --yes
   uv run python -m evals check-reference
   ```

   The reference model (`[reference]`) runs stages 1 to 4 and then the cover
   letter for every case, writing the results to
   `evals/fixtures/reference/<case>/`. Cases run concurrently, so each stage
   level goes out as one batch; the batch state lives in
   `evals/results/bootstrap/`, so running the command again resumes it. Each
   review probe copies its stage 1 to 3 files from the case with the same
   persona and job description and keeps its hand-written resume.

   `check-reference` lists every number, employer, title, name, and forbidden
   term in the references that the knowledge base does not support. **Review
   every file under `evals/fixtures/reference/` by hand** before committing:
   the references are the input every evaluated model sees, so a fabricated
   fact there poisons the whole run. An existing reference is never
   overwritten; delete a case's file to regenerate it.

3. **Run the matrix.**

   ```bash
   uv run python -m evals run --yes
   ```

   Without `--yes` it asks `Proceed? [y/N]`, and exits 2 when stdin is not a
   terminal. Results go to `evals/results/<UTC time>-<commit>/` (gitignored).
   Failed records do not stop the run or change the exit code.

   If a run stops, continue it with `--resume`: the records already written
   are kept, and calls already submitted in a batch are collected, not paid
   for again.

   ```bash
   uv run python -m evals run --yes --resume evals/results/<run>
   ```

   `--round screening` runs only the first round; `--round finals --resume
   <run>` runs the finals of a screened run.

4. **Read `report.md`.** See the next section.

5. **Publish the run** so the evidence is in the repository:

   ```bash
   uv run python -m evals report evals/results/<run> --publish
   ```

   This copies `results.jsonl`, `summary.json`, `report.md`, `run.json`, and
   `usage.jsonl` (not the `raw/` outputs or `batches/`) to
   `evals/results/published/<run id>/`. Commit that folder.

6. **Apply the results by hand.** Edit
   `src/mkcv/core/catalog/builtin_model_profiles.py` following "Suggested
   profile changes" and set `evidence="eval"` and `eval_run="<run id>"` on each
   profile you updated. Then update `docs/models.md`, citing
   `evals/results/published/<run id>/report.md`. Commit as
   `feat(catalog): adopt eval-backed model recommendations`. Nothing applies
   results automatically.

## Reading the report

`report.md` has these sections, in order:

- **Run**: the run ID, time, versions, judges and which ran, cases, and
  models.
- **Caveats**: what weakens the numbers: self-judged rows, rows with fewer
  than six runs, skipped models and judges, failed records, and a run that has
  only screened.
- **Judge panel**: how the panel scores, how often the judges agree, and the
  mean score each judge gave.
- **Cost**: what each model and judge cost as sent, beside the online price.
- **Tournament**: each model's screening score per stage and why it went on to
  the finals or not.
- **Stage: ...**: per stage, the best model overall, the best of each
  provider, and the full table: quality as mean ± standard deviation, the
  all-judge mean, the judges' spread, fabrication rates, cost, latency, and
  whether the model is **Eligible** (the Notes column names any gate it
  missed).
- **Recommendations**: one row per stage with the best model overall and per
  provider, cost ties, calls too close to call, and the stages not evaluated.
- **Suggested profile changes**: the provider profiles (`anthropic`, `openai`,
  `google`) where a stage's best model differs from today's, and the
  cross-provider `recommended` profile, also written as `mkcv.toml` stage
  overrides. Economy profiles are not changed: this rule recommends the best
  model, not the cheapest.
- **Token estimates**: measured median tokens per stage next to the planning
  estimates in `STAGE_REQUIREMENTS`.

`summary.json` holds the same conclusions as data: the stage summaries, the
recommendations, the suggested profiles, the screening decisions, the primary
metric of each stage, and the stages not evaluated.

## Layout

```text
evals/
  cli.py              commands
  config/matrix.toml  the default matrix: models, judges, tournament, batching
  fixtures/           personas, job descriptions, cases.toml, reference artifacts
  graders/            rule-based and judge graders, with rubrics/
  harness/            stage runner, matrix runner, tournament, cost estimate, bootstrap
  batch/              provider batches, transports, usage ledger, prompt caching
  models/             Pydantic models for cases, records, summaries, settings
  report/             aggregation, recommendations, profile suggestions, report
  results/            run output (gitignored); published/ holds shared runs
```

The tests under `tests/test_evals/` use stub providers, a stub judge panel,
and fake batch clients, and never reach the network.
