"""Port interface for cover letter PDF rendering."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from mkcv.core.models.cover_letter import CoverLetter


class CoverLetterRenderedOutput(BaseModel):
    """Result of a cover letter rendering operation."""

    pdf_path: Path
    md_path: Path | None = None
    txt_path: Path | None = None


@runtime_checkable
class CoverLetterRendererPort(Protocol):
    """Interface for cover letter rendering backends."""

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
            theme: Template theme name for future extensibility.

        Returns:
            CoverLetterRenderedOutput with paths to generated files.
        """
        ...
