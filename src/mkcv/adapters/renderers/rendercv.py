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
            "rendercv is not installed. Install with: "
            'uv add "rendercv[full]"'
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
    ) -> RenderedOutput:
        """Render a resume YAML file to PDF and other formats.

        Args:
            yaml_path: Path to the RenderCV-compatible YAML file.
            output_dir: Directory for rendered output files.
            theme: RenderCV theme name (ignored if design is in YAML).

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

        resolved_yaml = yaml_path.resolve()
        if not resolved_yaml.is_file():
            raise RenderError(f"YAML file not found: {resolved_yaml}")

        logger.info("Rendering %s with RenderCV", resolved_yaml.name)

        try:
            main_yaml = resolved_yaml.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(
                f"Failed to read YAML file: {resolved_yaml}"
            ) from exc

        try:
            _, rendercv_model = build_rendercv_dictionary_and_model(
                main_yaml,
                input_file_path=resolved_yaml,
                output_folder=str(output_dir),
            )
        except Exception as exc:
            raise RenderError(
                f"Invalid RenderCV YAML: {exc}"
            ) from exc

        try:
            typst_path = generate_typst(rendercv_model)
        except Exception as exc:
            raise RenderError(
                f"Typst generation failed: {exc}"
            ) from exc

        try:
            pdf_result = generate_pdf(rendercv_model, typst_path)
        except Exception as exc:
            raise RenderError(
                f"PDF generation failed: {exc}"
            ) from exc

        if pdf_result is None:
            raise RenderError(
                "PDF generation returned no output. "
                "Check that the YAML file is valid."
            )

        pdf_path = Path(pdf_result)

        # Generate optional outputs — failures here are non-fatal
        png_path = _generate_png_safe(rendercv_model, typst_path)
        md_path = _generate_markdown_safe(rendercv_model)
        html_path = _generate_html_safe(rendercv_model, md_path)

        logger.info("Rendered PDF: %s", pdf_path)

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
