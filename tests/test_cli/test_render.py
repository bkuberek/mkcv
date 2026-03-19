"""Tests for the mkcv render CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.batch_render_result import (
    BatchRenderResult,
    ThemeRenderResult,
)
from mkcv.core.ports.renderer import RenderedOutput


@pytest.fixture
def mock_rendered_output(tmp_path: Path) -> RenderedOutput:
    """Create a RenderedOutput with real temporary file paths."""
    pdf = tmp_path / "resume.pdf"
    png = tmp_path / "resume.png"
    pdf.write_bytes(b"%PDF-1.4 fake")
    png.write_bytes(b"fake png")
    return RenderedOutput(
        pdf_path=pdf,
        png_path=png,
        md_path=None,
        html_path=None,
    )


class TestRenderFormatParsing:
    """Tests that --format flag is parsed and passed to the service."""

    def test_default_format_passes_pdf_png(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            "mkcv.cli.commands.render.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        mock_service.render_resume.assert_called_once()
        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["formats"] == ["pdf", "png"]

    def test_single_format_passes_only_that_format(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            "mkcv.cli.commands.render.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, format="pdf")

        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["formats"] == ["pdf"]

    def test_multiple_formats_parsed_correctly(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            "mkcv.cli.commands.render.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, format="pdf,md,html")

        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["formats"] == ["pdf", "md", "html"]

    def test_format_with_spaces_trimmed(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            "mkcv.cli.commands.render.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, format=" pdf , png ")

        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["formats"] == ["pdf", "png"]


_FACTORY = "mkcv.cli.commands.render"


class TestRenderFileHandling:
    """Tests for file existence checks in the render command."""

    def test_missing_yaml_file_exits_with_error(
        self,
        tmp_path: Path,
    ) -> None:
        yaml_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

    def test_resolves_yaml_to_absolute_path(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        call_args = mock_service.render_resume.call_args
        passed_path = call_args.args[0]
        assert passed_path.is_absolute()


class TestRenderOutputDisplay:
    """Tests for render command output display."""

    def test_successful_render_shows_pdf_path(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        captured = capsys.readouterr()
        assert "PDF:" in captured.out
        assert "resume.pdf" in captured.out

    def test_successful_render_shows_png_path(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        captured = capsys.readouterr()
        assert "PNG:" in captured.out
        assert "resume.png" in captured.out

    def test_render_shows_all_output_formats(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        pdf = tmp_path / "resume.pdf"
        png = tmp_path / "resume.png"
        md = tmp_path / "resume.md"
        html = tmp_path / "resume.html"
        pdf.write_bytes(b"%PDF-1.4 fake")
        png.write_bytes(b"fake png")
        md.write_text("# Resume")
        html.write_text("<html></html>")

        full_output = RenderedOutput(
            pdf_path=pdf, png_path=png, md_path=md, html_path=html
        )
        mock_service = MagicMock()
        mock_service.render_resume.return_value = full_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, format="pdf,png,md,html")

        captured = capsys.readouterr()
        assert "PDF:" in captured.out
        assert "PNG:" in captured.out
        assert "MD:" in captured.out
        assert "HTML:" in captured.out


class TestRenderErrorHandling:
    """Tests for error handling in the render command."""

    def test_render_error_propagates(
        self,
        tmp_path: Path,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.side_effect = RenderError("Typst compilation failed")

        with (
            patch(
                f"{_FACTORY}.create_render_service",
                return_value=mock_service,
            ),
            pytest.raises(RenderError, match="Typst compilation failed"),
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)


class TestRenderThemeAndOutputDir:
    """Tests for theme and output directory handling."""

    def test_custom_theme_passed_to_service(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, theme="classic")

        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["theme"] == "classic"

    def test_default_theme_is_sb2nov(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["theme"] == "sb2nov"

    def test_custom_output_dir_passed_to_service(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")
        output = tmp_path / "custom-output"
        output.mkdir()

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, output_dir=output)

        call_args = mock_service.render_resume.call_args
        assert call_args.args[1] == output

    def test_default_output_dir_is_yaml_parent(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        yaml_file = sub / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        call_args = mock_service.render_resume.call_args
        assert call_args.args[1] == sub


class TestRenderMultiTheme:
    """Tests for multi-theme rendering dispatch in the render command."""

    def test_comma_separated_theme_dispatches_to_batch_service(
        self,
        tmp_path: Path,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        batch_result = BatchRenderResult(
            results=[
                ThemeRenderResult(
                    theme="sb2nov",
                    status="success",
                    output=RenderedOutput(pdf_path=pdf),
                ),
                ThemeRenderResult(
                    theme="classic",
                    status="success",
                    output=RenderedOutput(pdf_path=pdf),
                ),
            ]
        )

        mock_batch_service = MagicMock()
        mock_batch_service.render_multi_theme.return_value = batch_result

        with (
            patch(
                f"{_FACTORY}.parse_theme_argument",
                return_value=["sb2nov", "classic"],
            ),
            patch(
                "mkcv.adapters.factory.create_batch_render_service",
                return_value=mock_batch_service,
            ),
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, theme="sb2nov,classic")

        mock_batch_service.render_multi_theme.assert_called_once()

    def test_all_keyword_dispatches_to_batch_service(
        self,
        tmp_path: Path,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        batch_result = BatchRenderResult(
            results=[
                ThemeRenderResult(
                    theme="sb2nov",
                    status="success",
                    output=RenderedOutput(pdf_path=pdf),
                ),
            ]
        )

        mock_batch_service = MagicMock()
        mock_batch_service.render_multi_theme.return_value = batch_result

        with (
            patch(
                f"{_FACTORY}.parse_theme_argument",
                return_value=["sb2nov"],
            ),
            patch(
                "mkcv.adapters.factory.create_batch_render_service",
                return_value=mock_batch_service,
            ),
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, theme="all")

        mock_batch_service.render_multi_theme.assert_called_once()

    def test_single_theme_unchanged(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file, theme="classic")

        # Should use single-theme path, not batch
        mock_service.render_resume.assert_called_once()
        call_kwargs = mock_service.render_resume.call_args
        assert call_kwargs.kwargs["theme"] == "classic"

    def test_no_theme_flag_unchanged(
        self,
        tmp_path: Path,
        mock_rendered_output: RenderedOutput,
    ) -> None:
        yaml_file = tmp_path / "resume.yaml"
        yaml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()
        mock_service.render_resume.return_value = mock_rendered_output

        with patch(
            f"{_FACTORY}.create_render_service",
            return_value=mock_service,
        ):
            from mkcv.cli.commands.render import render_command

            render_command(yaml_file)

        # Should use single-theme path with resolve_theme default
        mock_service.render_resume.assert_called_once()
