"""Tests for BatchRenderService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mkcv.core.exceptions.render import RenderError
from mkcv.core.ports.renderer import RenderedOutput
from mkcv.core.services.batch_render import BatchRenderService
from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

_MINIMAL_YAML = "cv:\n  name: Test\ndesign:\n  theme: sb2nov\n"


@pytest.fixture
def postprocessor() -> YamlPostProcessor:
    """Create a real YamlPostProcessor (no external deps, fast)."""
    return YamlPostProcessor()


@pytest.fixture
def source_yaml(tmp_path: Path) -> Path:
    """Create a minimal source YAML file."""
    yaml_file = tmp_path / "resume.yaml"
    yaml_file.write_text(_MINIMAL_YAML, encoding="utf-8")
    return yaml_file


def _make_rendered_output(theme_dir: Path) -> RenderedOutput:
    """Create a RenderedOutput with a fake PDF in a theme dir."""
    pdf = theme_dir / "Test_CV.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return RenderedOutput(pdf_path=pdf)


class TestBatchRenderService:
    """Tests for BatchRenderService."""

    def test_render_two_themes_success(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()

        def side_effect(
            yaml_path: Path,
            output_dir: Path,
            *,
            theme: str,
            formats: list[str] | None = None,
        ) -> RenderedOutput:
            return _make_rendered_output(output_dir)

        mock_render_service.render_resume.side_effect = side_effect

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        result = service.render_multi_theme(
            source_yaml, tmp_path, ["sb2nov", "classic"]
        )

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0

    def test_one_failure_continues_to_next(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        call_count = 0

        def side_effect(
            yaml_path: Path,
            output_dir: Path,
            *,
            theme: str,
            formats: list[str] | None = None,
        ) -> RenderedOutput:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RenderError("Typst compilation failed")
            return _make_rendered_output(output_dir)

        mock_render_service.render_resume.side_effect = side_effect

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        result = service.render_multi_theme(
            source_yaml, tmp_path, ["sb2nov", "classic"]
        )

        assert result.succeeded == 1
        assert result.failed == 1

    def test_all_themes_fail(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        mock_render_service.render_resume.side_effect = RenderError("fail")

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        result = service.render_multi_theme(
            source_yaml, tmp_path, ["sb2nov", "classic"]
        )

        assert result.succeeded == 0
        assert result.failed == 2

    def test_creates_theme_subdirectories(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        mock_render_service.render_resume.side_effect = (
            lambda yaml_path, output_dir, **kw: _make_rendered_output(output_dir)
        )

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        service.render_multi_theme(source_yaml, tmp_path, ["sb2nov", "classic"])

        assert (tmp_path / "renders" / "sb2nov").is_dir()
        assert (tmp_path / "renders" / "classic").is_dir()

    def test_writes_themed_yaml_variant(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        mock_render_service.render_resume.side_effect = (
            lambda yaml_path, output_dir, **kw: _make_rendered_output(output_dir)
        )

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        service.render_multi_theme(source_yaml, tmp_path, ["classic"])

        variant = tmp_path / "renders" / "classic" / "resume.yaml"
        assert variant.is_file()

    def test_injects_theme_correctly(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        mock_render_service.render_resume.side_effect = (
            lambda yaml_path, output_dir, **kw: _make_rendered_output(output_dir)
        )

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        service.render_multi_theme(source_yaml, tmp_path, ["classic"])

        variant = tmp_path / "renders" / "classic" / "resume.yaml"
        content = variant.read_text(encoding="utf-8")
        assert "classic" in content

    def test_source_yaml_not_found_raises(
        self,
        tmp_path: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )

        with pytest.raises(RenderError, match="YAML file not found"):
            service.render_multi_theme(
                tmp_path / "nonexistent.yaml", tmp_path, ["classic"]
            )

    def test_formats_passed_to_render_service(
        self,
        tmp_path: Path,
        source_yaml: Path,
        postprocessor: YamlPostProcessor,
    ) -> None:
        mock_render_service = MagicMock()
        mock_render_service.render_resume.side_effect = (
            lambda yaml_path, output_dir, **kw: _make_rendered_output(output_dir)
        )

        service = BatchRenderService(
            render_service=mock_render_service,
            postprocessor=postprocessor,
        )
        service.render_multi_theme(
            source_yaml, tmp_path, ["classic"], formats=["pdf", "png"]
        )

        call_kwargs = mock_render_service.render_resume.call_args
        assert call_kwargs.kwargs["formats"] == ["pdf", "png"]
