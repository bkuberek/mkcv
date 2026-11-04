"""Print the non-blocking model warnings that precede a run."""

from rich.console import Console
from rich.markup import escape

from mkcv.core.models.model_report import ModelReport

_MODELS_COMMAND_HINT = "Run 'mkcv models' for recommended models per stage."


def print_model_warnings(report: ModelReport, console: Console) -> None:
    """Print each warning in ``report``, then a pointer to ``mkcv models``.

    Prints nothing when the report has no warnings. Messages hold bracketed
    config paths such as ``[[default.model_catalog]]``, so they are escaped.
    """
    if not report.warnings:
        return
    for warning in report.warnings:
        console.print(f"[yellow]Warning:[/yellow] {escape(warning.message)}")
    console.print(f"[dim]{_MODELS_COMMAND_HINT}[/dim]")
