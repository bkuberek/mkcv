"""Resume rendering service."""

from pathlib import Path

from mkcv.core.ports.renderer import RenderedOutput, RendererPort


class RenderService:
    """Renders resume YAML to PDF and other formats."""

    def __init__(self, renderer: RendererPort) -> None:
        self._renderer = renderer

    def render_resume(
        self,
        yaml_path: Path,
        output_dir: Path,
        *,
        theme: str = "sb2nov",
    ) -> RenderedOutput:
        """Render a resume YAML file to PDF.

        Args:
            yaml_path: Path to the RenderCV YAML file.
            output_dir: Directory for rendered output files.
            theme: RenderCV theme name.

        Returns:
            RenderedOutput with paths to generated files.
        """
        return self._renderer.render(yaml_path, output_dir, theme=theme)
