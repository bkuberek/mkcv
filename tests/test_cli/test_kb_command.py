"""Tests for the mkcv kb CLI commands."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mkcv.core.exceptions.kb_generation import KBGenerationError
from mkcv.core.models.document_content import DocumentContent
from mkcv.core.models.kb_generation_result import KBGenerationResult

_CMD = "mkcv.cli.commands.kb"


def _make_doc(name: str = "test.txt") -> DocumentContent:
    """Create a sample DocumentContent for test results."""
    return DocumentContent(
        text="sample text",
        source_path=Path(f"/tmp/{name}"),
        format="text",
        char_count=11,
    )


def _make_result(
    output_path: Path | None = None,
    warnings: list[str] | None = None,
) -> KBGenerationResult:
    """Create a sample KBGenerationResult for testing."""
    return KBGenerationResult(
        kb_text="# Career KB\n\n## Summary\nGenerated.",
        source_documents=[_make_doc()],
        output_path=output_path,
        validation_warnings=warnings or [],
    )


def _run_mkcv(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run mkcv CLI via subprocess and return the result."""
    return subprocess.run(
        ["uv", "run", "mkcv", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


# ------------------------------------------------------------------
# CLI help tests (subprocess)
# ------------------------------------------------------------------


class TestKBHelp:
    """Tests for mkcv kb --help output."""

    def test_kb_help_exits_zero(self) -> None:
        result = _run_mkcv("kb", "--help")
        assert result.returncode == 0

    def test_kb_help_mentions_generate(self) -> None:
        result = _run_mkcv("kb", "--help")
        assert "generate" in result.stdout.lower()

    def test_kb_help_mentions_update(self) -> None:
        result = _run_mkcv("kb", "--help")
        assert "update" in result.stdout.lower()


class TestKBGenerateHelp:
    """Tests for mkcv kb generate --help."""

    def test_generate_help_exits_zero(self) -> None:
        result = _run_mkcv("kb", "generate", "--help")
        assert result.returncode == 0

    def test_generate_help_mentions_sources(self) -> None:
        result = _run_mkcv("kb", "generate", "--help")
        assert "source" in result.stdout.lower()

    def test_generate_help_mentions_output(self) -> None:
        result = _run_mkcv("kb", "generate", "--help")
        assert "output" in result.stdout.lower()

    def test_generate_help_mentions_name(self) -> None:
        result = _run_mkcv("kb", "generate", "--help")
        assert "name" in result.stdout.lower()

    def test_generate_help_mentions_glob(self) -> None:
        result = _run_mkcv("kb", "generate", "--help")
        assert "glob" in result.stdout.lower()


class TestKBUpdateHelp:
    """Tests for mkcv kb update --help."""

    def test_update_help_exits_zero(self) -> None:
        result = _run_mkcv("kb", "update", "--help")
        assert result.returncode == 0

    def test_update_help_mentions_sources(self) -> None:
        result = _run_mkcv("kb", "update", "--help")
        assert "source" in result.stdout.lower()

    def test_update_help_mentions_kb(self) -> None:
        result = _run_mkcv("kb", "update", "--help")
        assert "kb" in result.stdout.lower()


# ------------------------------------------------------------------
# kb generate command (mocked service)
# ------------------------------------------------------------------


class TestKBGenerateCommand:
    """Tests for kb_generate_command with mocked service."""

    def test_generate_calls_service(self, tmp_path: Path) -> None:
        source = tmp_path / "resume.txt"
        source.write_text("resume content", encoding="utf-8")
        output = tmp_path / "kb.md"
        result = _make_result(output_path=output)
        mock_service = MagicMock()

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_kb_generation_service",
                return_value=mock_service,
            ),
            patch(f"{_CMD}.asyncio.run", return_value=result),
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_generate_command

            kb_generate_command(sources=[source], output=output)

    def test_generate_handles_service_error(self, tmp_path: Path) -> None:
        source = tmp_path / "resume.txt"
        source.write_text("content", encoding="utf-8")
        output = tmp_path / "kb.md"

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_kb_generation_service",
                side_effect=KBGenerationError("boom"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_generate_command

            kb_generate_command(sources=[source], output=output)

        assert exc_info.value.code == 9

    def test_generate_handles_runtime_error(self, tmp_path: Path) -> None:
        source = tmp_path / "resume.txt"
        source.write_text("content", encoding="utf-8")
        output = tmp_path / "kb.md"
        mock_service = MagicMock()

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_kb_generation_service",
                return_value=mock_service,
            ),
            patch(
                f"{_CMD}.asyncio.run",
                side_effect=KBGenerationError("generation failed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_generate_command

            kb_generate_command(sources=[source], output=output)

        assert exc_info.value.code == 9


# ------------------------------------------------------------------
# kb update command (mocked service)
# ------------------------------------------------------------------


class TestKBUpdateCommand:
    """Tests for kb_update_command with mocked service."""

    def test_update_calls_service(self, tmp_path: Path) -> None:
        kb_file = tmp_path / "existing.md"
        kb_file.write_text("# Old KB", encoding="utf-8")
        source = tmp_path / "new.txt"
        source.write_text("new content", encoding="utf-8")
        result = _make_result(output_path=kb_file)
        mock_service = MagicMock()

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(
                f"{_CMD}.create_kb_generation_service",
                return_value=mock_service,
            ),
            patch(f"{_CMD}.asyncio.run", return_value=result),
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_update_command

            kb_update_command(sources=[source], kb=kb_file)

    def test_update_nonexistent_kb_exits(self, tmp_path: Path) -> None:
        source = tmp_path / "new.txt"
        source.write_text("content", encoding="utf-8")
        ghost_kb = tmp_path / "nonexistent.md"

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_update_command

            kb_update_command(sources=[source], kb=ghost_kb)

        assert exc_info.value.code == 2

    def test_update_no_kb_specified_no_workspace_exits(self, tmp_path: Path) -> None:
        source = tmp_path / "new.txt"
        source.write_text("content", encoding="utf-8")

        with (
            patch(f"{_CMD}.settings") as mock_settings,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            from mkcv.cli.commands.kb import kb_update_command

            kb_update_command(sources=[source])

        assert exc_info.value.code == 2


# ------------------------------------------------------------------
# Path resolution helpers
# ------------------------------------------------------------------


class TestResolveOutput:
    """Tests for _resolve_output helper."""

    def test_explicit_output_returned(self) -> None:
        from mkcv.cli.commands.kb import _resolve_output

        p = Path("/tmp/my-kb.md")
        assert _resolve_output(p) == p

    def test_default_output_when_no_workspace(self) -> None:
        from mkcv.cli.commands.kb import _resolve_output

        with patch(f"{_CMD}.settings") as mock_settings:
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            result = _resolve_output(None)
            assert result.name == "career-kb.md"


class TestResolveExistingKB:
    """Tests for _resolve_existing_kb helper."""

    def test_explicit_kb_returned(self) -> None:
        from mkcv.cli.commands.kb import _resolve_existing_kb

        p = Path("/tmp/my-kb.md")
        assert _resolve_existing_kb(p) == p

    def test_returns_none_when_no_workspace(self) -> None:
        from mkcv.cli.commands.kb import _resolve_existing_kb

        with patch(f"{_CMD}.settings") as mock_settings:
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            assert _resolve_existing_kb(None) is None
