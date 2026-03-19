"""mkcv cover-letter — generate a cover letter from JD and resume/KB."""

import asyncio
import logging
import shutil
import sys
import tempfile
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

    Output is always placed alongside the JD in an application directory:
      - JD already in applications/ → output there
      - --app-dir / --company → output in that application dir
      - External JD → company/position inferred from LLM, app dir created
      - --output-dir overrides all automatic resolution
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

    try:
        jd_doc = read_jd(jd)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    jd_text = jd_doc.body

    # Resolve resume text and output directory
    resume_text: str | None = None
    kb_text: str | None = None
    resolved_company: str | None = None
    resolved_role: str | None = None
    resolved_output = output_dir
    needs_deferred_placement = False

    if app_dir is not None:
        resume_text, resolved_output, resolved_company, resolved_role = (
            _resolve_from_app_dir(app_dir, resolved_output)
        )
    elif company is not None:
        resume_text, resolved_output, resolved_company, resolved_role = (
            _resolve_from_company(company, resolved_output)
        )
    elif resume is not None:
        resume_text = _read_resume_file(resume)
    elif settings.in_workspace and settings.workspace_root:
        # Check if JD file is already inside an application dir
        jd_app_dir = _detect_jd_app_dir(jd) if not jd_is_url else None
        if jd_app_dir is not None:
            resume_text, resolved_output, resolved_company, resolved_role = (
                _resolve_from_app_dir(jd_app_dir, output_dir)
            )
            console.print(f"  [dim]JD is in app dir:[/dim] {jd_app_dir.name}")
        elif output_dir is None:
            # JD is external — we'll generate to a temp dir, then
            # use the LLM result to create the proper app dir.
            needs_deferred_placement = True

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

    # Determine generation directory — may be temp if deferred
    if needs_deferred_placement:
        gen_dir = Path(tempfile.mkdtemp(prefix="mkcv-cl-"))
    elif resolved_output is not None:
        # If output points to an app dir, create a versioned cover-letter subfolder
        if (resolved_output / "application.toml").is_file() and output_dir is None:
            workspace_service = create_workspace_service()
            gen_dir = workspace_service.create_output_version(
                resolved_output, "cover-letter"
            )
            console.print(f"  [dim]Output version: cover-letter/{gen_dir.name}[/dim]")
        else:
            gen_dir = resolved_output
    else:
        gen_dir = Path.cwd()

    gen_dir.mkdir(parents=True, exist_ok=True)

    # Display header (output dir may change if deferred)
    _display_header(
        jd_source=jd,
        resume_text=resume_text,
        kb_text=kb_text,
        output_dir=gen_dir,
        company=resolved_company,
        deferred=needs_deferred_placement,
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
                output_dir=gen_dir,
                company=resolved_company,
                role_title=resolved_role,
                render=render,
            )
        )
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    # Deferred placement: now we know company/role from the LLM result
    final_output = gen_dir
    if needs_deferred_placement:
        final_output = _place_in_application_dir(
            result=result,
            temp_dir=gen_dir,
            jd_text=jd_text,
            jd_source=jd,
            jd_is_url=jd_is_url,
            preset=preset or "standard",
        )

    # Save JD in the output dir if from URL/stdin (and not already there)
    if jd_is_url or jd_is_stdin:
        _save_jd_copy(jd_text, final_output, as_markdown=True)

    _display_result(result, final_output)


# ------------------------------------------------------------------
# Input resolution helpers
# ------------------------------------------------------------------


def _detect_jd_app_dir(jd_source: str) -> Path | None:
    """Check if a JD file path is inside an application directory.

    Returns the application directory if the JD lives inside one
    (identified by ``application.toml``), or None.
    """
    jd_path = Path(jd_source).resolve()
    if not jd_path.is_file():
        return None

    for parent in [jd_path.parent, *jd_path.parent.parents]:
        if (parent / "application.toml").is_file():
            return parent
        if (parent / "mkcv.toml").is_file():
            break

    return None


def _resolve_from_app_dir(
    app_dir: Path,
    output_dir: Path | None,
) -> tuple[str | None, Path, str | None, str | None]:
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
    output_dir: Path | None,
) -> tuple[str | None, Path, str | None, str | None]:
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

    console.print(f"  [dim]Auto-resolved:[/dim] {app_dir.name}")

    return (
        resume_text,
        output_dir or app_dir,
        resolved_company or company,
        role,
    )


def _place_in_application_dir(
    *,
    result: CoverLetterResult,
    temp_dir: Path,
    jd_text: str,
    jd_source: str,
    jd_is_url: bool,
    preset: str,
) -> Path:
    """Move generated files from temp dir to a proper application dir.

    Uses company and role_title from the LLM result to create a
    workspace application directory, then moves all output files there.
    """
    assert settings.workspace_root is not None

    company = result.company
    position = result.role_title

    if not company or not position:
        console.print(
            "  [yellow]\u26a0[/yellow] Could not infer company/position "
            "from JD — files remain in temp dir."
        )
        return temp_dir

    # Create the application dir via workspace service
    workspace_service = create_workspace_service()

    # Write JD to a temp file for workspace service
    jd_ext = ".md" if jd_is_url else ".txt"
    jd_tmp = temp_dir / f"jd{jd_ext}"
    if not jd_tmp.exists():
        jd_tmp.write_text(jd_text, encoding="utf-8")

    try:
        app_dir = workspace_service.setup_application(
            workspace_root=settings.workspace_root,
            company=company,
            position=position,
            jd_source=jd_tmp,
            preset_name=preset,
            url=jd_source if jd_is_url else None,
        )
    except MkcvError as exc:
        console.print(
            f"  [yellow]\u26a0[/yellow] Could not create app dir: "
            f"{exc} — files remain in: {temp_dir}"
        )
        return temp_dir

    console.print(f"  [green]\u2713[/green] Created application: {app_dir.name}")

    # Move all generated files from temp to app dir
    moved = _move_outputs(temp_dir, app_dir, result)

    # Clean up temp dir
    shutil.rmtree(temp_dir, ignore_errors=True)

    if moved:
        console.print(f"  [green]\u2713[/green] Moved {moved} files to {app_dir.name}")

    return app_dir


def _move_outputs(
    src_dir: Path,
    dst_dir: Path,
    result: CoverLetterResult,
) -> int:
    """Move cover letter output files and update result paths.

    Returns the number of files moved.
    """
    moved = 0
    updated_paths: dict[str, str] = {}

    for key, path_str in result.output_paths.items():
        src = Path(path_str)
        if src.is_file():
            dst = dst_dir / src.name
            shutil.move(str(src), str(dst))
            updated_paths[key] = str(dst)
            moved += 1
        else:
            updated_paths[key] = path_str

    # Also move the .mkcv/ artifacts and .typ source if present
    for pattern in ("*.typ", ".mkcv"):
        for item in src_dir.glob(pattern):
            dst = dst_dir / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(item), str(dst))
            elif item.is_file():
                shutil.move(str(item), str(dst))
            moved += 1

    # Update result in place (output_paths is a regular dict)
    result.output_paths.clear()
    result.output_paths.update(updated_paths)

    return moved


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


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
    deferred: bool = False,
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
    if deferred:
        console.print("  Output:   [dim]will auto-create application dir[/dim]")
    else:
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
