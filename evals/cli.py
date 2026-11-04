"""Command line for the offline eval harness: ``uv run python -m evals``.

Exit codes: 0 on success (even when individual records failed), 1 when
``bootstrap-reference`` could not produce a case, and 2 when the command did
not start because of bad input, bad configuration, a missing confirmation, or
an unfinished command.
"""

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from evals.harness.case_loader import load_cases, load_matrix, select_cases
from evals.harness.cost_estimator import estimate_matrix_cost
from evals.harness.credentials import split_by_credentials
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import DEFAULT_FIXTURES_DIR, REFERENCE_FILES, EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.matrix_overrides import MatrixOverrides
from evals.models.reference_outcome import ReferenceOutcome
from evals.models.run_settings import RunSettings
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

if TYPE_CHECKING:
    from mkcv.adapters.llm.provider_registry import ProviderRegistry
    from mkcv.config.configuration import Configuration

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_MATRIX = EVALS_DIR / "config" / "matrix.toml"
DEFAULT_RESULTS_DIR = EVALS_DIR / "results"
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
    report.set_defaults(handler=_not_implemented("report"))

    bootstrap = commands.add_parser(
        "bootstrap-reference",
        help="produce reference artifacts for stages 1-4 with the reference model",
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


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    _add_fixtures_argument(parser)
    parser.add_argument(
        "--matrix", type=Path, default=DEFAULT_MATRIX, help="matrix TOML file"
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=[stage.value for stage in PIPELINE_STAGES],
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
        "--judge", metavar="PROVIDER:MODEL", help="judge model (default: the matrix's)"
    )


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--out", type=Path, help="output directory (default: evals/results/<run id>)"
    )
    parser.add_argument("--concurrency", type=int, help="stage runs in flight at once")
    parser.add_argument(
        "--yes", action="store_true", help="run without asking for confirmation"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit instead of skipping models whose provider has no credentials",
    )


def _add_bootstrap_arguments(parser: argparse.ArgumentParser) -> None:
    _add_fixtures_argument(parser)
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
    estimate = estimate_matrix_cost(matrix, cases, registry.catalog)
    for line in _estimate_lines(estimate, case_count=len(cases)):
        _out(line)
    return 0


def _run(args: argparse.Namespace, config: "Configuration") -> int:
    from evals.harness.eval_runner import (
        REPO_ROOT,
        EvalRunner,
        current_git_sha,
        new_run_id,
    )

    matrix, cases, registry = _load_plan(args, config)
    runnable, skipped = split_by_credentials(registry, matrix.models)
    for reason in skipped:
        _err(f"warning: skipping {reason}")
    if skipped and args.strict:
        return _fail("--strict: some models have no credentials (see warnings above)")

    effective = matrix.model_copy(update={"models": runnable})
    estimate = estimate_matrix_cost(effective, cases, registry.catalog)
    for line in _estimate_lines(estimate, case_count=len(cases)):
        _out(line)
    if not args.yes and not _confirmed():
        return EXIT_USAGE

    run_id = new_run_id(datetime.now(UTC), current_git_sha(REPO_ROOT))
    out_dir = args.out or default_out_dir(run_id)
    runner = EvalRunner(config, out_dir=out_dir, run_id=run_id, on_record=_progress)
    records = asyncio.run(runner.run(effective, cases, skipped_models=skipped))
    _out(_run_summary(records, out_dir))
    return 0


def _bootstrap_reference(args: argparse.Namespace, config: "Configuration") -> int:
    from evals.harness.reference_bootstrapper import ReferenceBootstrapper
    from mkcv.adapters.factory import create_provider_registry

    matrix = load_matrix(args.matrix)
    reference = _reference_model(args, matrix)
    known = load_cases(args.fixtures)
    cases = select_cases(known, args.cases or matrix.run.cases)
    registry = create_provider_registry(config)
    if not registry.has_credentials(reference.provider):
        return _fail(f"no API key for the reference provider '{reference.provider}'")

    _out(_bootstrap_estimate_line(reference, cases, registry))
    if not args.yes and not _confirmed():
        return EXIT_USAGE

    bootstrapper = ReferenceBootstrapper(
        config, reference=reference, preset=matrix.run.preset
    )
    outcomes = asyncio.run(bootstrapper.bootstrap(cases, known))
    for outcome in outcomes:
        _out(_outcome_line(outcome))
    _out(
        f"Review every file under {args.fixtures / 'reference'} for fabricated "
        "facts before committing."
    )
    return EXIT_FAILED if any(o.status == "error" for o in outcomes) else 0


def _not_implemented(name: str) -> _Handler:
    def handler(args: argparse.Namespace, config: "Configuration") -> int:
        return _fail(f"{name} is not implemented yet")

    return handler


def _load_plan(
    args: argparse.Namespace, config: "Configuration"
) -> tuple[MatrixConfig, list[EvalCase], "ProviderRegistry"]:
    from mkcv.adapters.factory import create_provider_registry

    overrides = MatrixOverrides(
        stages=args.stages,
        cases=args.cases,
        models=args.models,
        judge=args.judge,
        concurrency=getattr(args, "concurrency", None),
    )
    matrix = overrides.apply(load_matrix(args.matrix))
    cases = select_cases(load_cases(args.fixtures), matrix.run.cases)
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
    available = case.reference_stages()
    if len(available) == len(REFERENCE_FILES):
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
    rows.append(
        (
            f"Judge {estimate.judge}",
            f"{estimate.judge_calls} calls",
            _usd(estimate.judge_cost_usd),
        )
    )
    lines = _aligned(rows)
    note = " (some prices unknown)" if estimate.is_partial else ""
    lines.append(f"Total{note}: {_usd(estimate.total_usd)}")
    return lines


def _bootstrap_estimate_line(
    reference: JudgeConfig, cases: Sequence[EvalCase], registry: "ProviderRegistry"
) -> str:
    pending = [
        c
        for c in cases
        if not c.review_probe_defects and not c.existing_reference_files()
    ]
    model = MatrixModel(provider=reference.provider, model=reference.model)
    matrix = MatrixConfig(
        run=RunSettings(stages=list(REFERENCE_STAGES)),
        judge=reference,
        reference=reference,
        models=[model],
    )
    cost = estimate_matrix_cost(matrix, pending, registry.catalog).model_costs[
        model.label
    ]
    return (
        f"Reference model {model.label}: {_usd(cost)} for {len(pending)} case(s), "
        "stages 1-4 each"
    )


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
