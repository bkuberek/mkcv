"""mkcv generate — run the AI pipeline to generate a tailored resume."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_pipeline_service, create_workspace_manager
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError

logger = logging.getLogger(__name__)

console = Console()


def generate_command(
    *,
    jd: Annotated[
        Path,
        cyclopts.Parameter(
            help="Path to job description file (text/markdown).",
        ),
    ],
    kb: Annotated[
        Path | None,
        cyclopts.Parameter(
            help=(
                "Path to knowledge base file. "
                "In workspace mode, defaults to config value."
            ),
        ),
    ] = None,
    company: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Company name (required in workspace mode).",
        ),
    ] = None,
    position: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Position title (required in workspace mode).",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--output-dir",
            help="Output directory (default: auto-generated).",
        ),
    ] = None,
    theme: Annotated[
        str,
        cyclopts.Parameter(
            help="RenderCV theme name.",
        ),
    ] = "sb2nov",
    profile: Annotated[
        str,
        cyclopts.Parameter(
            help="Provider profile (budget/premium).",
        ),
    ] = "premium",
    from_stage: Annotated[
        int,
        cyclopts.Parameter(
            name="--from-stage",
            help="Resume from this pipeline stage (1-5).",
        ),
    ] = 1,
    render: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--render", "--no-render"],
            help="Auto-render PDF after pipeline completes.",
        ),
    ] = True,
    interactive: Annotated[
        bool,
        cyclopts.Parameter(
            help="Pause after each stage for review.",
        ),
    ] = False,
) -> None:
    """Generate a tailored resume from a job description and knowledge base.

    Runs the AI pipeline: analyze JD, select experience, tailor content,
    structure YAML, and review.
    """
    # ---- Validate JD file ----
    if not jd.is_file():
        console.print(f"[red]Error:[/red] Job description file not found: {jd}")
        sys.exit(2)

    # ---- Workspace vs standalone mode ----
    if settings.in_workspace:
        _generate_workspace_mode(
            jd=jd,
            kb=kb,
            company=company,
            position=position,
            output_dir=output_dir,
            theme=theme,
            profile=profile,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
        )
    else:
        _generate_standalone_mode(
            jd=jd,
            kb=kb,
            output_dir=output_dir,
            theme=theme,
            profile=profile,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
        )


def _generate_workspace_mode(
    *,
    jd: Path,
    kb: Path | None,
    company: str | None,
    position: str | None,
    output_dir: Path | None,
    theme: str,
    profile: str,
    from_stage: int,
    render_pdf: bool,
    interactive: bool,
) -> None:
    """Generate in workspace mode — creates application directory."""
    workspace_root = settings.workspace_root
    assert workspace_root is not None  # guarded by settings.in_workspace

    # Resolve KB from workspace config if not provided
    if kb is None:
        kb_relative = settings.workspace.knowledge_base
        kb = workspace_root / kb_relative
    if not kb.is_file():
        console.print(f"[red]Error:[/red] Knowledge base not found: {kb}")
        sys.exit(2)

    # Company and position are required in workspace mode
    if company is None or position is None:
        console.print(
            "[red]Error:[/red] --company and --position are required in workspace mode."
        )
        sys.exit(2)

    console.print("\n  [bold]mkcv generate[/bold] — workspace mode")
    console.print(f"  Workspace: {workspace_root}")
    console.print(f"  JD:        {jd}")
    console.print(f"  KB:        {kb}")
    console.print(f"  Company:   {company}")
    console.print(f"  Position:  {position}")
    console.print(f"  Theme:     {theme}")
    console.print(f"  Profile:   {profile}")
    console.print()

    # Create application directory
    manager = create_workspace_manager()
    try:
        app_dir = manager.create_application(
            workspace_root=workspace_root,
            company=company,
            position=position,
            jd_source=jd,
        )
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    console.print(f"  [green]✓[/green] Created application: {app_dir.name}")

    # Use application dir as output if not specified
    run_dir = output_dir or app_dir

    # Run the pipeline
    _run_pipeline(
        jd=jd,
        kb=kb,
        output_dir=run_dir,
        from_stage=from_stage,
    )


def _generate_standalone_mode(
    *,
    jd: Path,
    kb: Path | None,
    output_dir: Path | None,
    theme: str,
    profile: str,
    from_stage: int,
    render_pdf: bool,
    interactive: bool,
) -> None:
    """Generate in standalone mode (no workspace)."""
    if kb is None:
        console.print(
            "[red]Error:[/red] --kb is required when not in a workspace.\n"
            "  Either provide --kb or run from inside an mkcv workspace "
            "(see: mkcv init)."
        )
        sys.exit(2)

    if not kb.is_file():
        console.print(f"[red]Error:[/red] Knowledge base not found: {kb}")
        sys.exit(2)

    # Create a .mkcv run directory in CWD
    run_dir = output_dir or (Path.cwd() / ".mkcv")
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print("\n  [bold]mkcv generate[/bold] — standalone mode")
    console.print(f"  JD:        {jd}")
    console.print(f"  KB:        {kb}")
    console.print(f"  Output:    {run_dir}")
    console.print(f"  Theme:     {theme}")
    console.print(f"  Profile:   {profile}")
    console.print()

    # Run the pipeline
    _run_pipeline(
        jd=jd,
        kb=kb,
        output_dir=run_dir,
        from_stage=from_stage,
    )


def _run_pipeline(
    *,
    jd: Path,
    kb: Path,
    output_dir: Path,
    from_stage: int,
) -> None:
    """Execute the AI pipeline and display results."""
    pipeline = create_pipeline_service(settings)

    console.print("  [bold]Running AI pipeline...[/bold]")
    console.print()

    try:
        result = asyncio.run(
            pipeline.generate(
                jd,
                kb,
                output_dir=output_dir,
                from_stage=from_stage,
            )
        )
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    # Display stage results
    for stage in result.stages:
        console.print(
            f"  [green]✓[/green] Stage {stage.stage_number}: "
            f"{stage.stage_name} ({stage.duration_seconds:.1f}s)"
        )

    console.print()
    console.print(f"  Company:  {result.company}")
    console.print(f"  Role:     {result.role_title}")
    console.print(f"  Score:    [bold]{result.review_score}[/bold]/100")
    console.print(f"  Duration: {result.total_duration_seconds:.1f}s")

    if result.output_paths.get("resume_yaml"):
        console.print(f"  Output:   {result.output_paths['resume_yaml']}")

    console.print()
