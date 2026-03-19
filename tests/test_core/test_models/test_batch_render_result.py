"""Tests for BatchRenderResult and ThemeRenderResult models."""

from pathlib import Path

from mkcv.core.models.batch_render_result import (
    BatchRenderResult,
    ThemeRenderResult,
)
from mkcv.core.ports.renderer import RenderedOutput


class TestThemeRenderResult:
    """Tests for ThemeRenderResult model."""

    def test_success_result_has_output_no_error(self, tmp_path: Path) -> None:
        pdf = tmp_path / "resume.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        output = RenderedOutput(pdf_path=pdf)
        result = ThemeRenderResult(
            theme="classic",
            status="success",
            output=output,
        )
        assert result.status == "success"
        assert result.output is not None
        assert result.error_message is None

    def test_error_result_has_message_no_output(self) -> None:
        result = ThemeRenderResult(
            theme="classic",
            status="error",
            error_message="Typst compilation failed",
        )
        assert result.status == "error"
        assert result.output is None
        assert result.error_message == "Typst compilation failed"


class TestBatchRenderResult:
    """Tests for BatchRenderResult model."""

    def _make_success(self, theme: str, tmp_path: Path) -> ThemeRenderResult:
        pdf = tmp_path / f"{theme}.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        return ThemeRenderResult(
            theme=theme,
            status="success",
            output=RenderedOutput(pdf_path=pdf),
        )

    def _make_error(self, theme: str) -> ThemeRenderResult:
        return ThemeRenderResult(
            theme=theme,
            status="error",
            error_message=f"Failed for {theme}",
        )

    def test_total_counts_all_results(self, tmp_path: Path) -> None:
        results = [
            self._make_success("sb2nov", tmp_path),
            self._make_success("classic", tmp_path),
            self._make_error("moderncv"),
        ]
        batch = BatchRenderResult(results=results)
        assert batch.total == 3

    def test_succeeded_counts_success_only(self, tmp_path: Path) -> None:
        results = [
            self._make_success("sb2nov", tmp_path),
            self._make_success("classic", tmp_path),
            self._make_error("moderncv"),
        ]
        batch = BatchRenderResult(results=results)
        assert batch.succeeded == 2

    def test_failed_counts_errors_only(self, tmp_path: Path) -> None:
        results = [
            self._make_success("sb2nov", tmp_path),
            self._make_success("classic", tmp_path),
            self._make_error("moderncv"),
        ]
        batch = BatchRenderResult(results=results)
        assert batch.failed == 1

    def test_all_succeeded_true_when_no_failures(self, tmp_path: Path) -> None:
        results = [
            self._make_success("sb2nov", tmp_path),
            self._make_success("classic", tmp_path),
        ]
        batch = BatchRenderResult(results=results)
        assert batch.all_succeeded is True

    def test_all_succeeded_false_with_any_failure(self, tmp_path: Path) -> None:
        results = [
            self._make_success("sb2nov", tmp_path),
            self._make_error("classic"),
        ]
        batch = BatchRenderResult(results=results)
        assert batch.all_succeeded is False
