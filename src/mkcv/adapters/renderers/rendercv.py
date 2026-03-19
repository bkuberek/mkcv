"""RenderCV adapter for PDF resume rendering."""

import importlib.util
import logging
from pathlib import Path

from mkcv.core.exceptions.render import RenderError
from mkcv.core.ports.renderer import RenderedOutput

logger = logging.getLogger(__name__)


def _ensure_rendercv_installed() -> None:
    """Verify rendercv is importable, raising RenderError if not."""
    if importlib.util.find_spec("rendercv") is None:
        raise RenderError(
            'rendercv is not installed. Install with: uv add "rendercv[full]"'
        )


class RenderCVAdapter:
    """Renders resume YAML to PDF using RenderCV's Python API.

    Uses rendercv's internal functions to parse the YAML model,
    generate Typst source, compile to PDF/PNG, and produce
    Markdown/HTML outputs.

    Implements: RendererPort
    """

    def render(
        self,
        yaml_path: Path,
        output_dir: Path,
        *,
        theme: str = "sb2nov",
        formats: list[str] | None = None,
    ) -> RenderedOutput:
        """Render a resume YAML file to the requested formats.

        Args:
            yaml_path: Path to the RenderCV-compatible YAML file.
            output_dir: Directory for rendered output files.
            theme: RenderCV theme name (ignored if design is in YAML).
            formats: Output formats to generate (e.g. ["pdf", "png"]).
                When None, all supported formats are generated.

        Returns:
            RenderedOutput with paths to generated files.

        Raises:
            RenderError: If the YAML is invalid, rendering fails, or
                rendercv is not installed.
        """
        _ensure_rendercv_installed()

        from rendercv.renderer.pdf_png import generate_pdf
        from rendercv.renderer.typst import generate_typst
        from rendercv.schema.rendercv_model_builder import (
            build_rendercv_dictionary_and_model,
        )

        requested = _normalize_formats(formats)

        resolved_yaml = yaml_path.resolve()
        if not resolved_yaml.is_file():
            raise RenderError(f"YAML file not found: {resolved_yaml}")

        logger.info("Rendering %s with RenderCV", resolved_yaml.name)

        try:
            main_yaml = resolved_yaml.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(f"Failed to read YAML file: {resolved_yaml}") from exc

        try:
            _, rendercv_model = build_rendercv_dictionary_and_model(
                main_yaml,
                input_file_path=resolved_yaml,
                output_folder=str(output_dir),
            )
        except Exception as exc:
            raise RenderError(f"Invalid RenderCV YAML: {exc}") from exc

        try:
            typst_path = generate_typst(rendercv_model)
        except Exception as exc:
            raise RenderError(f"Typst generation failed: {exc}") from exc

        # PDF is always generated — RenderCV requires it for PNG
        try:
            pdf_result = generate_pdf(rendercv_model, typst_path)
        except Exception as exc:
            raise RenderError(f"PDF generation failed: {exc}") from exc

        if pdf_result is None:
            raise RenderError(
                "PDF generation returned no output. Check that the YAML file is valid."
            )

        pdf_path = Path(pdf_result)

        # Generate optional outputs only when requested
        png_path: Path | None = None
        md_path: Path | None = None
        html_path: Path | None = None

        if "png" in requested:
            png_path = _generate_png_safe(rendercv_model, typst_path)

        if "md" in requested or "html" in requested:
            md_path = _generate_markdown_safe(rendercv_model)

        if "html" in requested:
            html_path = _generate_html_safe(rendercv_model, md_path)

        # If md was only generated as an intermediate for html, clear it
        if "md" not in requested:
            md_path = None

        # If pdf was not requested, remove the file and clear the path.
        # RenderCV always produces a PDF (needed for PNG), so we delete
        # the unwanted artifact after generation.
        if "pdf" not in requested:
            _remove_file_safe(pdf_path)
            # RenderedOutput requires pdf_path; keep the path but the
            # file won't exist on disk.

        logger.info("Rendered formats: %s", requested)

        return RenderedOutput(
            pdf_path=pdf_path,
            png_path=png_path,
            md_path=md_path,
            html_path=html_path,
        )


def _generate_png_safe(
    rendercv_model: object,
    typst_path: Path | None,
) -> Path | None:
    """Generate PNG, returning None on failure."""
    try:
        from rendercv.renderer.pdf_png import generate_png

        result = generate_png(rendercv_model, typst_path)
        if result:
            # generate_png returns a list of paths (one per page)
            return Path(result[0])
    except Exception:
        logger.warning("PNG generation failed; skipping", exc_info=True)
    return None


def _generate_markdown_safe(
    rendercv_model: object,
) -> Path | None:
    """Generate Markdown, returning None on failure."""
    try:
        from rendercv.renderer.markdown import generate_markdown

        result = generate_markdown(rendercv_model)
        if result:
            return Path(result)
    except Exception:
        logger.warning("Markdown generation failed; skipping", exc_info=True)
    return None


def _generate_html_safe(
    rendercv_model: object,
    md_path: Path | None,
) -> Path | None:
    """Generate HTML from Markdown, returning None on failure."""
    try:
        from rendercv.renderer.html import generate_html

        result = generate_html(rendercv_model, md_path)
        if result:
            return Path(result)
    except Exception:
        logger.warning("HTML generation failed; skipping", exc_info=True)
    return None


ALL_FORMATS = frozenset({"pdf", "png", "md", "html"})


def _normalize_formats(formats: list[str] | None) -> frozenset[str]:
    """Normalize and validate the requested output formats.

    Args:
        formats: List of format strings, or None for all formats.

    Returns:
        Frozenset of lowercase format names.

    Raises:
        RenderError: If any format name is unrecognized.
    """
    if formats is None:
        return ALL_FORMATS

    normalized = frozenset(f.lower().strip() for f in formats)
    unknown = normalized - ALL_FORMATS
    if unknown:
        raise RenderError(
            f"Unknown output format(s): {', '.join(sorted(unknown))}. "
            f"Supported: {', '.join(sorted(ALL_FORMATS))}"
        )
    return normalized


def _remove_file_safe(path: Path) -> None:
    """Remove a file, logging a warning on failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to remove %s", path, exc_info=True)
