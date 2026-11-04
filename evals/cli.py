"""Command line for the offline eval harness: ``uv run python -m evals``.

Exit codes: 0 on success (even when individual records failed), 2 when the
run could not start because of bad input, bad configuration, or an
unfinished command.
"""

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from evals.harness.case_loader import load_cases, load_matrix, select_cases
from evals.harness.cost_estimator import estimate_matrix_cost
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import DEFAULT_FIXTURES_DIR, REFERENCE_FILES, EvalCase
from mkcv.core.exceptions.base import MkcvError

if TYPE_CHECKING:
    from mkcv.config.configuration import Configuration

DEFAULT_MATRIX = Path(__file__).resolve().parent / "config" / "matrix.toml"
EXIT_USAGE = 2

_Handler = Callable[[argparse.Namespace, "Configuration"], int]


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
    _add_fixtures_argument(estimate)
    estimate.add_argument(
        "--matrix", type=Path, default=DEFAULT_MATRIX, help="matrix TOML file"
    )
    estimate.set_defaults(handler=_estimate)

    for name, summary in (
        ("run", "run the matrix, grade the outputs, and write the report"),
        ("report", "rebuild summary.json and report.md from a results directory"),
        ("bootstrap-reference", "produce reference artifacts with the reference model"),
    ):
        unfinished = commands.add_parser(name, help=summary)
        unfinished.set_defaults(handler=_not_implemented(name))

    return parser


def _add_fixtures_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="fixtures directory holding cases.toml (default: evals/fixtures)",
    )


def _list_cases(args: argparse.Namespace, config: "Configuration") -> int:
    cases = load_cases(args.fixtures)
    rows = [("ID", "PERSONA", "JD", "REFERENCE")]
    rows.extend((c.id, c.persona, c.jd, _reference_status(c)) for c in cases)
    for line in _aligned(rows):
        _out(line)
    return 0


def _estimate(args: argparse.Namespace, config: "Configuration") -> int:
    from mkcv.adapters.factory import create_provider_registry

    matrix = load_matrix(args.matrix)
    cases = select_cases(load_cases(args.fixtures), matrix.run.cases)
    catalog = create_provider_registry(config).catalog
    estimate = estimate_matrix_cost(matrix, cases, catalog)
    for line in _estimate_lines(estimate, case_count=len(cases)):
        _out(line)
    return 0


def _not_implemented(name: str) -> _Handler:
    def handler(args: argparse.Namespace, config: "Configuration") -> int:
        return _fail(f"{name} is not implemented yet")

    return handler


def _reference_status(case: EvalCase) -> str:
    available = case.reference_stages()
    if len(available) == len(REFERENCE_FILES):
        return "yes"
    if available:
        return "partial: " + ",".join(stage.value for stage in available)
    return "no"


def _estimate_lines(estimate: CostEstimate, *, case_count: int) -> list[str]:
    rows = [
        (
            f"Estimated cost ({case_count} case(s); no model is called)",
            "RUNS",
            "COST",
        )
    ]
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
    _console(stderr=True).print(f"error: {message}")
    return EXIT_USAGE


def _out(text: str) -> None:
    _console(stderr=False).print(text)


def _console(*, stderr: bool) -> Console:
    return Console(stderr=stderr, highlight=False, markup=False, soft_wrap=True)
