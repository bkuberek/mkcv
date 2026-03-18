"""Port interface for resume PDF rendering."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class RenderedOutput(BaseModel):
    """Result of a rendering operation."""

    pdf_path: Path
    png_path: Path | None = None
    md_path: Path | None = None
    html_path: Path | None = None


@runtime_checkable
class RendererPort(Protocol):
    """Interface for resume rendering backends.

    Implementations: RenderCVRenderer, WeasyPrintRenderer.
    """

    def render(
        self,
        yaml_path: Path,
        output_dir: Path,
        *,
        theme: str = "sb2nov",
    ) -> RenderedOutput:
        """Render a resume YAML file to PDF and other formats."""
        ...
