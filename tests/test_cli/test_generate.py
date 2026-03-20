"""Tests for the mkcv generate CLI command."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.workspace import WorkspaceError
from mkcv.core.models.kb_validation import KBValidationResult
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.ports.renderer import RenderedOutput

_CMD = "mkcv.cli.commands.generate"


def _make_stage(stage_number: int) -> StageMetadata:
    return StageMetadata(
        stage_number=stage_number,
        stage_name=f"stage_{stage_number}",
        provider="stub",
        model="test-model",
        temperature=0.3,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        duration_seconds=1.5,
    )


def _make_pipeline_result(
    output_dir: Path, *, include_yaml: bool = True
) -> PipelineResult:
    output_paths: dict[str, str] = {}
    if include_yaml:
        yaml_path = output_dir / "resume.yaml"
        yaml_path.write_text("cv:\n  name: Test\n", encoding="utf-8")
        output_paths["resume_yaml"] = str(yaml_path)
    return PipelineResult(
        run_id="test-run-001",
        timestamp=datetime.now(tz=UTC),
        jd_source="test-jd.txt",
        kb_source="career.md",
        company="TestCo",
        role_title="Engineer",
        stages=[_make_stage(i) for i in range(1, 6)],
        total_cost_usd=0.005,
        total_duration_seconds=7.5,
        review_score=85,
        output_paths=output_paths,
    )


def _valid_kb_result() -> KBValidationResult:
    return KBValidationResult(
        is_valid=True,
        warnings=[],
        errors=[],
        sections_found=["Professional Summary", "Experience"],
        sections_missing=[],
    )


def _jd_path(tmp_path: Path) -> Path:
    jd = tmp_path / "jd.txt"
    jd.write_text("Job description content")
    return jd


class TestGenerateStandaloneMode:
    def test_standalone_runs_pipeline_with_correct_args(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_pipeline.generate = MagicMock(return_value=result)
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb)
        # theme is resolved from settings.rendering.theme via resolve_theme()
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="standard",
            provider_override=None,
            theme=mock_settings.rendering.theme,
        )

    def test_standalone_missing_kb_exits_with_error(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=None)

    def test_standalone_missing_kb_file_exits_with_error(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "nonexistent.md"
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb)

    def test_jd_resolution_error_exits(self) -> None:
        with (
            patch(f"{_CMD}._resolve_jd", side_effect=SystemExit(2)),
            pytest.raises(SystemExit, match="2"),
        ):
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd="nonexistent.txt", kb=None)

    def test_from_stage_passed_to_pipeline(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, from_stage=3)
        call_args = mock_pipeline.generate.call_args
        assert call_args.kwargs["from_stage"] == 3

    def test_preset_passed_to_factory(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, preset="comprehensive")
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="comprehensive",
            provider_override=None,
            theme=mock_settings.rendering.theme,
        )

    def test_no_render_skips_auto_render(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(f"{_CMD}.create_render_service") as mock_render_factory,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=False)
        mock_render_factory.assert_not_called()

    def test_auto_render_runs_after_pipeline(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path, include_yaml=True)
        mock_pipeline = MagicMock()
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        mock_rendered = RenderedOutput(pdf_path=pdf_path)
        mock_render_svc = MagicMock()
        mock_render_svc.render_resume.return_value = mock_rendered
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(f"{_CMD}.create_render_service", return_value=mock_render_svc),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=True)
        mock_render_svc.render_resume.assert_called_once()

    def test_interactive_calls_interactive_pipeline(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(
                f"{_CMD}._run_interactive_pipeline",
            ) as mock_interactive,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, interactive=True)
        mock_interactive.assert_called_once()

    def test_non_interactive_uses_progress_callback(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(f"{_CMD}._ProgressCallback") as mock_cls,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, interactive=False)
        mock_cls.assert_called_once()

    def test_kb_validation_failure_exits_with_code_5(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        invalid_kb = KBValidationResult(
            is_valid=False,
            warnings=[],
            errors=["No Markdown headings found."],
            sections_found=[],
            sections_missing=["Professional Summary"],
        )
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.validate_kb", return_value=invalid_kb),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb)
        assert exc_info.value.code == 5


class TestGenerateWorkspaceMode:
    def test_workspace_mode_calls_workspace_service(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "testco" / "2025-01-engineer"
        app_dir.mkdir(parents=True)
        version_dir = app_dir / "resumes" / "v1"
        version_dir.mkdir(parents=True)
        (version_dir / ".mkcv").mkdir()
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
        mock_ws_service.create_output_version.return_value = version_dir
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company="TestCo", position="Engineer")
        mock_ws_service.setup_application.assert_called_once()
        mock_ws_service.create_output_version.assert_called_once()

    def test_workspace_mode_missing_company_extracts_via_llm(
        self, tmp_path: Path
    ) -> None:
        """When company is missing, LLM extraction is attempted."""
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "extracted-co" / "2025-01-engineer"
        app_dir.mkdir(parents=True)
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
        mock_ws_service.create_output_version.return_value = app_dir / "resumes" / "v1"
        (app_dir / "resumes" / "v1").mkdir(parents=True)
        (app_dir / "resumes" / "v1" / ".mkcv").mkdir()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(
                f"{_CMD}._extract_jd_metadata",
                return_value=("ExtractedCo", "Engineer"),
            ),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company=None, position="Engineer")
        mock_ws_service.setup_application.assert_called_once()

    def test_workspace_mode_extraction_fails_exits(self, tmp_path: Path) -> None:
        """When LLM extraction returns None, exit with error."""
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(
                f"{_CMD}._extract_jd_metadata",
                return_value=(None, None),
            ),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company=None, position=None)

    def test_workspace_mode_missing_position_extracts_via_llm(
        self, tmp_path: Path
    ) -> None:
        """When position is missing, LLM extraction is attempted."""
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "testco" / "2025-01-engineer"
        app_dir.mkdir(parents=True)
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
        mock_ws_service.create_output_version.return_value = app_dir / "resumes" / "v1"
        (app_dir / "resumes" / "v1").mkdir(parents=True)
        (app_dir / "resumes" / "v1" / ".mkcv").mkdir()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(
                f"{_CMD}._extract_jd_metadata",
                return_value=("TestCo", "ExtractedEngineer"),
            ),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company="TestCo", position=None)
        mock_ws_service.setup_application.assert_called_once()

    def test_workspace_mode_resolves_kb_from_config(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "knowledge-base" / "career.md"
        kb.parent.mkdir(parents=True)
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "testco" / "2025-01-engineer"
        app_dir.mkdir(parents=True)
        version_dir = app_dir / "resumes" / "v1"
        version_dir.mkdir(parents=True)
        (version_dir / ".mkcv").mkdir()
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
        mock_ws_service.create_output_version.return_value = version_dir
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "knowledge-base/career.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=None, company="TestCo", position="Engineer")
        mock_pipeline.generate.assert_called_once()

    def test_workspace_mode_kb_not_found_exits(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "nonexistent.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=None, company="TestCo", position="Engineer")

    def test_workspace_error_exits_with_workspace_exit_code(
        self, tmp_path: Path
    ) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.side_effect = WorkspaceError(
            "Directory already exists"
        )
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company="TestCo", position="Engineer")
        assert exc_info.value.code == 7


class TestGenerateErrorHandling:
    def test_provider_error_exits_with_code_4(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(
                f"{_CMD}.asyncio.run",
                side_effect=ProviderError("API key invalid", provider="anthropic"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb)
        assert exc_info.value.code == 4

    def test_pipeline_stage_error_exits_with_code_5(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(
                f"{_CMD}.asyncio.run",
                side_effect=PipelineStageError(
                    "Stage 3 failed", stage="tailor_content", stage_number=3
                ),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb)
        assert exc_info.value.code == 5

    def test_auto_render_failure_does_not_crash(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path, include_yaml=True)
        mock_pipeline = MagicMock()
        mock_render_svc = MagicMock()
        mock_render_svc.render_resume.side_effect = RuntimeError("Typst failed")
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(f"{_CMD}.create_render_service", return_value=mock_render_svc),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=True)

    def test_auto_render_skipped_when_no_yaml_in_output(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path, include_yaml=False)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
            patch(f"{_CMD}.create_render_service") as mock_render_factory,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=True)
        mock_render_factory.assert_not_called()


class TestGenerateOutput:
    def test_standalone_prints_mode_label(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=False)
        captured = capsys.readouterr()
        assert "standalone mode" in captured.out

    def test_pipeline_summary_shows_score(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, render=False)
        captured = capsys.readouterr()
        assert "85" in captured.out
        assert "100" in captured.out


class TestPresetAndProfileFlags:
    """Tests for --preset, --profile deprecation, and --provider override."""

    def test_preset_flag_is_accepted(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, preset="concise")
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="concise",
            provider_override=None,
            theme=mock_settings.rendering.theme,
        )

    def test_profile_budget_maps_to_concise_with_ollama(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, profile="budget")
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="concise",
            provider_override="ollama",
            theme=mock_settings.rendering.theme,
        )

    def test_profile_premium_maps_to_standard(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, profile="premium")
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="standard",
            provider_override=None,
            theme=mock_settings.rendering.theme,
        )

    def test_profile_triggers_deprecation_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, profile="budget")
        captured = capsys.readouterr()
        assert "deprecated" in captured.out.lower()

    def test_provider_override_passed_to_factory(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_pipeline_service", return_value=mock_pipeline
            ) as mock_create,
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(
                jd=str(jd), kb=kb, preset="comprehensive", provider="openrouter"
            )
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="comprehensive",
            provider_override="openrouter",
            theme=mock_settings.rendering.theme,
        )

    def test_preset_label_in_standalone_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, preset="concise", render=False)
        captured = capsys.readouterr()
        assert "Preset:" in captured.out
        assert "concise" in captured.out


class TestVersionBasedOutputDir:
    """Tests for version-based output directory naming."""

    def test_first_run_creates_v1(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_next_version

        version = _find_next_version(tmp_path, "2026-03-senior-swe-standard")
        assert version == 1

    def test_second_run_creates_v2(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_next_version

        (tmp_path / "2026-03-senior-swe-standard-v1").mkdir()
        version = _find_next_version(tmp_path, "2026-03-senior-swe-standard")
        assert version == 2

    def test_finds_highest_version(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_next_version

        (tmp_path / "2026-03-senior-swe-standard-v1").mkdir()
        (tmp_path / "2026-03-senior-swe-standard-v2").mkdir()
        (tmp_path / "2026-03-senior-swe-standard-v3").mkdir()
        version = _find_next_version(tmp_path, "2026-03-senior-swe-standard")
        assert version == 4

    def test_different_preset_starts_at_v1(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_next_version

        (tmp_path / "2026-03-senior-swe-standard-v1").mkdir()
        (tmp_path / "2026-03-senior-swe-standard-v2").mkdir()
        version = _find_next_version(tmp_path, "2026-03-senior-swe-comprehensive")
        assert version == 1

    def test_nonexistent_parent_returns_v1(self) -> None:
        from mkcv.cli.commands.generate import _find_next_version

        version = _find_next_version(Path("/nonexistent"), "base")
        assert version == 1

    def test_preset_name_in_output_dir(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _default_output_dir

        with patch(f"{_CMD}.settings") as mock_settings:
            mock_settings.in_workspace = False
            result = _default_output_dir("<generic resume>", "standard")
        assert "standard" in result.name
        assert result.name.endswith("-v1")

    def test_output_dir_includes_version(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _default_output_dir

        with patch(f"{_CMD}.settings") as mock_settings:
            mock_settings.in_workspace = False
            result = _default_output_dir("<generic resume>", "concise")
        assert "-v1" in result.name


class TestWriteRunMetadata:
    """Tests for _write_run_metadata helper."""

    def test_writes_run_metadata_json(self, tmp_path: Path) -> None:
        import json

        from mkcv.cli.commands.generate import _write_run_metadata

        result = _make_pipeline_result(tmp_path)
        _write_run_metadata(
            output_dir=tmp_path,
            result=result,
            preset_name="standard",
            provider_override=None,
        )
        metadata_path = tmp_path / ".mkcv" / "run_metadata.json"
        assert metadata_path.is_file()
        data = json.loads(metadata_path.read_text())
        assert data["preset"] == "standard"
        assert data["review_score"] == 85

    def test_run_metadata_includes_cost(self, tmp_path: Path) -> None:
        import json

        from mkcv.cli.commands.generate import _write_run_metadata

        result = _make_pipeline_result(tmp_path)
        _write_run_metadata(
            output_dir=tmp_path,
            result=result,
            preset_name="concise",
            provider_override=None,
        )
        data = json.loads((tmp_path / ".mkcv" / "run_metadata.json").read_text())
        assert data["total_cost_usd"] == result.total_cost_usd

    def test_run_metadata_uses_provider_override(self, tmp_path: Path) -> None:
        import json

        from mkcv.cli.commands.generate import _write_run_metadata

        result = _make_pipeline_result(tmp_path)
        _write_run_metadata(
            output_dir=tmp_path,
            result=result,
            preset_name="standard",
            provider_override="openrouter",
        )
        data = json.loads((tmp_path / ".mkcv" / "run_metadata.json").read_text())
        assert data["provider"] == "openrouter"

    def test_no_write_when_no_stages(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _write_run_metadata

        result = PipelineResult(
            run_id="empty",
            timestamp=datetime.now(tz=UTC),
            jd_source="jd.txt",
            kb_source="kb.md",
            company="Co",
            role_title="Eng",
            stages=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            review_score=0,
            output_paths={},
        )
        _write_run_metadata(
            output_dir=tmp_path,
            result=result,
            preset_name="standard",
            provider_override=None,
        )
        assert not (tmp_path / ".mkcv" / "run_metadata.json").exists()


class TestExtractJDMetadataCommand:
    """Tests for _extract_jd_metadata CLI helper."""

    def test_returns_company_position(self) -> None:
        from mkcv.cli.commands.generate import _extract_jd_metadata

        with (
            patch(f"{_CMD}.create_pipeline_service") as mock_factory,
            patch(f"{_CMD}.asyncio.run") as mock_run,
            patch(f"{_CMD}.settings"),
        ):
            mock_fm = MagicMock()
            mock_fm.company = "ExtractedCo"
            mock_fm.position = "Sr. Engineer"
            mock_run.return_value = mock_fm
            company, position = _extract_jd_metadata(
                "JD text", preset="standard", provider_override=None, theme="sb2nov"
            )
        assert company == "ExtractedCo"
        assert position == "Sr. Engineer"
        mock_factory.assert_called_once()

    def test_returns_none_on_error(self) -> None:
        from mkcv.cli.commands.generate import _extract_jd_metadata

        with (
            patch(f"{_CMD}.create_pipeline_service"),
            patch(f"{_CMD}.asyncio.run", side_effect=RuntimeError("fail")),
            patch(f"{_CMD}.settings"),
        ):
            company, position = _extract_jd_metadata(
                "JD text", preset="standard", provider_override=None, theme="sb2nov"
            )
        assert company is None
        assert position is None


class TestVersionedOutputWorkspaceMode:
    """Tests for versioned output placement in workspace mode."""

    def test_workspace_mode_creates_versioned_resume_dir(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "testco" / "engineer" / "2025-01-01"
        version_dir = app_dir / "resumes" / "v1"
        version_dir.mkdir(parents=True)
        (version_dir / ".mkcv").mkdir()
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
        mock_ws_service.create_output_version.return_value = version_dir
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.asyncio.run", return_value=result),
            patch(f"{_CMD}.validate_kb", return_value=_valid_kb_result()),
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            patch(f"{_CMD}._write_jd_file", return_value=jd),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company="TestCo", position="Engineer")
        mock_ws_service.create_output_version.assert_called_once_with(
            app_dir, "resumes"
        )

    def test_cover_letter_chain_creates_versioned_dir(self, tmp_path: Path) -> None:
        """Chaining cover letter in workspace mode creates versioned dir."""
        from mkcv.cli.commands.generate import _chain_cover_letter

        result = _make_pipeline_result(tmp_path, include_yaml=True)
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        cl_version_dir = app_dir / "cover-letter" / "v1"
        cl_version_dir.mkdir(parents=True)
        (cl_version_dir / ".mkcv").mkdir()

        mock_ws_service = MagicMock()
        mock_ws_service.create_output_version.return_value = cl_version_dir
        mock_cl_result = MagicMock()
        mock_cl_result.stages = []
        mock_cl_result.review_score = 80
        mock_cl_result.output_paths = {}

        with (
            patch(f"{_CMD}.create_workspace_service", return_value=mock_ws_service),
            patch(f"{_CMD}.create_cover_letter_service"),
            patch(f"{_CMD}.asyncio.run", return_value=mock_cl_result),
        ):
            _chain_cover_letter(
                result=result,
                jd_text="JD text",
                output_dir=tmp_path,
                provider_override=None,
                cl_preset="standard",
                app_dir=app_dir,
            )
        mock_ws_service.create_output_version.assert_called_once_with(
            app_dir, "cover-letter"
        )


class TestAppDirMutualExclusivity:
    """Tests for --app-dir mutual exclusivity with other flags."""

    def test_app_dir_with_jd_exits_2(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir, jd="some-jd.txt")

    def test_app_dir_with_company_exits_2(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir, company="TestCo")

    def test_app_dir_with_position_exits_2(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir, position="Engineer")

    def test_app_dir_with_target_exits_2(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        with pytest.raises(SystemExit, match="2"):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir, target="Staff Engineer")


class TestAppDirValidation:
    """Tests for --app-dir validation errors."""

    def test_app_dir_not_found_exits(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        with (
            patch(f"{_CMD}.settings"),
            pytest.raises(SystemExit, match="2"),
        ):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=nonexistent)

    def test_app_dir_missing_application_toml_exits(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        with (
            patch(f"{_CMD}.settings"),
            pytest.raises(SystemExit, match="2"),
        ):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir)

    def test_app_dir_missing_jd_exits(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "application.toml").write_text(
            '[application]\ncompany = "Co"\nposition = "Eng"\n'
        )
        with (
            patch(f"{_CMD}.settings"),
            pytest.raises(SystemExit, match="2"),
        ):
            from mkcv.cli.commands.generate import generate_command

            generate_command(app_dir=app_dir)


class TestAppDirHelpers:
    """Unit tests for app-dir helper functions."""

    def test_find_jd_prefers_md_over_txt(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_jd_in_app_dir

        (tmp_path / "jd.md").write_text("# JD")
        (tmp_path / "jd.txt").write_text("JD text")
        result = _find_jd_in_app_dir(tmp_path)
        assert result is not None
        assert result.name == "jd.md"

    def test_find_jd_falls_back_to_txt(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_jd_in_app_dir

        (tmp_path / "jd.txt").write_text("JD text")
        result = _find_jd_in_app_dir(tmp_path)
        assert result is not None
        assert result.name == "jd.txt"

    def test_find_jd_returns_none_when_missing(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_jd_in_app_dir

        result = _find_jd_in_app_dir(tmp_path)
        assert result is None

    def test_read_app_metadata_returns_company_position(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _read_app_metadata

        (tmp_path / "application.toml").write_text(
            '[application]\ncompany = "Acme"\nposition = "SWE"\n'
        )
        company, position = _read_app_metadata(tmp_path)
        assert company == "Acme"
        assert position == "SWE"

    def test_read_app_metadata_returns_none_when_missing(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _read_app_metadata

        company, position = _read_app_metadata(tmp_path)
        assert company is None
        assert position is None

    def test_read_app_metadata_handles_malformed_toml(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _read_app_metadata

        (tmp_path / "application.toml").write_text("not valid toml [[[")
        company, position = _read_app_metadata(tmp_path)
        assert company is None
        assert position is None

    def test_find_latest_version_dir_returns_highest(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _find_latest_version_dir

        (tmp_path / "v1").mkdir()
        (tmp_path / "v2").mkdir()
        (tmp_path / "v3").mkdir()
        result = _find_latest_version_dir(tmp_path)
        assert result is not None
        assert result.name == "v3"

    def test_find_latest_version_dir_returns_none_when_empty(
        self, tmp_path: Path
    ) -> None:
        from mkcv.cli.commands.generate import _find_latest_version_dir

        result = _find_latest_version_dir(tmp_path)
        assert result is None

    def test_find_latest_version_dir_returns_none_for_nonexistent(self) -> None:
        from mkcv.cli.commands.generate import _find_latest_version_dir

        result = _find_latest_version_dir(Path("/nonexistent/dir"))
        assert result is None

    def test_find_latest_version_dir_ignores_non_version_dirs(
        self, tmp_path: Path
    ) -> None:
        from mkcv.cli.commands.generate import _find_latest_version_dir

        (tmp_path / "v1").mkdir()
        (tmp_path / "not-a-version").mkdir()
        (tmp_path / "latest").mkdir()
        result = _find_latest_version_dir(tmp_path)
        assert result is not None
        assert result.name == "v1"

    def test_copy_stage_artifacts_copies_json_files(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _copy_stage_artifacts

        source = tmp_path / "v1"
        source_mkcv = source / ".mkcv"
        source_mkcv.mkdir(parents=True)
        (source_mkcv / "stage1.json").write_text('{"data": 1}')
        (source_mkcv / "stage2.json").write_text('{"data": 2}')
        (source_mkcv / "notes.txt").write_text("not json")

        target = tmp_path / "v2"
        target.mkdir()

        copied = _copy_stage_artifacts(source, target)
        assert copied == 2
        assert (target / ".mkcv" / "stage1.json").is_file()
        assert (target / ".mkcv" / "stage2.json").is_file()
        assert not (target / ".mkcv" / "notes.txt").exists()

    def test_copy_stage_artifacts_returns_zero_when_no_source(
        self, tmp_path: Path
    ) -> None:
        from mkcv.cli.commands.generate import _copy_stage_artifacts

        source = tmp_path / "v1"
        source.mkdir()
        target = tmp_path / "v2"
        target.mkdir()

        copied = _copy_stage_artifacts(source, target)
        assert copied == 0

    def test_copy_stage_artifacts_creates_target_mkcv_dir(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.generate import _copy_stage_artifacts

        source = tmp_path / "v1"
        source_mkcv = source / ".mkcv"
        source_mkcv.mkdir(parents=True)
        (source_mkcv / "stage1.json").write_text('{"data": 1}')

        target = tmp_path / "v2"
        target.mkdir()

        _copy_stage_artifacts(source, target)
        assert (target / ".mkcv").is_dir()


class TestInteractivePipelineRegenWiring:
    """Tests that _run_interactive_pipeline wires up regeneration service."""

    @staticmethod
    def _stage3_data() -> dict[str, object]:
        """Minimal stage-3 JSON content for TailoredContent."""
        return {
            "mission": {
                "text": "Experienced engineer.",
                "rationale": "Aligns with role.",
            },
            "skills": [{"label": "Languages", "skills": ["Python"]}],
            "roles": [
                {
                    "company": "Acme",
                    "position": "Engineer",
                    "start_date": "2020-01",
                    "end_date": "2023-06",
                    "bullets": [
                        {
                            "original": "orig",
                            "rewritten": "rewrite",
                            "keywords_incorporated": [],
                            "confidence": "high",
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def _stage1_data() -> dict[str, object]:
        """Minimal stage-1 JD analysis JSON."""
        return {
            "company": "Acme Corp",
            "role_title": "Engineer",
            "ats_keywords": ["python", "distributed"],
        }

    @staticmethod
    def _stage2_data() -> dict[str, object]:
        """Minimal stage-2 selection JSON."""
        return {"selected_roles": ["Engineer"]}

    def _setup_artifacts(
        self,
        tmp_path: Path,
        *,
        with_stage1: bool = True,
        with_stage2: bool = True,
    ) -> Path:
        """Create output dir with stage artifacts and return it."""
        output_dir = tmp_path / "output"
        mkcv_dir = output_dir / ".mkcv"
        mkcv_dir.mkdir(parents=True)

        import json

        (mkcv_dir / "stage3_content.json").write_text(
            json.dumps(self._stage3_data()),
        )
        if with_stage1:
            (mkcv_dir / "stage1_analysis.json").write_text(
                json.dumps(self._stage1_data()),
            )
        if with_stage2:
            (mkcv_dir / "stage2_selection.json").write_text(
                json.dumps(self._stage2_data()),
            )
        return output_dir

    def test_interactive_session_receives_regen_service_and_context(
        self, tmp_path: Path
    ) -> None:
        """When stage-1 artifact exists, InteractiveSession gets regen service."""
        output_dir = self._setup_artifacts(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_regen_service = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(
                f"{_CMD}.create_regeneration_service",
                return_value=mock_regen_service,
            ) as mock_create_regen,
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify InteractiveSession was called with regen_service and regen_context
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["regeneration_service"] is mock_regen_service
        assert call_kwargs.kwargs["regeneration_context"] is not None
        regen_ctx = call_kwargs.kwargs["regeneration_context"]
        assert regen_ctx.ats_keywords == ["python", "distributed"]
        assert regen_ctx.kb_text == "Knowledge base content"
        assert regen_ctx.jd_analysis["company"] == "Acme Corp"
        assert regen_ctx.selection == self._stage2_data()

        # Verify create_regeneration_service was called
        mock_create_regen.assert_called_once()

    def test_interactive_session_without_stage1_has_no_regen(
        self, tmp_path: Path
    ) -> None:
        """When stage-1 artifact is missing, session gets no regen service."""
        output_dir = self._setup_artifacts(tmp_path, with_stage1=False)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.create_regeneration_service") as mock_create_regen,
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify InteractiveSession was called with None for regen service
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["regeneration_service"] is None
        assert call_kwargs.kwargs["regeneration_context"] is None

        # create_regeneration_service should NOT have been called
        mock_create_regen.assert_not_called()

    def test_interactive_session_without_stage2_still_has_regen(
        self, tmp_path: Path
    ) -> None:
        """When stage-2 is missing but stage-1 exists, regen works without selection."""
        output_dir = self._setup_artifacts(
            tmp_path, with_stage1=True, with_stage2=False
        )
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_regen_service = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(
                f"{_CMD}.create_regeneration_service",
                return_value=mock_regen_service,
            ),
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify session gets regen service with context.selection = None
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["regeneration_service"] is mock_regen_service
        regen_ctx = call_kwargs.kwargs["regeneration_context"]
        assert regen_ctx is not None
        assert regen_ctx.selection is None

    def test_regen_service_creation_error_degrades_gracefully(
        self, tmp_path: Path
    ) -> None:
        """If create_regeneration_service raises, session works without regen."""
        output_dir = self._setup_artifacts(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(
                f"{_CMD}.create_regeneration_service",
                side_effect=RuntimeError("No API key"),
            ),
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify session was still created, but without regen service
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["regeneration_service"] is None
        assert call_kwargs.kwargs["regeneration_context"] is None


class TestInteractivePipelinePromptFnWiring:
    """Tests that _run_interactive_pipeline wires prompt_fn via create_prompt_fn."""

    @staticmethod
    def _stage3_data() -> dict[str, object]:
        """Minimal stage-3 JSON content for TailoredContent."""
        return {
            "mission": {
                "text": "Experienced engineer.",
                "rationale": "Aligns with role.",
            },
            "skills": [{"label": "Languages", "skills": ["Python"]}],
            "roles": [
                {
                    "company": "Acme",
                    "position": "Engineer",
                    "start_date": "2020-01",
                    "end_date": "2023-06",
                    "bullets": [
                        {
                            "original": "orig",
                            "rewritten": "rewrite",
                            "keywords_incorporated": [],
                            "confidence": "high",
                        }
                    ],
                }
            ],
        }

    def _setup_artifacts(self, tmp_path: Path) -> Path:
        """Create output dir with stage artifacts and return it."""
        import json

        output_dir = tmp_path / "output"
        mkcv_dir = output_dir / ".mkcv"
        mkcv_dir.mkdir(parents=True)

        (mkcv_dir / "stage3_content.json").write_text(
            json.dumps(self._stage3_data()),
        )
        return output_dir

    def test_prompt_fn_passed_to_interactive_session(self, tmp_path: Path) -> None:
        """When create_prompt_fn returns a callable, it is passed to the session."""
        output_dir = self._setup_artifacts(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance
        mock_prompt_fn = MagicMock()

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.create_regeneration_service"),
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            patch(
                "mkcv.cli.interactive.prompt_input.create_prompt_fn",
                return_value=mock_prompt_fn,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify prompt_fn is passed to InteractiveSession
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["prompt_fn"] is mock_prompt_fn

    def test_prompt_fn_is_none_when_create_returns_none(self, tmp_path: Path) -> None:
        """When create_prompt_fn returns None (non-TTY), prompt_fn=None is passed."""
        output_dir = self._setup_artifacts(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description")

        mock_pipeline = MagicMock()
        mock_session_cls = MagicMock()
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = None  # cancelled

        mock_session_cls.return_value = mock_session_instance

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_pipeline_service", return_value=mock_pipeline),
            patch(f"{_CMD}.create_regeneration_service"),
            patch(f"{_CMD}.asyncio.run", return_value=_make_pipeline_result(tmp_path)),
            patch(
                "mkcv.cli.interactive.InteractiveSession",
                mock_session_cls,
            ),
            patch(
                "mkcv.cli.interactive.prompt_input.create_prompt_fn",
                return_value=None,
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False

            from mkcv.cli.commands.generate import _run_interactive_pipeline

            _run_interactive_pipeline(
                jd=jd,
                kb=kb,
                output_dir=output_dir,
                preset_name="standard",
                theme="sb2nov",
            )

        # Verify prompt_fn=None is passed to InteractiveSession
        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args
        assert call_kwargs.kwargs["prompt_fn"] is None
