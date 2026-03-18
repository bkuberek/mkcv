"""mkcv validate — check resume for ATS compliance."""

from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

console = Console()


def validate_command(
    file: Annotated[
        Path,
        cyclopts.Parameter(
            help="Resume file to validate (PDF or YAML).",
        ),
    ],
    *,
    jd: Annotated[
        Path | None,
        cyclopts.Parameter(
            help="Job description to check keyword coverage against.",
        ),
    ] = None,
) -> None:
    """Check a resume (PDF or YAML) for ATS compliance.

    Analyzes formatting, text extractability, section headings,
    and optionally keyword coverage against a job description.
    """
    console.print(
        f"\n  [yellow]Resume validation not yet implemented.[/yellow]\n  File: {file}\n"
    )
    if jd is not None:
        console.print(f"  JD:   {jd}\n")
