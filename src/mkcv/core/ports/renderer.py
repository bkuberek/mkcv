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
        theme: str,
        formats: list[str] | None = None,
        yaml_content: str | None = None,
    ) -> RenderedOutput:
        """Render a resume YAML file to PDF and other formats.

        Args:
            yaml_path: Path to the RenderCV-compatible YAML file.
            output_dir: Directory for rendered output files.
            theme: RenderCV theme name.
            formats: Output formats to generate (e.g. ["pdf", "png"]).
                When None, all supported formats are generated.
            yaml_content: Pre-processed YAML content to render instead
                of reading from yaml_path. When provided, yaml_path is
                still used for path resolution but its content is ignored.
        """
        ...
