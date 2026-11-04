# mkcv eval harness

An offline harness that measures how well models do each stage of mkcv's resume
pipeline. Its report suggests changes to the model profiles in
`src/mkcv/core/catalog/builtin_model_profiles.py`; the maintainer applies them
by hand. Nothing here ships in the mkcv package.

Run everything from the repository root:

```bash
uv run python -m evals --help
```

## What it does

For every combination of **model**, **case** (a synthetic persona plus a job
description), and **stage**, the harness runs that one pipeline stage on its own.
Stage inputs come from reference artifacts, so every model sees the same input
whatever earlier stages would have produced for it. Each output is graded:

| Kind | Grades |
|------|--------|
| By rule | `schema`, `jd_keyword_recall`, `ats_rules` (seven ATS rules), `structure`, `faithfulness_extraction` (numbers, employers, titles, and forbidden skills traced to the knowledge base) |
| By a judge model | `faithfulness_judge`, `selection_judge`, `tailoring_judge`, and `review_defect_recall` (on the review probes) |

It then writes a report with recommendations. The five commands:

| Command | What it does |
|---------|--------------|
| `list-cases` | Lists the cases and whether their reference artifacts exist |
| `estimate` | Prints what a run would cost, per model and for the judge |
| `bootstrap-reference` | Produces the reference artifacts for stages 1 to 4 |
| `run` | Runs the matrix, grades, and writes `results.jsonl`, `run.json`, `summary.json`, and `report.md` |
| `report DIR` | Rebuilds `summary.json` and `report.md` from a run directory; `--publish` shares the run |

## Prerequisites

Export an API key for every provider you want to evaluate, and for the
**judge** (Anthropic's `claude-opus-5-5` unless you pass `--judge` or edit
`config/matrix.toml`):

| Provider | Variable |
|----------|----------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) |

A model whose provider has no key is skipped with a warning, and the report
lists it. If the judge has no key the run still goes on, but the judged grades
are missing, so no model gets a quality score for the select, tailor, and review
stages.
`run --strict` turns either problem into an error before any call is made.
Providers you define in `mkcv.toml` work in the matrix too.

## Step by step

1. **Check the cost.**

   ```bash
   uv run python -m evals estimate
   ```

   For the shipped matrix (ten models over the 26 cases) the estimate is
   about $138, of which about $39 is the judge. These are planning token counts,
   not measurements; `report.md` shows what the run really used. Narrow a run
   with `--models`, `--cases`, or `--stages`, or lower `repeats` in
   `config/matrix.toml`.

2. **Bootstrap the reference artifacts** (once, until the fixtures change):

   ```bash
   uv run python -m evals bootstrap-reference --yes
   ```

   The reference model (`[reference]` in the matrix) runs stages 1 to 4 for
   every case and writes the results to `evals/fixtures/reference/<case>/`. Each
   review probe copies its stage 1 to 3 files from the case that shares its
   persona and job description, and keeps its hand-written resume with seeded
   defects.

   **Review every file under `evals/fixtures/reference/` by hand** before
   committing them: the references are the input every evaluated model sees, so
   a fabricated fact there poisons the whole run. An existing reference is never
   overwritten; delete a case's directory to regenerate it.

3. **Run the matrix.**

   ```bash
   uv run python -m evals run --yes
   ```

   Without `--yes` it asks `Proceed? [y/N]`, and exits 2 when stdin is not a
   terminal. Results go to `evals/results/<UTC time>-<commit>/` (gitignored).
   Failed records do not stop the run or change the exit code. Add `--verbose`
   to log each stage run as it starts; warnings from mkcv (retries, repairs)
   always show on stderr.

4. **Read `report.md`.** See the next section.

5. **Publish the run** so the evidence is in the repository:

   ```bash
   uv run python -m evals report evals/results/<run> --publish
   ```

   This copies `results.jsonl`, `summary.json`, `report.md`, and `run.json` (not
   the `raw/` outputs) to `evals/results/published/<run id>/`. Commit that folder.

6. **Apply the results by hand.** Edit
   `src/mkcv/core/catalog/builtin_model_profiles.py` following "Suggested profile
   changes" and set `evidence="eval"` and `eval_run="<run id>"` on each profile
   you updated. Then update `docs/models.md`, citing
   `evals/results/published/<run id>/report.md`. Commit as
   `feat(catalog): adopt eval-backed model recommendations`. A profile that is
   updated this way shows `eval-backed: <run>` in `mkcv models`. Nothing applies
   results automatically.

## Reading the report

`report.md` has these sections, in order:

- **Run**: the run ID, time, versions, judge, cases, and models.
- **Caveats**: what weakens the numbers. Rows marked self-judged were scored by a
  judge from the same provider, so favour them less. A low sample row has fewer
  than six runs. Skipped models, a judge that did not run, and failed records are
  listed here too.
- **Cost**: what each model's completed runs cost at catalog prices. Judge calls
  are not included.
- **Stage: ...**: one table per stage. *Quality* is the stage's primary metric:
  `jd_keyword_recall` for analyze, `selection_judge` for select,
  `tailoring_judge` for tailor, `ats_rules` for structure, and
  `review_defect_recall` for review.
- **Recommendations**: for each stage and provider, the best eligible model, the
  **recommended** one (the cheapest within 0.05 of the best), and the **economy**
  one (the cheapest scoring at least 0.70).
- **Suggested profile changes**: where a built-in profile's model differs from
  the recommendation for its provider. Non-economy profiles follow *recommended*,
  economy profiles follow *economy*.
- **Token estimates**: measured median tokens per stage next to the planning
  estimates in `STAGE_REQUIREMENTS`.

A model is **Eligible** for a stage when at least 95% of its runs completed, its
`schema` mean is at least 0.95, and, where the stage has them, its
`faithfulness_extraction` mean is at least 0.95 and its `faithfulness_judge` mean
at least 0.90. A model that fails any of these is never recommended, however
well it writes. The Notes column says which one it missed.

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
- **Cover letters.** `fixtures/cover_letter_cases.md` lists the cases suited to
  cover letter evaluation and what each letter must and must not say.

`tests/test_evals/test_fixtures.py` checks these rules.

## Layout

```
evals/
  cli.py            commands
  config/matrix.toml  the default matrix: models, judge, reference model
  fixtures/         personas, job descriptions, cases.toml, reference artifacts
  graders/          rule-based and judge graders, with rubrics/
  harness/          stage runner, matrix runner, cost estimate, bootstrap
  models/           Pydantic models for cases, records, summaries
  report/           aggregation, recommendations, Markdown report
  results/          run output (gitignored); published/ holds shared runs
```

The tests under `tests/test_evals/` use stub providers and a stub judge and never
reach the network.
