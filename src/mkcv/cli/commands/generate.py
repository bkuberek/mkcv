"""mkcv generate — run the AI pipeline to generate a tailored resume."""

import asyncio
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts
from rich.console import Console
from rich.prompt import Confirm

if TYPE_CHECKING:
    from rich.status import Status

from mkcv.adapters.factory import (
    create_pipeline_service,
    create_render_service,
    create_workspace_service,
)
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError
from mkcv.core.models.kb_validation import KBValidationResult
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.services.jd_reader import read_jd
from mkcv.core.services.kb_validator import validate_kb

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
            help="Pause after each stage for review.",
        ),
    ] = False,
) -> None:
    """Generate a tailored resume from a job description and knowledge base.

    Runs the AI pipeline: analyze JD, select experience, tailor content,
    structure YAML, and review.

    The --jd option accepts a file path, an HTTP/HTTPS URL, or "-" to
    read from stdin. Omit --jd to generate a generic resume (optionally
    with --target to specify the role).
    """
    # ---- Resolve preset from --preset / --profile ----
    resolved_preset, resolved_provider = _resolve_preset_and_provider(
        preset_raw=preset, profile=profile, provider=provider
    )

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
    use_workspace_mode = (
        settings.in_workspace and not is_generic and company and position
    )

    if use_workspace_mode:
        _generate_workspace_mode(
            jd_text=jd_text,
            jd_display=jd_display,
            kb=kb,
            company=company,
            position=position,
            output_dir=output_dir,
            theme=theme,
            preset=resolved_preset,
            provider=resolved_provider,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
        )
    elif settings.in_workspace and not is_generic and (not company or not position):
        # Targeted resume in workspace but missing company/position
        console.print(
            "[red]Error:[/red] --company and --position are required "
            "when using --jd in a workspace.\n"
            "  For a generic resume, omit --jd."
        )
        sys.exit(2)
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
            theme=theme,
            preset=resolved_preset,
            provider=resolved_provider,
            from_stage=from_stage,
            render_pdf=render,
            interactive=interactive,
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
        jd_text = read_jd(source)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

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

    # Use application dir as output if not specified
    run_dir = output_dir or app_dir

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
    theme: str = "sb2nov",
    interactive: bool = False,
) -> None:
    """Execute the AI pipeline, display results, and optionally render PDF."""
    # ---- Validate KB before running pipeline ----
    kb_content = kb.read_text(encoding="utf-8")
    kb_result = validate_kb(kb_content)
    _display_kb_validation(kb_result)
    if not kb_result.is_valid:
        sys.exit(5)

    pipeline = create_pipeline_service(
        settings, preset_name=preset_name, provider_override=provider_override
    )

    if interactive:
        callback: _ProgressCallback | _InteractiveProgressCallback = (
            _InteractiveProgressCallback(console)
        )
    else:
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
            )
        )
    except MkcvError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

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
# Interactive mode callback with spinner
# ------------------------------------------------------------------


class _InteractiveProgressCallback:
    """Stage callback for interactive mode with a spinner.

    Shows a spinner while each stage runs, displays results,
    and prompts the user to continue or stop.
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
        """Stop the spinner, display result, and ask to continue."""
        if self._status is not None:
            self._status.stop()
            self._status = None

        label = _STAGE_LABELS.get(stage_number, stage_name)
        duration = metadata.duration_seconds
        self._console.print(
            f"  [green]\u2713[/green] Stage {stage_number}/5: "
            f"{label} ({duration:.1f}s, model={metadata.model})"
        )

        # Don't prompt after the last stage
        if stage_number >= 5:
            return True

        self._console.print()
        return Confirm.ask(
            "  Continue to next stage?",
            default=True,
            console=self._console,
        )
