"""mkcv cover-letter — generate a cover letter from JD and resume/KB."""

import asyncio
import logging
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import (
    create_cover_letter_service,
    create_workspace_service,
)
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError
from mkcv.core.models.cover_letter_result import CoverLetterResult
from mkcv.core.services.jd_reader import read_jd

logger = logging.getLogger(__name__)

console = Console()


def cover_letter_command(
    *,
    jd: Annotated[
        str,
        cyclopts.Parameter(
            help=(
                'Job description source: file path, URL (http/https), or "-" for stdin.'
            ),
        ),
    ],
    app_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--app-dir",
            help="Application directory containing resume.yaml.",
        ),
    ] = None,
    company: Annotated[
        str | None,
        cyclopts.Parameter(
            help=("Company name — auto-resolves to latest application."),
        ),
    ] = None,
    position: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Position title (used with --company for output naming).",
        ),
    ] = None,
    resume: Annotated[
        Path | None,
        cyclopts.Parameter(
            help="Path to a resume.yaml file to use as context.",
        ),
    ] = None,
    kb: Annotated[
        Path | None,
        cyclopts.Parameter(
            help="Path to knowledge base file.",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--output-dir",
            help="Output directory for cover letter files.",
        ),
    ] = None,
    preset: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Preset name (concise/standard/comprehensive).",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Override AI provider for all stages.",
        ),
    ] = None,
    render: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--render", "--no-render"],
            help="Render cover letter to PDF.",
        ),
    ] = True,
) -> None:
    """Generate a cover letter from a job description and optional resume.

    Works with or without a resume — can use just the knowledge base and
    job description. Supports multiple input modes:

      --app-dir   Use resume from a specific application directory
      --company   Auto-find the latest resume for a company
      --resume    Use a specific resume.yaml file
      (none)      Auto-find latest resume or fall back to KB-only

    The --jd option accepts a file path, URL, or "-" for stdin.

    Output location is determined automatically:
      - JD from an application dir → output alongside resume
      - --company → output in that company's latest application
      - In workspace → creates/reuses application dir from JD context
      - Standalone → output in current directory or --output-dir
    """
    # Validate mutual exclusivity
    explicit_count = sum(1 for x in [app_dir, company, resume] if x is not None)
    if explicit_count > 1:
        console.print(
            "[red]Error:[/red] Only one of --app-dir, --company, "
            "or --resume can be specified."
        )
        sys.exit(2)

    # Determine JD source type and read content
    jd_is_url = jd.startswith("http://") or jd.startswith("https://")
    jd_is_stdin = jd in ("-", "")
    jd_is_file = not jd_is_url and not jd_is_stdin

    try:
        jd_text = read_jd(jd)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    # Resolve resume text and output directory
    resume_text: str | None = None
    kb_text: str | None = None
    resolved_company: str | None = None
    resolved_role: str | None = None
    resolved_output = output_dir

    if app_dir is not None:
        resume_text, resolved_output, resolved_company, resolved_role = (
            _resolve_from_app_dir(app_dir, resolved_output)
        )
    elif company is not None:
        resume_text, resolved_output, resolved_company, resolved_role = (
            _resolve_from_company(company, position, resolved_output)
        )
    elif resume is not None:
        resume_text = _read_resume_file(resume)
    elif settings.in_workspace and settings.workspace_root:
        # Smart resolution: check if JD file is inside applications/
        if jd_is_file and output_dir is None:
            jd_app_dir = _detect_jd_app_dir(jd)
            if jd_app_dir is not None:
                resume_text, resolved_output, resolved_company, resolved_role = (
                    _resolve_from_app_dir(jd_app_dir, None)
                )
                console.print(f"  [dim]JD is in app dir:[/dim] {jd_app_dir.name}")

        # If still no output, try auto-resolve
        if resolved_output is None and output_dir is None:
            resume_text_auto, auto_output, auto_company, auto_role = _resolve_auto(None)
            if resume_text is None:
                resume_text = resume_text_auto
            resolved_company = resolved_company or auto_company
            resolved_role = resolved_role or auto_role
            resolved_output = auto_output

    # Resolve KB text
    if kb is not None:
        kb_text = _read_file_safe(kb, "knowledge base")
    elif settings.in_workspace and settings.workspace_root:
        kb_relative = settings.workspace.knowledge_base
        kb_path = settings.workspace_root / kb_relative
        if kb_path.is_file():
            kb_text = kb_path.read_text(encoding="utf-8")

    # Ensure we have at least resume or KB
    if resume_text is None and kb_text is None:
        console.print(
            "[red]Error:[/red] At least one of --resume, --app-dir, "
            "--company, or --kb is required.\n"
            "  Provide a resume or knowledge base for cover letter "
            "context."
        )
        sys.exit(2)

    # Smart output dir: in workspace, create application dir if needed
    if resolved_output is None and output_dir is None:
        if settings.in_workspace and settings.workspace_root:
            resolved_output = _ensure_workspace_output(
                jd_text=jd_text,
                jd_source=jd,
                jd_is_url=jd_is_url,
                jd_is_file=jd_is_file,
                company_hint=resolved_company,
                position_hint=resolved_role,
                preset=preset or "standard",
            )
        else:
            resolved_output = Path.cwd()

    if resolved_output is None:
        resolved_output = Path.cwd()

    resolved_output.mkdir(parents=True, exist_ok=True)

    # Save JD in the output dir if it came from URL or stdin
    if jd_is_url or jd_is_stdin:
        _save_jd_copy(jd_text, resolved_output, as_markdown=True)
    elif jd_is_file:
        # Copy JD file if output dir is different from JD's parent
        jd_path = Path(jd).resolve()
        if jd_path.parent != resolved_output.resolve():
            _save_jd_copy(jd_text, resolved_output, as_markdown=False)

    # Display mode info
    _display_header(
        jd_source=jd,
        resume_text=resume_text,
        kb_text=kb_text,
        output_dir=resolved_output,
        company=resolved_company,
    )

    # Create and run the service
    try:
        service = create_cover_letter_service(settings, provider_override=provider)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    try:
        result = asyncio.run(
            service.generate(
                jd_text,
                resume_text=resume_text,
                kb_text=kb_text,
                output_dir=resolved_output,
                company=resolved_company,
                role_title=resolved_role,
                render=render,
            )
        )
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    _display_result(result, resolved_output)


# ------------------------------------------------------------------
# Input resolution helpers
# ------------------------------------------------------------------


def _detect_jd_app_dir(jd_source: str) -> Path | None:
    """Check if a JD file path is inside an applications/ directory.

    Returns the application directory if the JD lives inside one
    (identified by ``application.toml``), or None.
    """
    jd_path = Path(jd_source).resolve()
    if not jd_path.is_file():
        return None

    # Walk up from JD's parent looking for application.toml
    for parent in [jd_path.parent, *jd_path.parent.parents]:
        if (parent / "application.toml").is_file():
            return parent
        # Stop if we hit the workspace root or top of applications/
        if (parent / "mkcv.toml").is_file():
            break

    return None


def _resolve_from_app_dir(
    app_dir: Path,
    output_dir: Path | None,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Resolve resume from an explicit application directory."""
    if not app_dir.is_dir():
        console.print(f"[red]Error:[/red] Application directory not found: {app_dir}")
        sys.exit(2)

    resume_path = app_dir / "resume.yaml"
    resume_text: str | None = None
    if resume_path.is_file():
        resume_text = resume_path.read_text(encoding="utf-8")

    company, role = _read_app_metadata(app_dir)
    return resume_text, output_dir or app_dir, company, role


def _resolve_from_company(
    company: str,
    position: str | None,
    output_dir: Path | None,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Resolve resume from the latest application for a company."""
    if not settings.in_workspace or not settings.workspace_root:
        console.print(
            "[red]Error:[/red] --company requires a workspace. "
            "Run from inside an mkcv workspace."
        )
        sys.exit(2)

    workspace_service = create_workspace_service()
    app_dir = workspace_service.find_latest_application(
        settings.workspace_root, company=company
    )

    if app_dir is None:
        console.print(
            f"[red]Error:[/red] No applications found for company '{company}'."
        )
        sys.exit(2)

    resume_path = app_dir / "resume.yaml"
    resume_text: str | None = None
    if resume_path.is_file():
        resume_text = resume_path.read_text(encoding="utf-8")

    resolved_company, role = _read_app_metadata(app_dir)
    resolved_role = position or role

    console.print(f"  [dim]Auto-resolved:[/dim] {app_dir.name}")

    return (
        resume_text,
        output_dir or app_dir,
        resolved_company or company,
        resolved_role,
    )


def _resolve_auto(
    output_dir: Path | None,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Auto-resolve the latest resume from the workspace."""
    assert settings.workspace_root is not None

    workspace_service = create_workspace_service()

    app_dir = workspace_service.find_latest_application(settings.workspace_root)
    if app_dir is not None:
        resume_path = app_dir / "resume.yaml"
        if resume_path.is_file():
            resume_text = resume_path.read_text(encoding="utf-8")
            company, role = _read_app_metadata(app_dir)
            console.print(f"  [dim]Auto-resolved:[/dim] {app_dir.name}")
            return (
                resume_text,
                output_dir or app_dir,
                company,
                role,
            )

    return None, output_dir, None, None


def _ensure_workspace_output(
    *,
    jd_text: str,
    jd_source: str,
    jd_is_url: bool,
    jd_is_file: bool,
    company_hint: str | None,
    position_hint: str | None,
    preset: str,
) -> Path:
    """Create or find the right workspace output directory.

    When a JD is provided but no explicit output dir, this function
    creates an application directory if company/position can be inferred.
    Falls back to a ``cover-letters/`` generic directory otherwise.
    """
    assert settings.workspace_root is not None
    workspace_root = settings.workspace_root

    # If we have company+position hints, create a proper application dir
    if company_hint and position_hint:
        return _create_app_dir_for_cover_letter(
            workspace_root=workspace_root,
            jd_text=jd_text,
            jd_source=jd_source,
            jd_is_url=jd_is_url,
            jd_is_file=jd_is_file,
            company=company_hint,
            position=position_hint,
            preset=preset,
        )

    # Fall back to cover-letters/ generic directory
    return _create_generic_cl_output_dir(workspace_root, preset)


def _create_app_dir_for_cover_letter(
    *,
    workspace_root: Path,
    jd_text: str,
    jd_source: str,
    jd_is_url: bool,
    jd_is_file: bool,
    company: str,
    position: str,
    preset: str,
) -> Path:
    """Create an application directory for a cover letter.

    Reuses the workspace service to create a properly versioned
    application directory with the JD copied in.
    """
    workspace_service = create_workspace_service()

    # Write JD to a temp file for workspace service
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md" if jd_is_url else ".txt",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(jd_text)
        tmp_jd = Path(f.name)

    try:
        app_dir = workspace_service.setup_application(
            workspace_root=workspace_root,
            company=company,
            position=position,
            jd_source=tmp_jd,
            preset_name=preset,
            url=jd_source if jd_is_url else None,
        )
    except MkcvError as exc:
        console.print(
            f"  [yellow]\u26a0[/yellow] Could not create application dir: {exc}"
        )
        return _create_generic_cl_output_dir(workspace_root, preset)
    finally:
        tmp_jd.unlink(missing_ok=True)

    console.print(f"  [green]\u2713[/green] Created application: {app_dir.name}")
    return app_dir


def _create_generic_cl_output_dir(
    workspace_root: Path,
    preset: str,
) -> Path:
    """Create a versioned cover-letters/ output directory."""
    from mkcv.adapters.filesystem.workspace_manager import (
        _next_version,
    )

    cl_dir = workspace_root / "cover-letters"
    cl_dir.mkdir(exist_ok=True)

    date_prefix = date.today().strftime("%Y-%m")
    base_name = f"{date_prefix}-cover-letter-{preset}"
    version = _next_version(cl_dir, base_name)
    output = cl_dir / f"{base_name}-v{version}"
    output.mkdir(parents=True, exist_ok=True)
    return output


def _save_jd_copy(
    jd_text: str,
    output_dir: Path,
    *,
    as_markdown: bool,
) -> None:
    """Save a copy of the JD text in the output directory."""
    ext = ".md" if as_markdown else ".txt"
    jd_path = output_dir / f"jd{ext}"
    if not jd_path.exists():
        jd_path.write_text(jd_text, encoding="utf-8")
        logger.debug("Saved JD copy: %s", jd_path)


def _read_resume_file(resume_path: Path) -> str:
    """Read a resume YAML file."""
    if not resume_path.is_file():
        console.print(f"[red]Error:[/red] Resume file not found: {resume_path}")
        sys.exit(2)
    return resume_path.read_text(encoding="utf-8")


def _read_file_safe(path: Path, label: str) -> str:
    """Read a file, exiting on error."""
    if not path.is_file():
        console.print(f"[red]Error:[/red] {label} not found: {path}")
        sys.exit(2)
    return path.read_text(encoding="utf-8")


def _read_app_metadata(
    app_dir: Path,
) -> tuple[str | None, str | None]:
    """Read company and position from application.toml."""
    toml_path = app_dir / "application.toml"
    if not toml_path.is_file():
        return None, None

    try:
        import tomllib

        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        app_data = data.get("application", {})
        return app_data.get("company"), app_data.get("position")
    except Exception:
        return None, None


def _slugify(text: str) -> str:
    """Simple slug for output naming."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "cover-letter"


# ------------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------------


def _display_header(
    *,
    jd_source: str,
    resume_text: str | None,
    kb_text: str | None,
    output_dir: Path,
    company: str | None,
) -> None:
    """Display the generation header."""
    console.print()
    console.print("  [bold]mkcv cover-letter[/bold]")
    console.print(f"  JD:       {jd_source}")
    if company:
        console.print(f"  Company:  {company}")
    if resume_text is not None:
        console.print("  Resume:   [green]provided[/green]")
    else:
        console.print("  Resume:   [dim]none (KB-only mode)[/dim]")
    if kb_text is not None:
        console.print("  KB:       [green]provided[/green]")
    console.print(f"  Output:   {output_dir}")
    console.print()


def _display_result(
    result: CoverLetterResult,
    output_dir: Path,
) -> None:
    """Display cover letter generation results."""
    for stage in result.stages:
        model_short = stage.model.split("/")[-1]
        cost_str = f"${stage.cost_usd:.4f}" if stage.cost_usd > 0 else "free"
        console.print(
            f"  [green]\u2713[/green] {stage.stage_name} "
            f"[dim]({stage.duration_seconds:.1f}s, "
            f"{model_short}, {cost_str})[/dim]"
        )

    total_cost = sum(s.cost_usd for s in result.stages)
    cost_display = f"${total_cost:.4f}" if total_cost > 0 else "free"
    console.print()
    console.print(
        f"  Score: [bold]{result.review_score}[/bold]/100  "
        f"  Cost: {cost_display}  "
        f"  Duration: {result.total_duration_seconds:.1f}s"
    )

    # Output tree
    console.print()
    console.print(f"  Output: {output_dir}/")
    paths = result.output_paths
    items = list(paths.values())
    for i, path_str in enumerate(items):
        name = Path(path_str).name
        connector = (
            "\u2514\u2500\u2500" if i == len(items) - 1 else "\u251c\u2500\u2500"
        )
        console.print(f"  {connector} {name}")

    console.print()
