"""Tests for the mkcv validate CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.kb_validation import KBValidationResult
from mkcv.core.models.keyword_coverage import KeywordCoverage
from mkcv.core.models.review_report import ReviewReport


def _make_review_report(
    *,
    overall_score: int = 82,
    ats_pass: bool = True,
    coverage_percent: float = 85.0,
) -> ReviewReport:
    """Create a ReviewReport with sensible defaults for testing."""
    return ReviewReport(
        overall_score=overall_score,
        bullet_reviews=[
            BulletReview(
                bullet_text="Led migration of API platform",
                classification="faithful",
            ),
            BulletReview(
                bullet_text="Reduced latency by 50%",
                classification="enhanced",
                explanation="Approximate figure",
            ),
        ],
        keyword_coverage=KeywordCoverage(
            total_keywords=20,
            matched_keywords=17,
            coverage_percent=coverage_percent,
            missing_keywords=["GraphQL", "gRPC", "Terraform"],
            suggestions=["Add GraphQL experience"],
        ),
        ats_check=ATSCheck(
            single_column=True,
            no_tables=True,
            no_text_boxes=True,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=True,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=ats_pass,
            issues=[],
        ),
        tone_consistency="Consistent professional tone throughout",
        section_balance="Well-balanced sections",
        length_assessment="Appropriate length for experience level",
        top_suggestions=["Quantify more achievements", "Add GraphQL experience"],
        low_confidence_items=["Latency reduction figure needs verification"],
    )


_FACTORY = "mkcv.cli.commands.validate"


class TestValidateFileHandling:
    """Tests for file existence checks in the validate command."""

    def test_missing_resume_file_exits_with_error(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "nonexistent.yaml"

        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

    def test_missing_jd_file_exits_with_error(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        jd = tmp_path / "nonexistent.txt"

        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume, jd=jd)

    def test_no_file_and_no_kb_exits_with_error(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.validate import validate_command

            validate_command(file=None, kb=None)


class TestValidateWithResumeOnly:
    """Tests for validate with resume file only (no JD)."""

    def test_validates_resume_without_jd(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()
        mock_service.validate = MagicMock(return_value=report)

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        mock_service.validate.assert_called_once()

    def test_passes_none_jd_to_service(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()
        mock_service.validate = MagicMock(return_value=report)

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume, jd=None)

        call_args = mock_service.validate.call_args
        assert call_args.kwargs.get("jd_path") is None


class TestValidateWithJD:
    """Tests for validate with both resume and JD."""

    def test_validates_resume_with_jd(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description content")

        report = _make_review_report()
        mock_service = MagicMock()
        mock_service.validate = MagicMock(return_value=report)

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume, jd=jd)

        call_args = mock_service.validate.call_args
        assert call_args.kwargs.get("jd_path") == jd


class TestValidateKBMode:
    """Tests for validate --kb mode."""

    def test_kb_validation_succeeds(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        kb = tmp_path / "career.md"
        kb.write_text("# Summary\nSenior engineer.\n# Experience\n")

        valid_result = KBValidationResult(
            is_valid=True,
            warnings=[],
            errors=[],
            sections_found=["Summary", "Experience"],
            sections_missing=[],
        )

        with patch(f"{_FACTORY}.validate_kb", return_value=valid_result):
            from mkcv.cli.commands.validate import validate_command

            validate_command(file=None, kb=kb)

        captured = capsys.readouterr()
        assert "looks good" in captured.out

    def test_kb_validation_failure_exits_with_code_5(
        self,
        tmp_path: Path,
    ) -> None:
        kb = tmp_path / "bad.md"
        kb.write_text("No headings here")

        invalid_result = KBValidationResult(
            is_valid=False,
            warnings=[],
            errors=["No Markdown headings found."],
            sections_found=[],
            sections_missing=["Professional Summary"],
        )

        with (
            patch(f"{_FACTORY}.validate_kb", return_value=invalid_result),
            pytest.raises(SystemExit) as exc_info,
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(file=None, kb=kb)

        assert exc_info.value.code == 5

    def test_kb_file_not_found_exits_with_error(
        self,
        tmp_path: Path,
    ) -> None:
        kb = tmp_path / "nonexistent.md"

        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.validate import validate_command

            validate_command(file=None, kb=kb)


class TestValidateErrorHandling:
    """Tests for error handling in the validate command."""

    def test_validation_error_exits_with_code_5(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(
                f"{_FACTORY}.asyncio.run",
                side_effect=ValidationError("Unsupported file type"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        assert exc_info.value.code == 5

    def test_pipeline_stage_error_exits_with_code_5(
        self,
        tmp_path: Path,
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(
                f"{_FACTORY}.asyncio.run",
                side_effect=PipelineStageError(
                    "Review failed", stage="review", stage_number=5
                ),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        assert exc_info.value.code == 5


class TestValidateOutput:
    """Tests for validate command console output."""

    def test_displays_overall_score(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report(overall_score=82)
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "82" in captured.out

    def test_displays_ats_pass_status(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report(ats_pass=True)
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "PASS" in captured.out

    def test_displays_ats_fail_status(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report(ats_pass=False)
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "FAIL" in captured.out

    def test_displays_keyword_coverage(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report(coverage_percent=85.0)
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "17/20" in captured.out

    def test_displays_missing_keywords(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "GraphQL" in captured.out

    def test_displays_top_suggestions(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "Quantify more achievements" in captured.out

    def test_displays_low_confidence_items(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "verification" in captured.out

    def test_displays_resume_path_in_header(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")

        report = _make_review_report()
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume)

        captured = capsys.readouterr()
        assert "resume.yaml" in captured.out

    def test_displays_jd_path_when_provided(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description content")

        report = _make_review_report()
        mock_service = MagicMock()

        with (
            patch(
                f"{_FACTORY}.create_validation_service",
                return_value=mock_service,
            ),
            patch(f"{_FACTORY}.asyncio.run", return_value=report),
        ):
            from mkcv.cli.commands.validate import validate_command

            validate_command(resume, jd=jd)

        captured = capsys.readouterr()
        assert "jd.txt" in captured.out
