# Spec: Eval Harness and Graders

Design references: §9.

All scenarios are offline. LLM calls use `StubLLMAdapter` (evaluated model) and a stub judge. Tests live under `tests/test_evals/` and import `evals` through the pytest `pythonpath = ["."]` setting.

## Packaging and tooling

### REQ-EV-1: Not shipped

- **When** the wheel is built (`uv build --wheel`), **then** no file under `evals/` is in it. (Checked once during T13; the existing `packages = ["src/mkcv"]` guarantees it.)
- `uv run python -m evals --help` exits 0 and lists `list-cases`, `estimate`, `run`, `report`, and `bootstrap-reference`.
- CI runs `ruff check` and `ruff format --check` on `src/ tests/ evals/` and `mypy` on `src/ evals/`.

## Fixtures

### REQ-EV-2: Cases load and validate

- **When** `load_cases(Path("evals/fixtures"))` runs, **then** it returns seven cases: the six of design §9.4 plus `review-probe`.
- Every case's persona and JD files exist and are non-empty; every `forbidden_claims` term appears in the case's JD and not in its persona KB (case-insensitive word match).
- Persona line counts fall within the ranges of design §9.4.
- No fixture contains an email address outside `example.com`, a phone number not matching `555-01\d\d`, or a URL other than `example.com`/`example.org` domains.

## Stage isolation

### REQ-EV-3: Runs exactly one stage

- **Given** recorded reference artifacts for stages 1–2 of a case and a stub adapter that returns a canned `TailoredContent`, **when** `StageRunner.run(case, StageKey.TAILOR, model, repeat=0, work_dir)` runs, **then** the stub received exactly one `complete_structured` call, with `response_model=TailoredContent`, and the run's status is `ok` with the canned payload.
- `StopAfterStage(3).on_stage_complete(3, ...)` returns `False` and stores the metadata.

### REQ-EV-4: Missing reference

- **Given** no reference artifacts for a case, **when** the runner is asked for stage `select`, **then** the record has `status == "skipped"` and `error` contains `bootstrap-reference`; no LLM call is made.

### REQ-EV-5: Errors are recorded, not raised

- **Given** a stub whose `complete_structured` raises `ProviderError("boom")`, **then** the record has `status == "error"`, `error == "boom"` (or contains it), and the runner continues with the next item.

### REQ-EV-6: Work directory naming

- **Given** provider `openrouter` and model `openai/gpt-4o`, **then** the work directory ends with `openrouter__openai_gpt-4o/r0`.

## Deterministic graders

### REQ-EV-7: Schema grader

- **Given** a valid `JDAnalysis` payload, **then** `schema` scores 1.0; **given** a payload missing a required field, **then** 0.0 and `passed is False`.
- **Given** stage-4 YAML without `cv.sections`, **then** 0.0.

### REQ-EV-8: JD keyword recall

- **Given** expected keywords `["Kubernetes", "Go", "Terraform"]` and an analysis mentioning `kubernetes` and `Go` only, **then** score ≈ 0.667 and `passed is False`.

### REQ-EV-9: ATS rules

- Each rule R1–R7 has one failing fixture and the clean recorded YAML passes all seven (score 1.0).
- **Given** a highlight `I led the migration`, **then** R3 fails and `details["failures"]` contains an item with rule `R3` and the offending text.

### REQ-EV-10: Faithfulness extraction

- **Given** a KB containing `reduced p99 latency by 40%` and a bullet `Cut p99 latency by 40 percent`, **then** no number violation.
- **Given** a bullet `Saved $2.4M annually` and a KB without `2.4`, **then** one `number` violation with text `$2.4M`.
- **Given** a role with `company = "Initech, Inc."` and a KB containing `Initech`, **then** no company violation.
- **Given** case `forbidden_claims = ["PyTorch"]` and a bullet `Trained models in PyTorch`, **then** one `forbidden_claim` violation.
- **Given** a date field `2019-03`, **then** `2019` is not checked as a number.

### REQ-EV-11: Structure grader

- **Given** reference stage-3 roles at `Initech` and `Globex` and YAML containing only `Initech`, **then** score 0.5.

## Judge graders

### REQ-EV-12: Faithfulness judge

- **Given** a stub judge returning verdicts `supported`, `partial`, `unsupported`, `supported`, **then** score = 0.625, `passed is False`, and `details["judge"] == "<provider>/<model>"`.
- The judge request's system message is the content of `rubrics/faithfulness.md`; the user message contains the KB text and numbered bullets.

### REQ-EV-13: Rubric judges

- **Given** a stub `RubricJudgement` with criterion scores 5, 4, 4, 3, 4, **then** `tailoring_judge` score = 0.8.
- **Given** a `CriterionScore` with `score=6`, **then** Pydantic validation fails (scores are 1–5).

### REQ-EV-14: Review defect recall

- **Given** three seeded defects and a stub `DefectJudgement` detecting two, **then** score ≈ 0.667.
- For a non-probe case, `review_defect_recall` is not computed (no grade with that name in the record).

### REQ-EV-15: Self-judged flag

- **Given** the judge provider equals the evaluated provider, **then** every judge grade has `details["self_judged"] is True`, and the stage summary has `self_judged is True`.

## Aggregation, recommendation, report

### REQ-EV-16: Aggregation

- **Given** six records for one `(stage, provider, model)` with latencies 1–6 s and one `error` record, **then** the summary has `n == 7`, `ok_rate == 6/7`, `latency_p50_s == 3.5` (median of ok records), and `low_sample is False`.
- Records with `status == "skipped"` are excluded from `n`.

### REQ-EV-17: Eligibility and recommendation

- **Given** summaries for tailor/openai: A (quality 0.90, cost $0.20, eligible), B (0.87, $0.05, eligible), C (0.95, $0.01, faithfulness_extraction 0.90 → ineligible), **then** `best == A`, `recommended == B`, `economy == B`.
- **Given** no eligible model, **then** all three are `None` and `reason == "no eligible model"`.
- Ties on quality resolve to the lower cost, then the lower p50 latency.

### REQ-EV-18: Report

- **Given** a synthetic run, **then** `render_markdown` output starts with `# mkcv eval report: <run_id>` and contains, in order, the headings `## Run`, `## Caveats`, `## Cost`, one `## Stage: <stage>` per stage present, `## Recommendations`, `## Suggested profile changes`, `## Token estimates`.
- **Given** a recommended model that differs from the current built-in profile model for that stage and provider, **then** `## Suggested profile changes` lists `<profile> / <stage>: <current> → <recommended>`.

### REQ-EV-19: Files

- **When** `EvalRunner` finishes, **then** the output directory contains `results.jsonl` (one valid `EvalRecord` per line), `run.json`, `summary.json`, and `report.md`.
- **When** `python -m evals report DIR --publish` runs, **then** `evals/results/published/<run_id>/` contains those four files and no `raw/` directory.

## CLI behaviour

### REQ-EV-20: Confirmation and credentials

- **When** `python -m evals run` runs with stdin not a TTY and without `--yes`, **then** it prints the estimate and exits 2 without calling any model.
- **Given** no `OPENAI_API_KEY`, **when** `run --yes` runs with a matrix that includes OpenAI models, **then** those models are skipped with a warning line naming the provider, and other providers run.
- **Given** the same and `--strict`, **then** it exits 2 before any call.
- `--judge openai:gpt-6.1-sol` overrides the matrix judge; a value without `:` exits 2 with a usage message.

### REQ-EV-21: Estimate

- **Given** a matrix with one model (`anthropic/claude-haiku-5-5`), one stage (`analyze`), two cases, one repeat, **then** `estimate` reports `2 × (4000 × 0.10 + 2000 × 0.50) / 1e6 = $0.0028` for the evaluated model, plus judge cost 0 (analyze has no judge grader).

## Documentation

### REQ-EV-22: Docs

- `evals/README.md` explains prerequisites (keys per provider), `bootstrap-reference` and human review of references, the one-command run `uv run python -m evals run --yes`, expected cost (from `estimate`), how to read `report.md`, how to publish, and how to apply results to `core/catalog/builtin_model_profiles.py` and `docs/models.md`.
- `docs/models.md` has a section "How recommendations are made" that links `evals/README.md` and states that all current profiles are provisional.
