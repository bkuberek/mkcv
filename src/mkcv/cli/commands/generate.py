"""mkcv generate — run the AI pipeline to generate a tailored resume."""

import asyncio
import json
import logging
import re
import shutil
import sys
import time
import tomllib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts
from rich.console import Console

if TYPE_CHECKING:
    from rich.status import Status

from mkcv.adapters.factory import (
    create_cover_letter_service,
    create_pipeline_service,
    create_regeneration_service,
    create_render_service,
    create_workspace_service,
)
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError
from mkcv.core.models.kb_validation import KBValidationResult
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.run_metadata import RunMetadata
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.services.jd_reader import read_jd
from mkcv.core.services.kb_validator import validate_kb
from mkcv.core.services.theme import resolve_theme

logger = logging.getLogger(__name__)

console = Console()

_STAGE_LABELS: dict[int, str] = {
    1: "Analyzing job description",
    2: "Selecting experience",
    3: "Tailoring content",
    4: "Structuring resume YAML",
    5: "Reviewing resume",
}


_PROFILE_TO_PRESET: dict[str, str] = {
    "budget": "concise",
    "premium": "standard",
    "default": "standard",
}

_PROFILE_PROVIDER_OVERRIDES: dict[str, str] = {
    "budget": "ollama",
}

_PRESET_SENTINEL = "__unset__"


def generate_command(
    *,
    jd: Annotated[
        str | None,
        cyclopts.Parameter(
            help=(
                "Job description source: file path, URL (http/https), "
                '"-" for stdin, or omit for a generic resume.'
            ),
        ),
    ] = None,
    kb: Annotated[
        Path | None,
        cyclopts.Parameter(
            help=(
                "Path to knowledge base file. "
                "In workspace mode, defaults to config value."
            ),
        ),
    ] = None,
    target: Annotated[
        str | None,
        cyclopts.Parameter(
            help=(
                "Target role for generic resume (used when --jd is omitted). "
                'E.g. "Senior Software Engineer" or "Staff Backend Engineer, Python".'
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
    app_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--app-dir",
            help="Re-generate from an existing application directory.",
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
        str | None,
        cyclopts.Parameter(
            help=(
                "Visual theme for the resume (fonts, colors, layout). "
                "Run 'mkcv themes' to list available options."
            ),
        ),
    ] = None,
    preset: Annotated[
        str,
        cyclopts.Parameter(
            help="Resume preset (concise/standard/comprehensive).",
        ),
    ] = _PRESET_SENTINEL,
    profile: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Deprecated: use --preset instead.",
            show=False,
        ),
    ] = None,
    provider: Annotated[
        str | None,
        cyclopts.Parameter(
            help=(
                "Override AI provider for all stages "
                "(anthropic/openai/openrouter/ollama)."
            ),
        ),
    ] = None,
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
            help="Review and edit resume sections interactively after AI tailoring.",
        ),
    ] = False,
    cover_letter: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--cover-letter", "--no-cover-letter"],
            help="Chain cover letter generation after resume pipeline.",
        ),
    ] = False,
    cv_preset: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--cv-preset",
            help="Override preset for resume only (default: --preset value).",
        ),
    ] = None,
    cl_preset: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--cl-preset",
            help="Override preset for cover letter only (default: --preset value).",
        ),
    ] = None,
) -> None:
    """Generate a tailored resume from a job description and knowledge base.

    Runs the AI pipeline: analyze JD, select experience, tailor content,
    structure YAML, and review.

    The --jd option accepts a file path, an HTTP/HTTPS URL, or "-" to
    read from stdin. Omit --jd to generate a generic resume (optionally
    with --target to specify the role).
    """
    # ---- Mutual exclusivity: --app-dir vs --jd/--company/--position/--target ----
    if app_dir is not None:
        conflicting = {
            "--jd": jd,
            "--company": company,
            "--position": position,
            "--target": target,
        }
        provided = [name for name, val in conflicting.items() if val is not None]
        if provided:
            flags = ", ".join(provided)
            console.print(
                f"[red]Error:[/red] --app-dir cannot be combined with {flags}."
            )
            sys.exit(2)

    # ---- Resolve preset from --preset / --profile ----
    resolved_preset, resolved_provider = _resolve_preset_and_provider(
        preset_raw=preset, profile=profile, provider=provider
    )

    # ---- Resolve theme from CLI / config / default ----
    effective_theme = resolve_theme(theme, settings.rendering.theme)

    # Resolve per-output-type presets (needed before app-dir dispatch)
    effective_cv_preset = cv_preset or resolved_preset
    effective_cl_preset = cl_preset or resolved_preset

    # ---- App-dir regeneration mode ----
    if app_dir is not None:
        _generate_from_app_dir(
            app_dir=app_dir,
            kb=kb,
            output_dir=output_dir,
            theme=effective_theme,
            preset=effective_cv_preset,
            provider=resolved_provider,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
            chain_cover_letter=cover_letter,
            cl_preset=effective_cl_preset,
        )
        return

    # ---- Resolve JD source ----
    if jd is not None:
        jd_text, jd_display = _resolve_jd(jd)
    else:
        jd_text = _build_generic_jd(target)
        jd_display = f"<generic: {target}>" if target else "<generic resume>"

    # ---- Workspace vs standalone mode ----
    # Generic mode (no JD): skip application directory creation even in a
    # workspace. Resolve KB from workspace config but output to .mkcv/.
    is_generic = jd is None
    use_workspace_mode = settings.in_workspace and not is_generic

    # If in workspace mode without company/position, extract from JD via LLM
    if use_workspace_mode and (not company or not position):
        extracted_company, extracted_position = _extract_jd_metadata(
            jd_text,
            preset=effective_cv_preset,
            provider_override=resolved_provider,
            theme=effective_theme,
        )
        if not company:
            company = extracted_company
        if not position:
            position = extracted_position

        if not company or not position:
            console.print(
                "[red]Error:[/red] Could not determine company/position from JD.\n"
                "  Provide --company and --position explicitly."
            )
            sys.exit(2)

    if use_workspace_mode:
        _generate_workspace_mode(
            jd_text=jd_text,
            jd_display=jd_display,
            kb=kb,
            company=company,
            position=position,
            output_dir=output_dir,
            theme=effective_theme,
            preset=effective_cv_preset,
            provider=resolved_provider,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
            chain_cover_letter=cover_letter,
            cl_preset=effective_cl_preset,
        )
    else:
        # Standalone mode, or generic mode inside a workspace.
        # In a workspace, resolve KB from config if not provided.
        if kb is None and settings.in_workspace and settings.workspace_root:
            kb_relative = settings.workspace.knowledge_base
            kb = settings.workspace_root / kb_relative

        _generate_standalone_mode(
            jd_text=jd_text,
            jd_display=jd_display,
            kb=kb,
            output_dir=output_dir,
            theme=effective_theme,
            preset=effective_cv_preset,
            provider=resolved_provider,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
            chain_cover_letter=cover_letter,
            cl_preset=effective_cl_preset,
        )


def _resolve_preset_and_provider(
    *,
    preset_raw: str,
    profile: str | None,
    provider: str | None,
) -> tuple[str, str | None]:
    """Resolve the effective preset name and optional provider override.

    Handles backward-compatible mapping from legacy ``--profile`` values
    and prints a deprecation warning when ``--profile`` is used.

    Args:
        preset_raw: Raw ``--preset`` value (may be the sentinel).
        profile: Legacy ``--profile`` value, or None if not provided.
        provider: Explicit ``--provider`` override, or None.

    Returns:
        Tuple of (preset_name, provider_override).
    """
    preset_explicitly_set = preset_raw != _PRESET_SENTINEL

    if profile is not None and not preset_explicitly_set:
        console.print(
            "[yellow]Warning:[/yellow] --profile is deprecated, use --preset instead."
        )
        resolved_preset = _PROFILE_TO_PRESET.get(profile, "standard")
        if provider is None:
            provider = _PROFILE_PROVIDER_OVERRIDES.get(profile)
        return resolved_preset, provider

    resolved_preset = preset_raw if preset_explicitly_set else "standard"
    return resolved_preset, provider


def _default_output_dir(jd_display: str, preset_name: str) -> Path:
    """Build a dated, versioned output directory for resume generation.

    In a workspace:
        Generic:  resumes/{YYYY-MM}-{slug}-{preset}-v{N}/
        Targeted: handled by workspace mode, not this function.
    Outside a workspace:
        output/{YYYY-MM}-{slug}-{preset}-v{N}/

    Version numbering increments automatically: v1, v2, v3, etc.
    """
    date_prefix = date.today().strftime("%Y-%m")

    # Extract a slug from the display label
    if jd_display.startswith("<generic:"):
        raw = jd_display.removeprefix("<generic:").removesuffix(">").strip()
    elif jd_display == "<generic resume>":
        raw = "generic"
    else:
        # Targeted standalone (JD file/URL) — use the source name
        raw = (
            Path(jd_display).stem
            if "/" in jd_display or "." in jd_display
            else jd_display
        )
        raw = raw[:40]

    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:40] or "resume"
    base_name = f"{date_prefix}-{slug}-{preset_name}"

    if settings.in_workspace and settings.workspace_root:
        base = settings.workspace_root / "resumes"
    else:
        base = Path.cwd() / "output"

    version = _find_next_version(base, base_name)
    return base / f"{base_name}-v{version}"


def _find_next_version(parent: Path, base_name: str) -> int:
    """Scan a directory for existing versioned dirs and return the next number.

    Args:
        parent: Directory to scan.
        base_name: The prefix before ``-v{N}``.

    Returns:
        The next version number (>= 1).
    """
    if not parent.is_dir():
        return 1

    pattern = re.compile(re.escape(base_name) + r"-v(\d+)$")
    max_version = 0
    for entry in parent.iterdir():
        if entry.is_dir():
            match = pattern.match(entry.name)
            if match:
                max_version = max(max_version, int(match.group(1)))

    return max_version + 1


def _build_generic_jd(target: str | None) -> str:
    """Build a synthetic JD for a generic (non-targeted) resume.

    When no real JD is provided, this creates a broad description
    that guides the pipeline to produce a general-purpose resume
    showcasing the candidate's strongest skills and achievements.
    """
    role = target or "Software Engineer"
    return (
        f"Position: {role}\n\n"
        "This is a general-purpose resume. There is no specific job posting.\n\n"
        "Produce a strong, well-rounded resume that:\n"
        "- Highlights the candidate's most impactful achievements and metrics\n"
        "- Showcases breadth and depth of technical skills\n"
        "- Emphasizes leadership, architecture, and system design experience\n"
        "- Uses clear, concise XYZ-formula bullet points\n"
        "- Is suitable for senior-level individual contributor or technical "
        "leadership roles\n"
        "- Covers the candidate's strongest and most recent experience\n\n"
        "Requirements:\n"
        "- Strong software engineering background\n"
        "- System design and architecture experience\n"
        "- Track record of delivering measurable impact\n"
        "- Collaboration across teams and stakeholders\n"
    )


def _extract_jd_metadata(
    jd_text: str,
    *,
    preset: str,
    provider_override: str | None,
    theme: str,
) -> tuple[str | None, str | None]:
    """Use a lightweight LLM call to extract company and position from JD text.

    Args:
        jd_text: Raw job description text.
        preset: Preset name for pipeline creation.
        provider_override: Optional provider override.
        theme: Theme name for pipeline creation.

    Returns:
        Tuple of (company, position), either may be None.
    """
    console.print("  [dim]Extracting company/position from JD via LLM...[/dim]")

    try:
        pipeline = create_pipeline_service(
            settings,
            preset_name=preset,
            provider_override=provider_override,
            theme=theme,
        )
        metadata = asyncio.run(pipeline.extract_jd_metadata(jd_text))
    except MkcvError as exc:
        logger.warning("JD metadata extraction failed: %s", exc)
        return None, None
    except Exception:
        logger.warning("JD metadata extraction failed", exc_info=True)
        return None, None

    company = metadata.company
    position = metadata.position

    if company:
        console.print(f"  [green]\u2713[/green] Company:  {company}")
    if position:
        console.print(f"  [green]\u2713[/green] Position: {position}")

    return company, position


def _resolve_jd(source: str) -> tuple[str, str]:
    """Resolve the JD source to text and a display label.

    Returns:
        Tuple of (jd_text, display_label).
    """
    is_url = source.startswith("http://") or source.startswith("https://")
    is_stdin = source in ("-", "")

    if is_url:
        console.print(f"  Fetching JD from URL: {source}")
    elif is_stdin:
        console.print("  Reading JD from stdin...")

    try:
        jd_doc = read_jd(source)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    jd_text = jd_doc.body

    if is_url:
        display = source
    elif is_stdin:
        display = "<stdin>"
    else:
        display = source

    return jd_text, display


def _write_jd_file(jd_text: str, target_dir: Path) -> Path:
    """Write JD text to a file in the target directory.

    Returns:
        Path to the written JD file.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    jd_path = target_dir / "jd.txt"
    jd_path.write_text(jd_text, encoding="utf-8")
    return jd_path


# ------------------------------------------------------------------
# App-dir regeneration helpers
# ------------------------------------------------------------------


def _find_jd_in_app_dir(app_dir: Path) -> Path | None:
    """Find a JD file in an application directory.

    Checks for ``jd.md`` first, then ``jd.txt``.

    Args:
        app_dir: Application directory to search.

    Returns:
        Path to the JD file, or None if not found.
    """
    for name in ("jd.md", "jd.txt"):
        jd_path = app_dir / name
        if jd_path.is_file():
            return jd_path
    return None


def _read_app_metadata(app_dir: Path) -> tuple[str | None, str | None]:
    """Read company and position from ``application.toml``.

    Args:
        app_dir: Application directory containing ``application.toml``.

    Returns:
        Tuple of (company, position), either may be None.
    """
    toml_path = app_dir / "application.toml"
    if not toml_path.is_file():
        return None, None

    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        app_data = data.get("application", {})
        return app_data.get("company"), app_data.get("position")
    except (tomllib.TOMLDecodeError, OSError):
        return None, None


def _find_latest_version_dir(parent: Path) -> Path | None:
    """Find the highest-numbered ``v{N}`` directory under *parent*.

    Args:
        parent: Directory to scan for versioned subdirectories.

    Returns:
        Path to the latest version directory, or None if none exist.
    """
    if not parent.is_dir():
        return None

    pattern = re.compile(r"^v(\d+)$")
    versions: list[tuple[int, Path]] = []
    for entry in parent.iterdir():
        if entry.is_dir():
            match = pattern.match(entry.name)
            if match:
                versions.append((int(match.group(1)), entry))

    if not versions:
        return None

    versions.sort(key=lambda x: x[0])
    return versions[-1][1]


def _copy_stage_artifacts(source_version: Path, target_version: Path) -> int:
    """Copy pipeline stage JSON artifacts from one version to another.

    Copies all ``.json`` files from ``source_version/.mkcv/`` into
    ``target_version/.mkcv/``, creating the target directory if needed.

    Args:
        source_version: Source version directory (e.g., ``app/resumes/v1``).
        target_version: Target version directory (e.g., ``app/resumes/v2``).

    Returns:
        Number of files copied.
    """
    source_mkcv = source_version / ".mkcv"
    if not source_mkcv.is_dir():
        return 0

    target_mkcv = target_version / ".mkcv"
    target_mkcv.mkdir(parents=True, exist_ok=True)

    copied = 0
    for json_file in sorted(source_mkcv.glob("*.json")):
        shutil.copy2(str(json_file), str(target_mkcv / json_file.name))
        copied += 1

    return copied


def _generate_from_app_dir(
    *,
    app_dir: Path,
    kb: Path | None,
    output_dir: Path | None,
    theme: str,
    preset: str,
    provider: str | None,
    from_stage: int,
    render_pdf: bool,
    interactive: bool,
    chain_cover_letter: bool = False,
    cl_preset: str = "standard",
) -> None:
    """Re-generate a resume from an existing application directory.

    Validates the app dir, finds JD and metadata, creates a new version
    directory, copies prior stage artifacts when resuming, and runs the
    pipeline.

    Args:
        app_dir: Existing application directory path.
        kb: Optional explicit knowledge base path.
        output_dir: Optional explicit output directory.
        theme: Visual theme name.
        preset: Pipeline preset name.
        provider: Optional AI provider override.
        from_stage: Pipeline stage to resume from (1-5).
        render_pdf: Whether to auto-render PDF after pipeline.
        interactive: Whether to pause after each stage.
        chain_cover_letter: Whether to chain cover letter generation.
        cl_preset: Preset for cover letter generation.
    """
    # 1. Resolve to absolute path
    app_dir = app_dir.resolve()

    # 2. Validate directory exists
    if not app_dir.is_dir():
        console.print(f"[red]Error:[/red] Application directory not found: {app_dir}")
        sys.exit(2)

    # 3. Validate application.toml exists
    if not (app_dir / "application.toml").is_file():
        console.print(
            "[red]Error:[/red] Not an application directory — "
            f"missing application.toml in {app_dir}"
        )
        sys.exit(2)

    # 4. Find JD
    jd_path = _find_jd_in_app_dir(app_dir)
    if jd_path is None:
        console.print(
            "[red]Error:[/red] No JD file found in application directory.\n"
            f"  Expected jd.md or jd.txt in {app_dir}"
        )
        sys.exit(2)

    # 5. Read company/position from metadata
    app_company, app_position = _read_app_metadata(app_dir)
    if not app_company or not app_position:
        console.print(
            "[red]Error:[/red] Could not read company/position from "
            f"application.toml in {app_dir}"
        )
        sys.exit(2)

    # 6. Resolve KB
    if kb is None and settings.in_workspace and settings.workspace_root:
        kb_relative = settings.workspace.knowledge_base
        kb = settings.workspace_root / kb_relative
    if kb is None:
        console.print(
            "[red]Error:[/red] --kb is required when not in a workspace.\n"
            "  Provide --kb or run from inside an mkcv workspace."
        )
        sys.exit(2)
    if not kb.is_file():
        console.print(f"[red]Error:[/red] Knowledge base not found: {kb}")
        sys.exit(2)

    # 7. Create version dir
    if output_dir is not None:
        run_dir = output_dir
    else:
        workspace_service = create_workspace_service()
        run_dir = workspace_service.create_output_version(app_dir, "resumes")

    # 8. Copy prior stage artifacts when resuming from a later stage
    if from_stage > 1:
        latest_version = _find_latest_version_dir(app_dir / "resumes")
        # Exclude the newly created run_dir from "latest" consideration
        if latest_version is not None and latest_version == run_dir:
            # The newly created dir is the latest; look for the one before
            resumes_parent = app_dir / "resumes"
            pattern = re.compile(r"^v(\d+)$")
            versions: list[tuple[int, Path]] = []
            for entry in resumes_parent.iterdir():
                if entry.is_dir() and entry != run_dir:
                    match = pattern.match(entry.name)
                    if match:
                        versions.append((int(match.group(1)), entry))
            if versions:
                versions.sort(key=lambda x: x[0])
                latest_version = versions[-1][1]
            else:
                latest_version = None

        if latest_version is None:
            console.print(
                "[red]Error:[/red] --from-stage requires a previous version "
                "to copy artifacts from, but no prior version was found."
            )
            sys.exit(2)

        copied = _copy_stage_artifacts(latest_version, run_dir)
        if copied > 0:
            console.print(
                f"  [green]\u2713[/green] Copied {copied} stage artifact(s) "
                f"from {latest_version.name}"
            )

    # 9. Display header
    console.print("\n  [bold]mkcv generate[/bold] — app-dir regeneration")
    console.print(f"  App dir:   {app_dir}")
    console.print(f"  Company:   {app_company}")
    console.print(f"  Position:  {app_position}")
    console.print(f"  JD:        {jd_path}")
    console.print(f"  KB:        {kb}")
    console.print(f"  Output:    {run_dir}")
    console.print(f"  Theme:     {theme}")
    console.print(f"  Preset:    {preset}")
    if from_stage > 1:
        console.print(f"  From:      stage {from_stage}")
    console.print()

    # 10. Run the pipeline
    _run_pipeline(
        jd=jd_path,
        kb=kb,
        output_dir=run_dir,
        preset_name=preset,
        provider_override=provider,
        from_stage=from_stage,
        render_pdf=render_pdf,
        theme=theme,
        interactive=interactive,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_path.read_text(encoding="utf-8"),
        cl_preset=cl_preset,
        app_dir=app_dir,
    )


def _generate_workspace_mode(
    *,
    jd_text: str,
    jd_display: str,
    kb: Path | None,
    company: str | None,
    position: str | None,
    output_dir: Path | None,
    theme: str,
    preset: str,
    provider: str | None,
    from_stage: int,
    render_pdf: bool,
    interactive: bool,
    chain_cover_letter: bool = False,
    cl_preset: str = "standard",
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

    # Company and position are guaranteed by the caller dispatch logic
    assert company is not None
    assert position is not None

    console.print("\n  [bold]mkcv generate[/bold] — workspace mode")
    console.print(f"  Workspace: {workspace_root}")
    console.print(f"  JD:        {jd_display}")
    console.print(f"  KB:        {kb}")
    console.print(f"  Company:   {company}")
    console.print(f"  Position:  {position}")
    console.print(f"  Theme:     {theme}")
    console.print(f"  Preset:    {preset}")
    console.print()

    # Write JD to a temp file for the workspace service
    jd_file = _write_jd_file(jd_text, workspace_root / ".mkcv-tmp")
    try:
        # Create application directory via workspace service
        workspace_service = create_workspace_service()
        try:
            app_dir = workspace_service.setup_application(
                workspace_root=workspace_root,
                company=company,
                position=position,
                jd_source=jd_file,
                preset_name=preset,
            )
        except MkcvError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            sys.exit(exc.exit_code)
    finally:
        # Clean up temp JD file
        jd_file.unlink(missing_ok=True)
        tmp_dir = jd_file.parent
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()

    console.print(f"  [green]\u2713[/green] Created application: {app_dir.name}")

    # Create versioned output sub-folder for resumes
    if output_dir is not None:
        run_dir = output_dir
    else:
        version_dir = workspace_service.create_output_version(app_dir, "resumes")
        run_dir = version_dir
        console.print(
            f"  [green]\u2713[/green] Output version: resumes/{version_dir.name}"
        )

    # Write JD to the run directory for the pipeline
    jd_path = _write_jd_file(jd_text, run_dir)

    # Run the pipeline
    _run_pipeline(
        jd=jd_path,
        kb=kb,
        output_dir=run_dir,
        preset_name=preset,
        provider_override=provider,
        from_stage=from_stage,
        render_pdf=render_pdf,
        theme=theme,
        interactive=interactive,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_text,
        cl_preset=cl_preset,
        app_dir=app_dir,
    )


def _generate_standalone_mode(
    *,
    jd_text: str,
    jd_display: str,
    kb: Path | None,
    output_dir: Path | None,
    theme: str,
    preset: str,
    provider: str | None,
    from_stage: int,
    render_pdf: bool,
    interactive: bool,
    chain_cover_letter: bool = False,
    cl_preset: str = "standard",
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

    # Output directory: explicit flag, or auto-generated with date + slug
    run_dir = output_dir or _default_output_dir(jd_display, preset)
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print("\n  [bold]mkcv generate[/bold] — standalone mode")
    console.print(f"  JD:        {jd_display}")
    console.print(f"  KB:        {kb}")
    console.print(f"  Output:    {run_dir}")
    console.print(f"  Theme:     {theme}")
    console.print(f"  Preset:    {preset}")
    console.print()

    # Write JD to the run directory for the pipeline
    jd_path = _write_jd_file(jd_text, run_dir)

    # Run the pipeline
    _run_pipeline(
        jd=jd_path,
        kb=kb,
        output_dir=run_dir,
        preset_name=preset,
        provider_override=provider,
        from_stage=from_stage,
        render_pdf=render_pdf,
        theme=theme,
        interactive=interactive,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_text,
        cl_preset=cl_preset,
    )


def _run_pipeline(
    *,
    jd: Path,
    kb: Path,
    output_dir: Path,
    preset_name: str,
    provider_override: str | None = None,
    from_stage: int,
    render_pdf: bool = True,
    theme: str,
    interactive: bool = False,
    chain_cover_letter: bool = False,
    jd_text: str = "",
    cl_preset: str = "standard",
    app_dir: Path | None = None,
) -> None:
    """Execute the AI pipeline, display results, and optionally render PDF."""
    # ---- Validate KB before running pipeline ----
    kb_content = kb.read_text(encoding="utf-8")
    kb_result = validate_kb(kb_content)
    _display_kb_validation(kb_result)
    if not kb_result.is_valid:
        sys.exit(5)

    if interactive and from_stage <= 3:
        _run_interactive_pipeline(
            jd=jd,
            kb=kb,
            output_dir=output_dir,
            preset_name=preset_name,
            provider_override=provider_override,
            from_stage=from_stage,
            render_pdf=render_pdf,
            theme=theme,
            chain_cover_letter=chain_cover_letter,
            jd_text=jd_text,
            cl_preset=cl_preset,
            app_dir=app_dir,
        )
        return

    _run_standard_pipeline(
        jd=jd,
        kb=kb,
        output_dir=output_dir,
        preset_name=preset_name,
        provider_override=provider_override,
        from_stage=from_stage,
        render_pdf=render_pdf,
        theme=theme,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_text,
        cl_preset=cl_preset,
        app_dir=app_dir,
    )


def _run_standard_pipeline(
    *,
    jd: Path,
    kb: Path,
    output_dir: Path,
    preset_name: str,
    provider_override: str | None = None,
    from_stage: int = 1,
    render_pdf: bool = True,
    theme: str,
    chain_cover_letter: bool = False,
    jd_text: str = "",
    cl_preset: str = "standard",
    app_dir: Path | None = None,
) -> None:
    """Run the full AI pipeline without interactive review."""
    pipeline = create_pipeline_service(
        settings,
        preset_name=preset_name,
        provider_override=provider_override,
        theme=theme,
    )

    callback = _ProgressCallback(console)

    console.print("  [bold]Running AI pipeline...[/bold]")
    console.print()

    try:
        result = asyncio.run(
            pipeline.generate(
                jd,
                kb,
                output_dir=output_dir,
                from_stage=from_stage,
                stage_callback=callback,
                theme=theme,
            )
        )
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    _finalize_pipeline(
        result=result,
        output_dir=output_dir,
        preset_name=preset_name,
        provider_override=provider_override,
        render_pdf=render_pdf,
        theme=theme,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_text,
        cl_preset=cl_preset,
        app_dir=app_dir,
    )


def _run_interactive_pipeline(
    *,
    jd: Path,
    kb: Path,
    output_dir: Path,
    preset_name: str,
    provider_override: str | None = None,
    from_stage: int = 1,
    render_pdf: bool = True,
    theme: str,
    chain_cover_letter: bool = False,
    jd_text: str = "",
    cl_preset: str = "standard",
    app_dir: Path | None = None,
) -> None:
    """Run stages 1-3 with spinners, interactive review, then stages 4-5.

    After stage 3 produces ``TailoredContent``, an ``InteractiveSession``
    lets the user accept, skip, or edit each section.  On ``/done`` the
    (possibly modified) content is written back to the artifact store and
    stages 4-5 continue.  On ``/cancel`` the process exits cleanly.
    """
    from mkcv.cli.interactive import InteractiveSession
    from mkcv.core.models.tailored_content import TailoredContent

    artifact_dir = output_dir / ".mkcv"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # -- Phase 1: run stages 1-3 with spinners (no interactive prompts) --
    pipeline = create_pipeline_service(
        settings,
        preset_name=preset_name,
        provider_override=provider_override,
        theme=theme,
    )

    stop_callback = _StopAfterStageCallback(console, stop_after=3)

    console.print("  [bold]Running AI pipeline (stages 1-3)...[/bold]")
    console.print()

    try:
        first_result = asyncio.run(
            pipeline.generate(
                jd,
                kb,
                output_dir=output_dir,
                from_stage=from_stage,
                stage_callback=stop_callback,
                theme=theme,
            )
        )
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    # -- Phase 2: load stage-3 content and run interactive session --
    stage3_path = artifact_dir / "stage3_content.json"
    if not stage3_path.is_file():
        console.print(
            "  [red]Error:[/red] Stage 3 content not found — "
            "cannot start interactive review."
        )
        sys.exit(1)

    stage3_data = json.loads(stage3_path.read_text(encoding="utf-8"))
    content = TailoredContent.model_validate(stage3_data)

    # -- Build regeneration service and context (graceful degradation) --
    regen_service = None
    regen_context = None

    stage1_path = artifact_dir / "stage1_analysis.json"
    if stage1_path.is_file():
        from mkcv.core.models.regeneration_context import RegenerationContext

        try:
            jd_data = json.loads(stage1_path.read_text(encoding="utf-8"))
            kb_text = kb.read_text(encoding="utf-8")

            # Optionally load stage-2 selection for richer context
            stage2_path = artifact_dir / "stage2_selection.json"
            sel_data = None
            if stage2_path.is_file():
                sel_data = json.loads(stage2_path.read_text(encoding="utf-8"))

            regen_context = RegenerationContext(
                jd_analysis=jd_data,
                ats_keywords=jd_data.get("ats_keywords", []),
                kb_text=kb_text,
                selection=sel_data,
            )
            regen_service = create_regeneration_service(
                settings,
                preset_name=preset_name,
                provider_override=provider_override,
            )
            logger.debug("Regeneration service created for interactive session")
        except Exception:
            logger.warning(
                "Could not create regeneration service; "
                "interactive regeneration will be unavailable",
                exc_info=True,
            )
            regen_service = None
            regen_context = None
    else:
        logger.debug(
            "Stage 1 artifact not found at %s; "
            "interactive regeneration will be unavailable",
            stage1_path,
        )

    # -- Build prompt function with tab completion (graceful degradation) --
    from mkcv.cli.interactive.prompt_input import create_prompt_fn
    from mkcv.cli.interactive.sections import build_sections

    sections = build_sections(content)
    prompt_fn = create_prompt_fn(sections)

    session = InteractiveSession(
        content,
        console,
        regeneration_service=regen_service,
        regeneration_context=regen_context,
        prompt_fn=prompt_fn,
    )
    edited_content = session.run()

    if edited_content is None:
        console.print("  [dim]Interactive review cancelled. No output generated.[/dim]")
        sys.exit(130)

    # -- Phase 3: write modified content back and run stages 4-5 --
    stage3_path.write_text(
        json.dumps(edited_content.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    logger.debug("Wrote edited stage3_content back to %s", stage3_path)

    pipeline_4 = create_pipeline_service(
        settings,
        preset_name=preset_name,
        provider_override=provider_override,
        theme=theme,
    )

    resume_callback = _ProgressCallback(console)

    console.print()
    console.print("  [bold]Running AI pipeline (stages 4-5)...[/bold]")
    console.print()

    try:
        second_result = asyncio.run(
            pipeline_4.generate(
                jd,
                kb,
                output_dir=output_dir,
                from_stage=4,
                stage_callback=resume_callback,
                theme=theme,
            )
        )
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    # Merge stage metadata from both runs for accurate summaries
    merged_result = _merge_pipeline_results(first_result, second_result)

    _finalize_pipeline(
        result=merged_result,
        output_dir=output_dir,
        preset_name=preset_name,
        provider_override=provider_override,
        render_pdf=render_pdf,
        theme=theme,
        chain_cover_letter=chain_cover_letter,
        jd_text=jd_text,
        cl_preset=cl_preset,
        app_dir=app_dir,
    )


def _finalize_pipeline(
    *,
    result: PipelineResult,
    output_dir: Path,
    preset_name: str,
    provider_override: str | None,
    render_pdf: bool,
    theme: str,
    chain_cover_letter: bool,
    jd_text: str,
    cl_preset: str,
    app_dir: Path | None,
) -> None:
    """Write metadata, display summary, render PDF, and chain cover letter."""
    # Write run metadata in the output directory
    _write_run_metadata(
        output_dir=output_dir,
        result=result,
        preset_name=preset_name,
        provider_override=provider_override,
    )

    # Display stage summary
    _display_pipeline_summary(result)

    # Auto-render PDF
    pdf_rendered = False
    pdf_path_str: str | None = None
    if render_pdf:
        pdf_rendered, pdf_path_str = _auto_render(result, output_dir, theme=theme)

    # Display output tree
    _display_output_tree(
        result, output_dir, pdf_rendered=pdf_rendered, pdf_path=pdf_path_str
    )

    # Chain cover letter if requested
    if chain_cover_letter:
        _chain_cover_letter(
            result=result,
            jd_text=jd_text,
            output_dir=output_dir,
            provider_override=provider_override,
            cl_preset=cl_preset,
            app_dir=app_dir,
        )


def _merge_pipeline_results(
    first: PipelineResult,
    second: PipelineResult,
) -> PipelineResult:
    """Merge results from a split pipeline run (stages 1-3 + stages 4-5).

    Combines stage metadata from both runs and takes final output paths
    and scores from the second run (which has stages 4-5).
    """
    merged_stages = list(first.stages) + list(second.stages)
    total_duration = first.total_duration_seconds + second.total_duration_seconds
    total_cost = sum(s.cost_usd for s in merged_stages)

    return second.model_copy(
        update={
            "stages": merged_stages,
            "total_duration_seconds": total_duration,
            "total_cost_usd": total_cost,
        },
    )


def _write_run_metadata(
    *,
    output_dir: Path,
    result: PipelineResult,
    preset_name: str,
    provider_override: str | None,
) -> None:
    """Write run-metadata.json in the output directory.

    Records the preset, provider, model, score, cost, and duration
    for traceability and later inspection.

    Args:
        output_dir: Directory where the pipeline output was written.
        result: PipelineResult from the completed pipeline run.
        preset_name: The preset name used for this run.
        provider_override: Provider override if used, or None.
    """
    if not result.stages:
        return

    # Use the first stage's provider/model as representative
    first_stage = result.stages[0]
    provider = provider_override or first_stage.provider
    model = first_stage.model

    metadata = RunMetadata(
        preset=preset_name,
        provider=provider,
        model=model,
        timestamp=datetime.now(tz=UTC),
        duration_seconds=result.total_duration_seconds,
        review_score=result.review_score,
        total_cost_usd=result.total_cost_usd,
    )

    mkcv_dir = output_dir / ".mkcv"
    mkcv_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = mkcv_dir / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    logger.debug("Wrote run metadata: %s", metadata_path)


def _display_kb_validation(result: KBValidationResult) -> None:
    """Display KB validation results — warnings in yellow, errors in red."""
    if result.is_valid and not result.warnings:
        return

    for error in result.errors:
        console.print(f"  [red]Error:[/red] {error}")

    for warning in result.warnings:
        console.print(f"  [yellow]Warning:[/yellow] {warning}")

    if not result.is_valid:
        console.print(
            "\n  [red]Knowledge base validation failed. "
            "Fix errors above before generating.[/red]"
        )
    console.print()


def _display_pipeline_summary(result: PipelineResult) -> None:
    """Display a summary of pipeline stage results."""
    for stage in result.stages:
        summary = _stage_summary(stage.stage_number, stage.stage_name, result)
        model_short = stage.model.split("/")[-1]  # strip provider prefix
        cost_str = f"${stage.cost_usd:.4f}" if stage.cost_usd > 0 else "free"
        console.print(
            f"  [green]\u2713[/green] Stage {stage.stage_number}: "
            f"{summary} [dim]({stage.duration_seconds:.1f}s, "
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


def _stage_summary(
    stage_number: int,
    stage_name: str,
    result: PipelineResult,
) -> str:
    """Build a human-readable summary string for a pipeline stage."""
    if stage_number == 1:
        return f"Analyzed JD — {result.company}, {result.role_title}"
    if stage_number == 2:
        return f"Selected experience ({stage_name})"
    if stage_number == 3:
        return f"Tailored content ({stage_name})"
    if stage_number == 4:
        return "Structured resume.yaml"
    if stage_number == 5:
        return f"Review score: {result.review_score}/100"
    return stage_name


def _auto_render(
    result: PipelineResult,
    output_dir: Path,
    *,
    theme: str,
) -> tuple[bool, str | None]:
    """Attempt to render the resume YAML to PDF.

    Returns:
        Tuple of (success, pdf_path_string).
    """
    yaml_path_str = result.output_paths.get("resume_yaml")
    if not yaml_path_str:
        console.print(
            "  [yellow]\u26a0[/yellow] No resume.yaml found; skipping render."
        )
        return False, None

    yaml_path = Path(yaml_path_str)
    if not yaml_path.is_file():
        console.print(
            f"  [yellow]\u26a0[/yellow] resume.yaml not found at {yaml_path}; "
            "skipping render."
        )
        return False, None

    try:
        render_service = create_render_service(settings)
        rendered = render_service.render_resume(yaml_path, output_dir, theme=theme)
        console.print(
            f"  [green]\u2713[/green] Rendered \u2192 {rendered.pdf_path.name}"
        )
        return True, str(rendered.pdf_path)
    except Exception as exc:
        console.print(f"  [yellow]\u26a0[/yellow] Render failed: {exc}")
        logger.warning("Auto-render failed", exc_info=True)
        return False, None


def _display_output_tree(
    result: PipelineResult,
    output_dir: Path,
    *,
    pdf_rendered: bool,
    pdf_path: str | None,
) -> None:
    """Display a tree of output files."""
    console.print()
    console.print(f"  Output: {output_dir}/")

    yaml_path = result.output_paths.get("resume_yaml")
    if yaml_path:
        connector = "\u251c\u2500\u2500" if pdf_rendered else "\u2514\u2500\u2500"
        console.print(f"  {connector} resume.yaml")
    if pdf_rendered and pdf_path:
        pdf_name = Path(pdf_path).name
        console.print(f"  \u2514\u2500\u2500 {pdf_name}")

    console.print()


# ------------------------------------------------------------------
# Cover letter chaining
# ------------------------------------------------------------------


def _chain_cover_letter(
    *,
    result: PipelineResult,
    jd_text: str,
    output_dir: Path,
    provider_override: str | None,
    cl_preset: str,
    app_dir: Path | None = None,
) -> None:
    """Chain cover letter generation after a successful resume pipeline."""
    console.print()
    console.print("  [bold]Chaining cover letter...[/bold]")

    # Read the generated resume
    yaml_path_str = result.output_paths.get("resume_yaml")
    if not yaml_path_str:
        console.print(
            "  [yellow]\u26a0[/yellow] No resume.yaml produced — skipping cover letter."
        )
        return

    yaml_path = Path(yaml_path_str)
    if not yaml_path.is_file():
        console.print(
            "  [yellow]\u26a0[/yellow] resume.yaml not found — skipping cover letter."
        )
        return

    resume_text = yaml_path.read_text(encoding="utf-8")

    # Create versioned cover-letter output directory if in workspace mode
    cl_output_dir = output_dir
    if app_dir is not None:
        workspace_service = create_workspace_service()
        cl_version_dir = workspace_service.create_output_version(
            app_dir, "cover-letter"
        )
        cl_output_dir = cl_version_dir
        console.print(
            f"  [green]\u2713[/green] Output version: "
            f"cover-letter/{cl_version_dir.name}"
        )

    try:
        cl_service = create_cover_letter_service(
            settings, provider_override=provider_override
        )
    except MkcvError as exc:
        console.print(f"  [yellow]\u26a0[/yellow] Cover letter setup failed: {exc}")
        return

    try:
        cl_result = asyncio.run(
            cl_service.generate(
                jd_text,
                resume_text=resume_text,
                output_dir=cl_output_dir,
                company=result.company,
                role_title=result.role_title,
            )
        )
    except MkcvError as exc:
        console.print(
            f"  [yellow]\u26a0[/yellow] Cover letter generation failed: {exc}"
        )
        return

    # Display CL results
    for stage in cl_result.stages:
        model_short = stage.model.split("/")[-1]
        cost_str = f"${stage.cost_usd:.4f}" if stage.cost_usd > 0 else "free"
        console.print(
            f"  [green]\u2713[/green] CL: {stage.stage_name} "
            f"[dim]({stage.duration_seconds:.1f}s, "
            f"{model_short}, {cost_str})[/dim]"
        )

    console.print(f"  Cover letter score: [bold]{cl_result.review_score}[/bold]/100")

    for path_str in cl_result.output_paths.values():
        name = Path(path_str).name
        console.print(f"  \u2514\u2500\u2500 {name}")

    console.print()


# ------------------------------------------------------------------
# Progress spinner callback
# ------------------------------------------------------------------


class _ProgressCallback:
    """Stage callback that shows a rich spinner during each stage.

    Displays a spinning indicator while a stage is running, then
    prints a completion line with duration when the stage finishes.
    """

    def __init__(self, target_console: Console) -> None:
        self._console = target_console
        self._status: Status | None = None
        self._stage_start: float = 0.0

    def on_stage_start(self, stage_number: int) -> None:
        """Start the spinner for the given stage."""
        label = _STAGE_LABELS.get(stage_number, f"Stage {stage_number}")
        self._stage_start = time.monotonic()
        self._status = self._console.status(
            f"  Stage {stage_number}/5: {label}...",
            spinner="dots",
        )
        self._status.start()

    def on_stage_complete(
        self,
        stage_number: int,
        stage_name: str,
        metadata: StageMetadata,
    ) -> bool:
        """Stop the spinner and print completion for the stage."""
        if self._status is not None:
            self._status.stop()
            self._status = None

        label = _STAGE_LABELS.get(stage_number, stage_name)
        duration = metadata.duration_seconds
        self._console.print(
            f"  [green]\u2713[/green] Stage {stage_number}/5: {label} ({duration:.1f}s)"
        )
        return True


# ------------------------------------------------------------------
# Callback that stops the pipeline after a given stage
# ------------------------------------------------------------------


class _StopAfterStageCallback:
    """Stage callback that shows spinners and stops after a specified stage.

    Used for the interactive flow: runs stages 1-N with progress spinners,
    then returns ``False`` after stage N to hand control to
    ``InteractiveSession``.
    """

    def __init__(self, target_console: Console, *, stop_after: int) -> None:
        self._console = target_console
        self._stop_after = stop_after
        self._status: Status | None = None
        self._stage_start: float = 0.0

    def on_stage_start(self, stage_number: int) -> None:
        """Start the spinner for the given stage."""
        label = _STAGE_LABELS.get(stage_number, f"Stage {stage_number}")
        self._stage_start = time.monotonic()
        self._status = self._console.status(
            f"  Stage {stage_number}/5: {label}...",
            spinner="dots",
        )
        self._status.start()

    def on_stage_complete(
        self,
        stage_number: int,
        stage_name: str,
        metadata: StageMetadata,
    ) -> bool:
        """Stop the spinner and halt after the target stage."""
        if self._status is not None:
            self._status.stop()
            self._status = None

        label = _STAGE_LABELS.get(stage_number, stage_name)
        duration = metadata.duration_seconds
        self._console.print(
            f"  [green]\u2713[/green] Stage {stage_number}/5: {label} ({duration:.1f}s)"
        )

        # Continue only if we haven't reached the stop stage
        return stage_number < self._stop_after
