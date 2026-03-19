"""mkcv validate — check resume for ATS compliance."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mkcv.adapters.factory import create_validation_service
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError
from mkcv.core.models.review_report import ReviewReport

logger = logging.getLogger(__name__)

console = Console()


def validate_command(
    file: Annotated[
        Path,
        cyclopts.Parameter(
            help="Resume file to validate (YAML).",
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
    """Check a resume for ATS compliance, quality, and keyword coverage.

    Validates resume content for ATS readiness, bullet quality, and
    overall presentation. Optionally checks keyword coverage against
    a specific job description.
    """
    if not file.is_file():
        console.print(f"[red]Error:[/red] Resume file not found: {file}")
        sys.exit(2)

    if jd is not None and not jd.is_file():
        console.print(f"[red]Error:[/red] Job description file not found: {jd}")
        sys.exit(2)

    console.print("\n  [bold]mkcv validate[/bold]")
    console.print(f"  Resume: {file}")
    if jd is not None:
        console.print(f"  JD:     {jd}")
    console.print()

    service = create_validation_service(settings)

    try:
        report = asyncio.run(service.validate(file, jd_path=jd))
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    _display_report(report)


def _display_report(report: ReviewReport) -> None:
    """Display the validation report using Rich formatting."""
    # Overall score
    score = report.overall_score
    score_color = _score_color(score)
    console.print(
        Panel(
            f"[bold {score_color}]{score}[/bold {score_color}] / 100",
            title="Overall Score",
            expand=False,
        )
    )

    # ATS check summary
    _display_ats_check(report)

    # Keyword coverage
    _display_keyword_coverage(report)

    # Bullet reviews summary
    _display_bullet_summary(report)

    # Top suggestions
    if report.top_suggestions:
        console.print("\n[bold]Top Suggestions[/bold]")
        for i, suggestion in enumerate(report.top_suggestions, 1):
            console.print(f"  {i}. {suggestion}")

    # Low confidence items
    if report.low_confidence_items:
        console.print("\n[bold yellow]Items Needing Review[/bold yellow]")
        for item in report.low_confidence_items:
            console.print(f"  [yellow]![/yellow] {item}")

    # Assessments
    console.print(f"\n  [dim]Tone:[/dim]    {report.tone_consistency}")
    console.print(f"  [dim]Balance:[/dim] {report.section_balance}")
    console.print(f"  [dim]Length:[/dim]  {report.length_assessment}")
    console.print()


def _display_ats_check(report: ReviewReport) -> None:
    """Display ATS compliance check results."""
    ats = report.ats_check
    status = "[green]PASS[/green]" if ats.overall_pass else "[red]FAIL[/red]"
    console.print(f"\n[bold]ATS Compliance:[/bold] {status}")

    if ats.issues:
        for issue in ats.issues:
            console.print(f"  [red]✗[/red] {issue}")


def _display_keyword_coverage(report: ReviewReport) -> None:
    """Display keyword coverage analysis."""
    kw = report.keyword_coverage
    pct = kw.coverage_percent
    pct_color = _score_color(int(pct))
    console.print(
        f"\n[bold]Keyword Coverage:[/bold] "
        f"[{pct_color}]{kw.matched_keywords}/{kw.total_keywords}[/{pct_color}] "
        f"([{pct_color}]{pct:.0f}%[/{pct_color}])"
    )

    if kw.missing_keywords:
        missing = ", ".join(kw.missing_keywords[:10])
        console.print(f"  [dim]Missing:[/dim] {missing}")


def _display_bullet_summary(report: ReviewReport) -> None:
    """Display a summary table of bullet review classifications."""
    if not report.bullet_reviews:
        return

    counts: dict[str, int] = {}
    for review in report.bullet_reviews:
        counts[review.classification] = counts.get(review.classification, 0) + 1

    table = Table(title="Bullet Reviews", show_header=True, expand=False)
    table.add_column("Classification", style="bold")
    table.add_column("Count", justify="right")

    classification_styles = {
        "faithful": "green",
        "enhanced": "cyan",
        "stretched": "yellow",
        "fabricated": "red",
    }

    for classification in ["faithful", "enhanced", "stretched", "fabricated"]:
        count = counts.get(classification, 0)
        if count > 0:
            style = classification_styles.get(classification, "white")
            table.add_row(f"[{style}]{classification}[/{style}]", str(count))

    console.print()
    console.print(table)

    # Show details for stretched/fabricated
    flagged = [
        r
        for r in report.bullet_reviews
        if r.classification in ("stretched", "fabricated")
    ]
    if flagged:
        console.print("\n[bold yellow]Flagged Bullets[/bold yellow]")
        for review in flagged:
            style = classification_styles[review.classification]
            label = review.classification
            console.print(f"  [{style}][{label}][/{style}] {review.bullet_text}")
            if review.explanation:
                console.print(f"    [dim]{review.explanation}[/dim]")
            if review.suggested_fix:
                console.print(f"    [dim]Fix: {review.suggested_fix}[/dim]")


def _score_color(score: int) -> str:
    """Return a Rich color name based on score."""
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"
