"""Tests for the mkcv cover-letter CLI command."""

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


class TestCoverLetterCommandRegistered:
    """Tests that the cover-letter command is registered."""

    def test_cover_letter_command_registered(self) -> None:
        result = _run_mkcv("--help")
        assert result.returncode == 0
        assert "cover-letter" in result.stdout

    def test_help_shows_cover_letter(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert result.returncode == 0
        assert "cover" in result.stdout.lower()

    def test_cover_letter_help_mentions_jd(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert result.returncode == 0
        assert "jd" in result.stdout.lower()

    def test_cover_letter_help_mentions_kb(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert result.returncode == 0
        assert "kb" in result.stdout.lower()

    def test_cover_letter_help_mentions_resume(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert result.returncode == 0
        assert "resume" in result.stdout.lower()

    def test_cover_letter_help_mentions_company(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert result.returncode == 0
        assert "company" in result.stdout.lower()
