"""mkcv kb — generate or update a career knowledge base from documents."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_kb_generation_service
from mkcv.config import settings
from mkcv.core.exceptions import MkcvError
from mkcv.core.models.kb_generation_result import KBGenerationResult

logger = logging.getLogger(__name__)

console = Console(stderr=True)
output_console = Console()

kb_app = cyclopts.App(
    name="kb",
    help="Generate or update a career knowledge base from source documents.",
)


@kb_app.command(name="generate")
def kb_generate_command(
    sources: Annotated[
        list[Path],
        cyclopts.Parameter(
            help=(
                "Source file(s) or directory paths containing career documents "
                "(PDF, Markdown, DOCX, HTML, TXT)."
            ),
        ),
    ],
    *,
    output: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--output", "-o"],
            help="Output path for the generated knowledge base file.",
        ),
    ] = None,
    name: Annotated[
        str,
        cyclopts.Parameter(
            name=["--name", "-n"],
            help="KB name used in the title heading.",
        ),
    ] = "Career",
    glob: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--glob", "-g"],
            help="Glob pattern to filter files when scanning directories.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--model", "-m"],
            help="Override the LLM model for KB generation.",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        cyclopts.Parameter(
            help=("Override AI provider (anthropic/openai/openrouter/ollama)."),
        ),
    ] = None,
) -> None:
    """Generate a knowledge base from source documents.

    Reads career documents (PDF, Markdown, DOCX, HTML, TXT) from the
    given sources and uses an LLM to synthesise a structured Markdown
    knowledge base suitable for resume generation.

    Sources can be individual files or directories.  When a directory is
    given, all supported files are discovered recursively (use --glob to
    filter).

    Examples:
      mkcv kb generate resume.pdf
      mkcv kb generate docs/ --output kb.md --name "Engineering"
      mkcv kb generate resume.pdf linkedin.html --glob "*.pdf"
    """
    # Resolve output path: default to workspace KB path or career-kb.md
    resolved_output = _resolve_output(output)

    # Display header
    console.print()
    console.print("  [bold]mkcv kb generate[/bold]")
    console.print(f"  Sources: {', '.join(str(s) for s in sources)}")
    console.print(f"  Name:    {name}")
    if glob:
        console.print(f"  Glob:    {glob}")
    console.print(f"  Output:  {resolved_output}")
    console.print()

    # Create and run the service
    try:
        service = create_kb_generation_service(
            settings,
            provider_override=provider,
            model_override=model,
        )
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    with console.status("  Generating knowledge base..."):
        try:
            result = asyncio.run(
                service.generate(
                    sources=sources,
                    output=resolved_output,
                    kb_name=name,
                    glob=glob,
                )
            )
        except MkcvError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            sys.exit(exc.exit_code)

    # Display results
    _display_generate_result(result)


@kb_app.command(name="update")
def kb_update_command(
    sources: Annotated[
        list[Path],
        cyclopts.Parameter(
            help=(
                "New source file(s) or directory paths to merge into "
                "the existing knowledge base."
            ),
        ),
    ],
    *,
    kb: Annotated[
        Path | None,
        cyclopts.Parameter(
            help=(
                "Path to existing knowledge base to update. "
                "Defaults to the workspace KB path."
            ),
        ),
    ] = None,
    glob: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--glob", "-g"],
            help="Glob pattern to filter files when scanning directories.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--model", "-m"],
            help="Override the LLM model for KB generation.",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        cyclopts.Parameter(
            help=("Override AI provider (anthropic/openai/openrouter/ollama)."),
        ),
    ] = None,
) -> None:
    """Update an existing knowledge base with new source documents.

    Reads new career documents and merges them into an existing knowledge
    base, preserving the existing structure while integrating new content.

    If --kb is not specified, the workspace knowledge base path is used.

    Examples:
      mkcv kb update new-cert.pdf
      mkcv kb update promotion-docs/ --kb my-kb.md
      mkcv kb update new-role.md --glob "*.md"
    """
    # Resolve existing KB path
    resolved_kb = _resolve_existing_kb(kb)

    if resolved_kb is None:
        console.print(
            "[red]Error:[/red] No existing knowledge base found. "
            "Use --kb to specify the path, or run 'mkcv kb generate' first."
        )
        sys.exit(2)

    if not resolved_kb.is_file():
        console.print(f"[red]Error:[/red] Knowledge base not found: {resolved_kb}")
        sys.exit(2)

    # Display header
    console.print()
    console.print("  [bold]mkcv kb update[/bold]")
    console.print(f"  KB:      {resolved_kb}")
    console.print(f"  Sources: {', '.join(str(s) for s in sources)}")
    if glob:
        console.print(f"  Glob:    {glob}")
    console.print()

    # Create and run the service
    try:
        service = create_kb_generation_service(
            settings,
            provider_override=provider,
            model_override=model,
        )
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)

    with console.status("  Updating knowledge base..."):
        try:
            result = asyncio.run(
                service.update(
                    existing_kb_path=resolved_kb,
                    sources=sources,
                    glob=glob,
                )
            )
        except MkcvError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            sys.exit(exc.exit_code)

    # Display results
    _display_update_result(result)


# ------------------------------------------------------------------
# Path resolution helpers
# ------------------------------------------------------------------


def _resolve_output(output: Path | None) -> Path:
    """Resolve the output path for a generated knowledge base.

    When no explicit output is given, uses the workspace KB path
    (if in a workspace) or defaults to ``career-kb.md`` in the
    current directory.

    Args:
        output: Explicit output path, or None.

    Returns:
        Resolved output path.
    """
    if output is not None:
        return output

    if settings.in_workspace and settings.workspace_root:
        kb_relative: str = settings.workspace.knowledge_base
        return Path(settings.workspace_root / kb_relative)

    return Path.cwd() / "career-kb.md"


def _resolve_existing_kb(kb: Path | None) -> Path | None:
    """Resolve the path to an existing knowledge base.

    When no explicit path is given, tries the workspace KB path.

    Args:
        kb: Explicit KB path, or None.

    Returns:
        Resolved path, or None if no KB can be found.
    """
    if kb is not None:
        return kb

    if settings.in_workspace and settings.workspace_root:
        kb_relative: str = settings.workspace.knowledge_base
        candidate = Path(settings.workspace_root / kb_relative)
        if candidate.is_file():
            return candidate

    return None


# ------------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------------


def _display_generate_result(
    result: KBGenerationResult,
) -> None:
    """Display knowledge base generation results."""
    doc_count = len(result.source_documents)
    total_chars = sum(d.char_count for d in result.source_documents)
    kb_chars = len(result.kb_text)

    console.print(
        f"  [green]Done.[/green] "
        f"Read {doc_count} document(s) ({total_chars:,} chars) "
        f"-> KB ({kb_chars:,} chars)"
    )

    if result.output_path is not None:
        console.print(f"  Output: {result.output_path}")

    if result.validation_warnings:
        console.print()
        for warning in result.validation_warnings:
            console.print(f"  [yellow]Warning:[/yellow] {warning}")

    console.print()


def _display_update_result(
    result: KBGenerationResult,
) -> None:
    """Display knowledge base update results."""
    doc_count = len(result.source_documents)
    kb_chars = len(result.kb_text)

    console.print(
        f"  [green]Done.[/green] "
        f"Merged {doc_count} new document(s) -> KB ({kb_chars:,} chars)"
    )

    if result.output_path is not None:
        console.print(f"  Output: {result.output_path}")

    if result.validation_warnings:
        console.print()
        for warning in result.validation_warnings:
            console.print(f"  [yellow]Warning:[/yellow] {warning}")

    console.print()
