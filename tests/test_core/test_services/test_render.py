"""Tests for RenderService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mkcv.core.exceptions.render import RenderError
from mkcv.core.ports.renderer import RenderedOutput
from mkcv.core.services.render import RenderService


@pytest.fixture
def mock_renderer() -> MagicMock:
    """Create a mock renderer implementing RendererPort."""
    renderer = MagicMock()
    renderer.render.return_value = RenderedOutput(
        pdf_path=Path("/tmp/output/resume.pdf"),
        png_path=Path("/tmp/output/resume.png"),
        md_path=Path("/tmp/output/resume.md"),
        html_path=Path("/tmp/output/resume.html"),
    )
    return renderer


@pytest.fixture
def service(mock_renderer: MagicMock) -> RenderService:
    """Create a RenderService with a mock renderer."""
    return RenderService(renderer=mock_renderer)


class TestRenderServiceDelegation:
    """Tests that RenderService delegates to the renderer."""

    def test_render_resume_delegates_to_renderer(
        self,
        service: RenderService,
        mock_renderer: MagicMock,
    ) -> None:
        yaml_path = Path("/tmp/resume.yaml")
        output_dir = Path("/tmp/output")

        service.render_resume(yaml_path, output_dir, theme="sb2nov")

        mock_renderer.render.assert_called_once_with(
            yaml_path, output_dir, theme="sb2nov", formats=None, yaml_content=None
        )

    def test_render_resume_passes_theme(
        self,
        service: RenderService,
        mock_renderer: MagicMock,
    ) -> None:
        yaml_path = Path("/tmp/resume.yaml")
        output_dir = Path("/tmp/output")

        service.render_resume(yaml_path, output_dir, theme="classic")

        mock_renderer.render.assert_called_once_with(
            yaml_path, output_dir, theme="classic", formats=None, yaml_content=None
        )

    def test_render_resume_passes_formats(
        self,
        service: RenderService,
        mock_renderer: MagicMock,
    ) -> None:
        yaml_path = Path("/tmp/resume.yaml")
        output_dir = Path("/tmp/output")

        service.render_resume(
            yaml_path, output_dir, theme="sb2nov", formats=["pdf", "png"]
        )

        mock_renderer.render.assert_called_once_with(
            yaml_path,
            output_dir,
            theme="sb2nov",
            formats=["pdf", "png"],
            yaml_content=None,
        )

    def test_render_resume_passes_yaml_content(
        self,
        service: RenderService,
        mock_renderer: MagicMock,
    ) -> None:
        yaml_path = Path("/tmp/resume.yaml")
        output_dir = Path("/tmp/output")
        content = "cv:\n  name: Test\ndesign:\n  theme: sb2nov\n"

        service.render_resume(
            yaml_path,
            output_dir,
            theme="sb2nov",
            yaml_content=content,
        )

        mock_renderer.render.assert_called_once_with(
            yaml_path,
            output_dir,
            theme="sb2nov",
            formats=None,
            yaml_content=content,
        )

    def test_render_resume_returns_rendered_output(
        self,
        service: RenderService,
    ) -> None:
        yaml_path = Path("/tmp/resume.yaml")
        output_dir = Path("/tmp/output")

        result = service.render_resume(yaml_path, output_dir, theme="sb2nov")

        assert isinstance(result, RenderedOutput)
        assert result.pdf_path == Path("/tmp/output/resume.pdf")

    def test_render_resume_propagates_render_error(
        self,
        mock_renderer: MagicMock,
    ) -> None:
        mock_renderer.render.side_effect = RenderError("render failed")
        service = RenderService(renderer=mock_renderer)

        with pytest.raises(RenderError, match="render failed"):
            service.render_resume(
                Path("/tmp/resume.yaml"), Path("/tmp/output"), theme="sb2nov"
            )
