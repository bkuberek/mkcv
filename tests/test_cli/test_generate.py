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
        mock_create.assert_called_once_with(
            mock_settings,
            preset_name="standard",
            provider_override=None,
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

    def test_interactive_uses_interactive_callback(self, tmp_path: Path) -> None:
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
            patch(f"{_CMD}._InteractiveProgressCallback") as mock_cls,
        ):
            mock_settings.in_workspace = False
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, interactive=True)
        mock_cls.assert_called_once()

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
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
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

    def test_workspace_mode_missing_company_exits(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company=None, position="Engineer")

    def test_workspace_mode_missing_position_exits(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "kb.md"
        kb.write_text("Knowledge base content")
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}._resolve_jd", return_value=("JD text", str(jd))),
            pytest.raises(SystemExit, match="2"),
        ):
            mock_settings.in_workspace = True
            mock_settings.workspace_root = tmp_path
            mock_settings.workspace.knowledge_base = "kb.md"
            from mkcv.cli.commands.generate import generate_command

            generate_command(jd=str(jd), kb=kb, company="TestCo", position=None)

    def test_workspace_mode_resolves_kb_from_config(self, tmp_path: Path) -> None:
        jd = _jd_path(tmp_path)
        kb = tmp_path / "knowledge-base" / "career.md"
        kb.parent.mkdir(parents=True)
        kb.write_text("Knowledge base content")
        app_dir = tmp_path / "applications" / "testco" / "2025-01-engineer"
        app_dir.mkdir(parents=True)
        result = _make_pipeline_result(tmp_path)
        mock_pipeline = MagicMock()
        mock_ws_service = MagicMock()
        mock_ws_service.setup_application.return_value = app_dir
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
