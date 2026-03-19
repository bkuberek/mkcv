"""Tests for RenderCVAdapter."""

import textwrap
from pathlib import Path

import pytest

from mkcv.adapters.renderers.rendercv import RenderCVAdapter
from mkcv.core.exceptions.render import RenderError
from mkcv.core.ports.renderer import RenderedOutput, RendererPort

# Minimal valid RenderCV YAML — produces a one-page PDF.
MINIMAL_YAML = textwrap.dedent("""\
    cv:
      name: Test User
      sections:
        summary:
          - Software engineer with testing experience.
    design:
      theme: classic
""")


@pytest.fixture
def adapter() -> RenderCVAdapter:
    """Create a RenderCVAdapter instance."""
    return RenderCVAdapter()


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    """Create a minimal valid RenderCV YAML file."""
    path = tmp_path / "test_resume.yaml"
    path.write_text(MINIMAL_YAML, encoding="utf-8")
    return path


class TestRenderCVAdapterProtocol:
    """Verify RenderCVAdapter satisfies RendererPort."""

    def test_implements_renderer_port(self, adapter: RenderCVAdapter) -> None:
        assert isinstance(adapter, RendererPort)


class TestRenderCVAdapterRender:
    """Tests for RenderCVAdapter.render with real rendercv."""

    @pytest.mark.slow
    def test_render_produces_pdf(
        self,
        adapter: RenderCVAdapter,
        yaml_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = adapter.render(yaml_file, output_dir)

        assert isinstance(result, RenderedOutput)
        assert result.pdf_path.exists()
        assert result.pdf_path.suffix == ".pdf"

    @pytest.mark.slow
    def test_render_produces_png(
        self,
        adapter: RenderCVAdapter,
        yaml_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = adapter.render(yaml_file, output_dir)

        assert result.png_path is not None
        assert result.png_path.exists()
        assert result.png_path.suffix == ".png"

    @pytest.mark.slow
    def test_render_produces_markdown(
        self,
        adapter: RenderCVAdapter,
        yaml_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = adapter.render(yaml_file, output_dir)

        assert result.md_path is not None
        assert result.md_path.exists()
        assert result.md_path.suffix == ".md"

    @pytest.mark.slow
    def test_render_produces_html(
        self,
        adapter: RenderCVAdapter,
        yaml_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = adapter.render(yaml_file, output_dir)

        assert result.html_path is not None
        assert result.html_path.exists()
        assert result.html_path.suffix == ".html"


class TestRenderCVAdapterErrors:
    """Tests for error handling in RenderCVAdapter."""

    def test_render_raises_for_missing_file(
        self,
        adapter: RenderCVAdapter,
        tmp_path: Path,
    ) -> None:
        nonexistent = tmp_path / "does_not_exist.yaml"
        with pytest.raises(RenderError, match="YAML file not found"):
            adapter.render(nonexistent, tmp_path / "output")

    def test_render_raises_for_invalid_yaml(
        self,
        adapter: RenderCVAdapter,
        tmp_path: Path,
    ) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("not: valid: rendercv: yaml: [[[", encoding="utf-8")

        with pytest.raises(RenderError, match="Invalid RenderCV YAML"):
            adapter.render(bad_yaml, tmp_path / "output")

    def test_render_raises_for_empty_yaml(
        self,
        adapter: RenderCVAdapter,
        tmp_path: Path,
    ) -> None:
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("", encoding="utf-8")

        with pytest.raises(RenderError, match="Invalid RenderCV YAML"):
            adapter.render(empty_yaml, tmp_path / "output")
