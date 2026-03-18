"""Stub renderer adapter for development and testing."""

from pathlib import Path

from mkcv.core.ports.renderer import RenderedOutput


class StubRenderer:
    """Stub renderer that raises NotImplementedError.

    Used as a placeholder until real renderer adapters
    (RenderCV, WeasyPrint) are implemented.

    Implements: RendererPort
    """

    def render(
        self,
        yaml_path: Path,
        output_dir: Path,
        *,
        theme: str = "sb2nov",
    ) -> RenderedOutput:
        """Not implemented — raises NotImplementedError."""
        raise NotImplementedError(
            "Resume rendering not yet implemented. "
            "RenderCV and WeasyPrint adapters coming soon."
        )
