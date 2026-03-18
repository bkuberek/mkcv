"""Tests for the mkcv CLI application."""

import subprocess
from pathlib import Path


def _run_mkcv(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run mkcv CLI via subprocess and return the result."""
    return subprocess.run(
        ["uv", "run", "mkcv", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )


class TestMkcvHelp:
    """Tests for mkcv --help output."""

    def test_help_exits_zero(self) -> None:
        result = _run_mkcv("--help")
        assert result.returncode == 0

    def test_help_contains_mkcv(self) -> None:
        result = _run_mkcv("--help")
        assert "mkcv" in result.stdout.lower()

    def test_help_mentions_generate(self) -> None:
        result = _run_mkcv("--help")
        assert "generate" in result.stdout


class TestMkcvVersion:
    """Tests for mkcv --version output."""

    def test_version_exits_zero(self) -> None:
        result = _run_mkcv("--version")
        assert result.returncode == 0

    def test_version_prints_version_number(self) -> None:
        from mkcv import __version__

        result = _run_mkcv("--version")
        assert __version__ in result.stdout


class TestMkcvInit:
    """Tests for the mkcv init command."""

    def test_init_creates_workspace(self, tmp_path: Path) -> None:
        target = tmp_path / "new-workspace"
        result = _run_mkcv("init", str(target), cwd=tmp_path)
        assert result.returncode == 0
        assert (target / "mkcv.toml").is_file()

    def test_init_existing_workspace_shows_message(self, workspace_dir: Path) -> None:
        result = _run_mkcv("init", str(workspace_dir), cwd=workspace_dir.parent)
        assert result.returncode == 0
        assert "already exists" in result.stdout.lower()


class TestMkcvThemes:
    """Tests for the mkcv themes command."""

    def test_themes_lists_themes(self, tmp_path: Path) -> None:
        result = _run_mkcv("themes", cwd=tmp_path)
        assert result.returncode == 0
        assert "sb2nov" in result.stdout


class TestMkcvRender:
    """Tests for the mkcv render command."""

    def test_render_help_exits_zero(self) -> None:
        result = _run_mkcv("render", "--help")
        assert result.returncode == 0

    def test_render_help_mentions_yaml(self) -> None:
        result = _run_mkcv("render", "--help")
        output = result.stdout.lower()
        assert "yaml" in output


class TestMkcvGenerate:
    """Tests for the mkcv generate command."""

    def test_generate_help_exits_zero(self) -> None:
        result = _run_mkcv("generate", "--help")
        assert result.returncode == 0

    def test_generate_help_mentions_jd(self) -> None:
        result = _run_mkcv("generate", "--help")
        assert "jd" in result.stdout.lower()
