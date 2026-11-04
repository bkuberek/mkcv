"""Command line for the offline eval harness: ``uv run python -m evals``.

Exit codes: 0 on success (even when individual records failed), 1 when
``bootstrap-reference`` could not produce a case, and 2 when the command did
not start because of bad input, bad configuration, or a missing confirmation.
"""

import argparse
import asyncio
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from evals.harness.case_loader import load_cases, load_matrix, select_cases
from evals.harness.cost_estimator import (
    estimate_matrix_cost,
    estimate_tournament_cost,
)
from evals.harness.credentials import split_by_credentials
from evals.harness.judge_factory import split_judges
from evals.harness.logging_setup import configure_logging
from evals.harness.run_files import REPORT_FILE
from evals.harness.tournament import unknown_screening_cases
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import DEFAULT_FIXTURES_DIR, EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.matrix_overrides import MatrixOverrides
from evals.models.reference_outcome import ReferenceOutcome
from evals.models.round import ROUNDS, Round
from evals.models.run_settings import RunSettings
from evals.models.tournament_estimate import TournamentEstimate
from evals.report.report_writer import (
    publish_run,
    read_manifest,
    write_report_files,
)
from evals.stages import EVALUATED_STAGES
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.stage_key import StageKey

if TYPE_CHECKING:
    from mkcv.adapters.llm.provider_registry import ProviderRegistry
    from mkcv.config.configuration import Configuration

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_MATRIX = EVALS_DIR / "config" / "matrix.toml"
DEFAULT_RESULTS_DIR = EVALS_DIR / "results"
PUBLISHED_DIR = DEFAULT_RESULTS_DIR / "published"
EXIT_FAILED = 1
EXIT_USAGE = 2
MAX_ERROR_CHARS = 160
REFERENCE_STAGES = (
    StageKey.ANALYZE,
    StageKey.SELECT,
    StageKey.TAILOR,
    StageKey.STRUCTURE,
)

_Handler = Callable[[argparse.Namespace, "Configuration"], int]


def default_out_dir(run_id: str) -> Path:
    """Return where a run's files go when ``--out`` is not given."""
    return DEFAULT_RESULTS_DIR / run_id


def main(
    argv: Sequence[str] | None = None, *, config: "Configuration | None" = None
) -> int:
    """Run the eval command line and return the process exit code.

    Args:
        argv: Arguments after the program name; defaults to ``sys.argv[1:]``.
        config: Mkcv configuration (providers, keys, catalog overrides);
            defaults to the real mkcv settings.
    """
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as request:
        return _exit_code(request)

    if config is None:
        from mkcv.config import settings

        config = settings

    handler: _Handler = args.handler
    try:
        return handler(args, config)
    except (OSError, ValueError, MkcvError) as error:
        return _fail(str(error))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals",
        description="Offline harness that evaluates models on mkcv's pipeline stages.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    list_cases = commands.add_parser(
        "list-cases", help="list eval cases and whether reference artifacts exist"
    )
    _add_fixtures_argument(list_cases)
    list_cases.set_defaults(handler=_list_cases)

    check = commands.add_parser(
        "check-reference",
        help="list reference claims the knowledge base does not support",
    )
    _add_fixtures_argument(check)
    check.add_argument("--cases", nargs="+", metavar="CASE", help="check only these")
    check.set_defaults(handler=_check_reference)

    estimate = commands.add_parser(
        "estimate", help="estimate what a matrix run would cost"
    )
    _add_selection_arguments(estimate)
    estimate.set_defaults(handler=_estimate)

    run = commands.add_parser(
        "run", help="run the matrix, grade the outputs, and write the results"
    )
    _add_selection_arguments(run)
    _add_run_arguments(run)
    run.set_defaults(handler=_run)

    report = commands.add_parser(
        "report", help="rebuild summary.json and report.md from a results directory"
    )
    report.add_argument("dir", type=Path, help="a run's output directory")
    report.add_argument(
        "--publish",
        action="store_true",
        help="copy the run's result files to evals/results/published/<run id>",
    )
    report.set_defaults(handler=_report)

    bootstrap = commands.add_parser(
        "bootstrap-reference",
        help=(
            "produce reference artifacts (stages 1-4 and the cover letter) "
            "with the reference model"
        ),
    )
    _add_bootstrap_arguments(bootstrap)
    bootstrap.set_defaults(handler=_bootstrap_reference)

    return parser


def _add_fixtures_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="fixtures directory holding cases.toml (default: evals/fixtures)",
    )


def _add_batch_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-batch",
        action="store_true",
        help="call every model online instead of in provider batches",
    )


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    _add_fixtures_argument(parser)
    _add_batch_argument(parser)
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="(estimate) price bootstrap-reference instead of a run",
    )
    parser.add_argument(
        "--matrix", type=Path, default=DEFAULT_MATRIX, help="matrix TOML file"
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=[stage.value for stage in EVALUATED_STAGES],
        metavar="STAGE",
        help="run only these stages (default: the matrix's stages)",
    )
    parser.add_argument(
        "--cases", nargs="+", metavar="CASE", help="run only these case IDs"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        metavar="PROVIDER:MODEL",
        help="evaluate these models instead of the matrix's",
    )
    parser.add_argument(
        "--single-round",
        action="store_true",
        help="run (or price) one round of every model on every case, no screening",
    )
    parser.add_argument(
        "--judge",
        nargs="+",
        metavar="PROVIDER:MODEL",
        help="judge panel: one or more judge models (default: the matrix's judges)",
    )


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--out", type=Path, help="output directory (default: evals/results/<run id>)"
    )
    parser.add_argument("--concurrency", type=int, help="stage runs in flight at once")
    parser.add_argument(
        "--round",
        choices=("all", "screening", "finals"),
        default="all",
        help="run one tournament round (the finals read the screening of --resume)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        metavar="DIR",
        help="continue the run in DIR: keep its records and make only the rest",
    )
    parser.add_argument(
        "--yes", action="store_true", help="run without asking for confirmation"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit instead of skipping models (or judges) with no credentials",
    )
    _add_verbose_argument(parser)


def _add_verbose_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="also log each stage run as it starts (warnings always show)",
    )


def _add_bootstrap_arguments(parser: argparse.ArgumentParser) -> None:
    _add_fixtures_argument(parser)
    _add_batch_argument(parser)
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_RESULTS_DIR / "bootstrap",
        metavar="DIR",
        help="where batches and usage persist, so a rerun resumes "
        "(default: evals/results/bootstrap)",
    )
    _add_verbose_argument(parser)
    parser.add_argument(
        "--matrix", type=Path, default=DEFAULT_MATRIX, help="matrix TOML file"
    )
    parser.add_argument(
        "--cases", nargs="+", metavar="CASE", help="bootstrap only these case IDs"
    )
    parser.add_argument("--provider", help="reference provider (with --model)")
    parser.add_argument("--model", help="reference model (with --provider)")
    parser.add_argument(
        "--yes", action="store_true", help="run without asking for confirmation"
    )


def _list_cases(args: argparse.Namespace, config: "Configuration") -> int:
    cases = load_cases(args.fixtures)
    rows = [("ID", "PERSONA", "JD", "REFERENCE")]
    rows.extend((c.id, c.persona, c.jd, _reference_status(c)) for c in cases)
    for line in _aligned(rows):
        _out(line)
    return 0


def _estimate(args: argparse.Namespace, config: "Configuration") -> int:
    matrix, cases, registry = _load_plan(args, config)
    discounts = _batch_discounts(matrix, registry)
    if args.bootstrap:
        lines = [_bootstrap_estimate_line(matrix.reference, cases, registry, discounts)]
    elif matrix.tournament.enabled:
        lines = _tournament_lines(
            estimate_tournament_cost(
                matrix, cases, registry.catalog, discounts=discounts
            ),
            matrix,
        )
    else:
        lines = _estimate_lines(
            estimate_matrix_cost(matrix, cases, registry.catalog, discounts=discounts),
            case_count=len(cases),
        )
    for line in lines:
        _out(line)
    return 0


def _run(args: argparse.Namespace, config: "Configuration") -> int:
    from evals.harness.eval_runner import (
        REPO_ROOT,
        EvalRunner,
        current_git_sha,
        new_run_id,
    )

    configure_logging(verbose=args.verbose)
    matrix, cases, registry = _load_plan(args, config)
    runnable, skipped = split_by_credentials(registry, matrix.models)
    for reason in skipped:
        _err(f"warning: skipping {reason}")
    if skipped and args.strict:
        return _fail("--strict: some models have no credentials (see warnings above)")

    effective = matrix.model_copy(update={"models": runnable})
    _, skipped_judges = split_judges(registry, effective.panel)
    discounts = _batch_discounts(effective, registry)
    estimate = estimate_matrix_cost(
        effective,
        cases,
        registry.catalog,
        skipped_judges=skipped_judges,
        discounts=discounts,
    )
    for label, reason in estimate.skipped_judges.items():
        _err(f"warning: judge {label} skipped ({reason})")
    if estimate.skipped_judges and not estimate.judges:
        _err("warning: no judge can run; scores that need a judge will be missing")
    if estimate.skipped_judges and args.strict:
        return _fail("--strict: some judges have no credentials (see warnings above)")
    if effective.tournament.enabled:
        lines = _tournament_lines(
            estimate_tournament_cost(
                effective,
                cases,
                registry.catalog,
                skipped_judges=skipped_judges,
                discounts=discounts,
            ),
            effective,
        )
    else:
        lines = _estimate_lines(estimate, case_count=len(cases))
    for line in lines:
        _out(line)
    if not args.yes and not _confirmed():
        return EXIT_USAGE

    if args.resume is not None:
        out_dir = args.resume
        run_id = read_manifest(out_dir).run_id
    else:
        run_id = new_run_id(datetime.now(UTC), current_git_sha(REPO_ROOT))
        out_dir = args.out or default_out_dir(run_id)
    runner = EvalRunner(
        config,
        out_dir=out_dir,
        run_id=run_id,
        on_record=_progress,
        resume=args.resume is not None,
    )
    rounds: tuple[Round, ...] = ROUNDS if args.round == "all" else (args.round,)
    records = asyncio.run(
        runner.run(effective, cases, skipped_models=skipped, rounds=rounds)
    )
    _out(_run_summary(records, out_dir))
    _out(_report_line(out_dir))
    return 0


def _report(args: argparse.Namespace, config: "Configuration") -> int:
    write_report_files(args.dir)
    _out(_report_line(args.dir))
    if args.publish:
        _out(f"Published to {publish_run(args.dir, PUBLISHED_DIR)}")
    return 0


def _bootstrap_reference(args: argparse.Namespace, config: "Configuration") -> int:
    from evals.batch.batch_store import BatchStore
    from evals.batch.eval_adapters import EvalAdapters
    from evals.batch.usage_ledger import UsageLedger
    from evals.harness.reference_bootstrapper import ReferenceBootstrapper
    from mkcv.adapters.factory import create_provider_registry

    configure_logging(verbose=args.verbose)
    matrix = MatrixOverrides(no_batch=args.no_batch).apply(load_matrix(args.matrix))
    reference = _reference_model(args, matrix)
    known = load_cases(args.fixtures)
    cases = select_cases(known, args.cases or matrix.run.cases)
    registry = create_provider_registry(config)
    if not registry.has_credentials(reference.provider):
        return _fail(f"no API key for the reference provider '{reference.provider}'")

    discounts = _batch_discounts(
        matrix.model_copy(update={"models": [], "judges": [reference], "judge": None}),
        registry,
    )
    _out(_bootstrap_estimate_line(reference, cases, registry, discounts))
    if not args.yes and not _confirmed():
        return EXIT_USAGE

    args.state.mkdir(parents=True, exist_ok=True)
    adapters = EvalAdapters(
        registry,
        settings=matrix.batch,
        store=BatchStore(args.state / "batches") if matrix.batch.enabled else None,
        ledger=UsageLedger(args.state / "usage.jsonl"),
        run_id="bootstrap",
    )
    bootstrapper = ReferenceBootstrapper(
        config,
        reference=reference,
        preset=matrix.run.preset,
        adapters=adapters,
        concurrency=matrix.batch.concurrency if matrix.batch.enabled else 4,
    )
    outcomes = asyncio.run(bootstrapper.bootstrap(cases, known))
    for outcome in outcomes:
        _out(_outcome_line(outcome))
    _out(
        f"Review every file under {args.fixtures / 'reference'} for fabricated "
        "facts before committing; `python -m evals check-reference` lists the "
        "claims the knowledge base does not support."
    )
    return EXIT_FAILED if any(o.status == "error" for o in outcomes) else 0


def _check_reference(args: argparse.Namespace, config: "Configuration") -> int:
    from evals.harness.reference_checker import check_references

    known = load_cases(args.fixtures)
    cases = select_cases(known, args.cases or ["*"])
    findings = asyncio.run(check_references(cases))
    for finding in findings:
        status = "ok"
        if finding.error:
            status = f"error: {finding.error}"
        elif finding.violations:
            listed = ", ".join(f"{v['type']} {v['text']!r}" for v in finding.violations)
            status = f"{len(finding.violations)} flagged: {listed}"
        note = (
            " (probe: planted on purpose)" if finding.probe and status != "ok" else ""
        )
        _out(f"{finding.case_id} / {finding.artifact}: {status}{note}")
    flagged = [f for f in findings if f.flagged]
    _out(
        f"{len(findings)} reference file(s) checked, {len(flagged)} to review"
        if findings
        else "No reference files found; run bootstrap-reference first."
    )
    return EXIT_FAILED if flagged else 0


def _load_plan(
    args: argparse.Namespace, config: "Configuration"
) -> tuple[MatrixConfig, list[EvalCase], "ProviderRegistry"]:
    from mkcv.adapters.factory import create_provider_registry

    overrides = MatrixOverrides(
        stages=args.stages,
        cases=args.cases,
        models=args.models,
        judges=args.judge,
        concurrency=getattr(args, "concurrency", None),
        single_round=args.single_round,
        no_batch=args.no_batch,
    )
    matrix = overrides.apply(load_matrix(args.matrix))
    known = load_cases(args.fixtures)
    if matrix.tournament.enabled and not args.cases:
        for name in unknown_screening_cases(known, matrix.tournament):
            _err(f"warning: screening case '{name}' is not in {args.fixtures}")
    cases = select_cases(known, matrix.run.cases)
    return matrix, cases, create_provider_registry(config)


def _reference_model(args: argparse.Namespace, matrix: MatrixConfig) -> JudgeConfig:
    if args.provider is None and args.model is None:
        return matrix.reference
    if args.provider is None or args.model is None:
        raise ValueError("--provider and --model must be given together")
    return JudgeConfig(provider=args.provider, model=args.model)


def _confirmed() -> bool:
    if not sys.stdin.isatty():
        _err("error: not a terminal; pass --yes to confirm the run")
        return False
    try:
        answer = input("Proceed? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() in ("y", "yes"):
        return True
    _err("aborted")
    return False


def _reference_status(case: EvalCase) -> str:
    """Whether the case has every reference its stages read from."""
    needed = case.needed_reference_stages()
    available = [stage for stage in needed if stage in case.reference_stages()]
    if len(available) == len(needed):
        return "yes"
    if available:
        return "partial: " + ",".join(stage.value for stage in available)
    return "no"


def _estimate_lines(estimate: CostEstimate, *, case_count: int) -> list[str]:
    rows = [(f"Estimated cost, {case_count} case(s)", "RUNS", "COST")]
    rows.extend(
        (label, str(estimate.runs_per_model), _usd(cost))
        for label, cost in estimate.model_costs.items()
    )
    rows.extend(
        (
            f"Judge {label}",
            f"{estimate.judge_call_counts.get(label, estimate.judge_calls)} calls",
            _usd(cost),
        )
        for label, cost in estimate.judge_costs.items()
    )
    rows.extend(
        (f"Judge {label} (skipped)", "0 calls", _usd(0.0))
        for label in estimate.skipped_judges
    )
    if not estimate.judge_costs and not estimate.skipped_judges:
        rows.append(("Judges (no judged stage)", "0 calls", _usd(0.0)))
    lines = _aligned(rows)
    if estimate.provider_costs:
        lines.append("By provider (models and judges):")
        lines.extend(
            "  " + line
            for line in _aligned(
                [
                    (provider, _usd(cost))
                    for provider, cost in estimate.provider_costs.items()
                ]
            )
        )
    note = " (some prices unknown)" if estimate.is_partial else ""
    lines.append(f"Total{note}: {_usd(estimate.total_usd)}")
    if estimate.online_total_usd != estimate.total_usd:
        lines.append(f"Online, without batching: {_usd(estimate.online_total_usd)}")
    return lines


def _tournament_lines(estimate: TournamentEstimate, matrix: MatrixConfig) -> list[str]:
    settings = matrix.tournament
    screening = estimate.screening
    lines = [
        f"Screening: every model, {screening.runs_per_model} run(s) each "
        f"({settings.screening_repeats} repeat), one judge per model",
        *("  " + line for line in _estimate_lines(screening, case_count=0)[1:]),
        f"Finals: assumed survivors {', '.join(estimate.assumed_survivors)}; "
        f"{estimate.finals.runs_per_model} run(s) each ({matrix.run.repeats} "
        "repeats), the whole panel",
        *("  " + line for line in _estimate_lines(estimate.finals, case_count=0)[1:]),
        f"Total (screening + finals): {_usd(estimate.total_usd)}",
        f"Online, without batching: {_usd(estimate.online_total_usd)}",
        "Worst case (no model eliminated): "
        f"{_usd(_sum(screening.total_usd, estimate.finals_worst_case.total_usd))}",
    ]
    return lines


def _sum(*amounts: float | None) -> float | None:
    if any(amount is None for amount in amounts):
        return None
    return sum(amount for amount in amounts if amount is not None)


def _batch_discounts(
    matrix: MatrixConfig, registry: "ProviderRegistry"
) -> dict[str, float]:
    """The batch discount of every provider whose calls the run would batch.

    Anthropic and OpenAI batch whenever ``[batch]`` is on; Google only with a
    Vertex AI bucket. Other providers always go online.
    """
    from mkcv.core.models.provider_kind import ProviderKind

    if not matrix.batch.enabled:
        return {}
    names = {model.provider for model in matrix.models} | {
        judge.provider for judge in matrix.panel
    }
    batching: list[str] = []
    for name in sorted(names):
        kind = registry.get(name).kind
        if kind in (ProviderKind.ANTHROPIC, ProviderKind.OPENAI) or (
            kind is ProviderKind.GOOGLE and matrix.batch.google_gcs_bucket
        ):
            batching.append(name)
    return {name: matrix.pricing.batch_discount.get(name, 0.0) for name in batching}


def _bootstrap_estimate_line(
    reference: JudgeConfig,
    cases: Sequence[EvalCase],
    registry: "ProviderRegistry",
    discounts: Mapping[str, float] | None = None,
) -> str:
    from evals.harness.reference_bootstrapper import (
        needs_cover_letter,
        needs_pipeline,
    )

    pipeline = [c for c in cases if needs_pipeline(c)]
    letters = [c for c in cases if needs_cover_letter(c)]
    model = MatrixModel(provider=reference.provider, model=reference.model)
    costs = [
        _reference_cost(model, stages, chosen, registry)
        for stages, chosen in (
            (list(REFERENCE_STAGES), pipeline),
            ([StageKey.COVER_LETTER_GENERATE], letters),
        )
    ]
    known = [cost for cost in costs if cost is not None]
    total = sum(known) if len(known) == len(costs) else None
    off = (discounts or {}).get(reference.provider, 0.0)
    batched = total * (1.0 - off) if total is not None and off else None
    priced = f"{_usd(total)} online" + (
        f", {_usd(batched)} batched" if batched is not None else ""
    )
    return (
        f"Reference model {model.label}: {priced} for {len(pipeline)} "
        f"case(s) of stages 1-4 and {len(letters)} cover letter(s)"
    )


def _reference_cost(
    model: MatrixModel,
    stages: list[StageKey],
    cases: Sequence[EvalCase],
    registry: "ProviderRegistry",
) -> float | None:
    matrix = MatrixConfig(
        run=RunSettings(stages=stages),
        judge=JudgeConfig(provider=model.provider, model=model.model),
        reference=JudgeConfig(provider=model.provider, model=model.model),
        models=[model],
    )
    return estimate_matrix_cost(matrix, cases, registry.catalog).model_costs[
        model.label
    ]


def _outcome_line(outcome: ReferenceOutcome) -> str:
    detail = f" ({outcome.detail})" if outcome.detail else ""
    return f"{outcome.case_id}: {outcome.status}{detail}"


def _progress(record: EvalRecord) -> None:
    line = (
        f"{record.provider}/{record.model} {record.stage.value} "
        f"{record.case_id} r{record.repeat}: {record.status}"
    )
    if record.error:
        line += f" ({' '.join(record.error.split())[:MAX_ERROR_CHARS]})"
    _out(line)


def _report_line(out_dir: Path) -> str:
    return f"Report: {out_dir / REPORT_FILE}"


def _run_summary(records: Sequence[EvalRecord], out_dir: Path) -> str:
    counts = {
        status: sum(1 for record in records if record.status == status)
        for status in ("ok", "error", "skipped")
    }
    return (
        f"Wrote {len(records)} records ({counts['ok']} ok, {counts['error']} error, "
        f"{counts['skipped']} skipped) to {out_dir}"
    )


def _usd(amount: float | None) -> str:
    return "n/a" if amount is None else f"${amount:.4f}"


def _aligned(rows: Sequence[Sequence[str]]) -> list[str]:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        ).rstrip()
        for row in rows
    ]


def _exit_code(request: SystemExit) -> int:
    code = request.code
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def _fail(message: str) -> int:
    _err(f"error: {message}")
    return EXIT_USAGE


def _out(text: str) -> None:
    _console(stderr=False).print(text)


def _err(text: str) -> None:
    _console(stderr=True).print(text)


def _console(*, stderr: bool) -> Console:
    return Console(stderr=stderr, highlight=False, markup=False, soft_wrap=True)
