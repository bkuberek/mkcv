"""Typst adapter for cover letter PDF rendering."""

import importlib.resources
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.ports.cover_letter_renderer import CoverLetterRenderedOutput

logger = logging.getLogger(__name__)


class TypstCoverLetterRenderer:
    """Renders cover letters to PDF using Typst compilation.

    Uses a Jinja2 template to produce Typst markup, then compiles
    it to PDF with the ``typst`` Python package.

    Implements: CoverLetterRendererPort
    """

    def render(
        self,
        cover_letter: CoverLetter,
        output_dir: Path,
        *,
        theme: str = "professional",
    ) -> CoverLetterRenderedOutput:
        """Render a cover letter to PDF.

        Args:
            cover_letter: Structured cover letter content.
            output_dir: Directory for rendered output files.
            theme: Template theme name (reserved for future use).

        Returns:
            CoverLetterRenderedOutput with paths to generated files.

        Raises:
            RenderError: If Typst compilation fails or typst is not installed.
        """
        try:
            import typst
        except ImportError as exc:
            raise RenderError(
                "typst Python package is not installed. Install with: uv add typst"
            ) from exc

        output_dir.mkdir(parents=True, exist_ok=True)

        # Render the Jinja2 template to Typst source
        typst_source = self._render_template(cover_letter, theme=theme)

        # Write .typ source for debugging/inspection
        typ_path = output_dir / "cover_letter.typ"
        typ_path.write_text(typst_source, encoding="utf-8")
        logger.debug("Wrote Typst source: %s", typ_path)

        # Compile Typst → PDF
        pdf_path = output_dir / "cover_letter.pdf"
        try:
            pdf_bytes = typst.compile(typst_source)
            pdf_path.write_bytes(pdf_bytes)
        except Exception as exc:
            raise RenderError(f"Typst compilation failed: {exc}") from exc

        logger.info("Rendered cover letter PDF: %s", pdf_path)

        return CoverLetterRenderedOutput(pdf_path=pdf_path)

    def _render_template(
        self,
        cover_letter: CoverLetter,
        *,
        theme: str,
    ) -> str:
        """Render the Jinja2 Typst template with cover letter data."""
        templates_dir = self._templates_dir()

        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
            keep_trailing_newline=True,
        )
        template = env.get_template("cover_letter.typ.j2")

        return template.render(
            salutation=cover_letter.salutation,
            opening_paragraph=cover_letter.opening_paragraph,
            body_paragraphs=cover_letter.body_paragraphs,
            closing_paragraph=cover_letter.closing_paragraph,
            sign_off=cover_letter.sign_off,
            candidate_name=cover_letter.candidate_name,
            company=cover_letter.company,
            role_title=cover_letter.role_title,
            theme=theme,
        )

    @staticmethod
    def _templates_dir() -> Path:
        """Locate the bundled templates directory."""
        # Use importlib.resources for package-relative path
        templates_ref = importlib.resources.files("mkcv") / "templates"
        # Traverse to get a concrete Path
        with importlib.resources.as_file(templates_ref) as templates_path:
            return Path(templates_path)
