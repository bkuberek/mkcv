"""Tests for the mkcv cover-letter CLI command."""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.model_report import ModelReport
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind

_CMD = "mkcv.cli.commands.cover_letter"


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


def _report(*warnings: ModelWarning) -> ModelReport:
    return ModelReport(
        profile_name="anthropic",
        profile_evidence="provisional",
        profile_source="default",
        preset_name="standard",
        stages=[],
        warnings=list(warnings),
        estimated_total_usd=None,
        estimate_is_partial=False,
    )


class TestCoverLetterHelp:
    def test_help_mentions_the_model_profile_flag(self) -> None:
        result = _run_mkcv("cover-letter", "--help")
        assert "--model-profile" in result.stdout


class TestCoverLetterModelSelection:
    """REQ-MP-4: ``cover-letter --model-profile`` and model warnings."""

    @pytest.fixture
    def run(self, tmp_path: Path) -> Iterator[MagicMock]:
        """Call the command with the service and report patched; yield the report."""
        jd = tmp_path / "jd.txt"
        jd.write_text("Job description", encoding="utf-8")
        kb = tmp_path / "kb.md"
        kb.write_text("# KB", encoding="utf-8")
        self.options: dict[str, object] = {
            "jd": str(jd),
            "kb": kb,
            "output_dir": tmp_path / "out",
        }
        with (
            patch(f"{_CMD}.settings") as mock_settings,
            patch(f"{_CMD}.create_cover_letter_service") as create_service,
            patch(f"{_CMD}.create_model_report", return_value=_report()) as report,
            patch(f"{_CMD}.asyncio.run", return_value=MagicMock()),
            patch(f"{_CMD}._display_result"),
        ):
            mock_settings.in_workspace = False
            self.settings = mock_settings
            self.create_service = create_service
            yield report

    def _invoke(self, **options: object) -> None:
        from mkcv.cli.commands.cover_letter import cover_letter_command

        cover_letter_command(**{**self.options, **options})  # type: ignore[arg-type]

    def test_the_profile_reaches_the_service_factory(self, run: MagicMock) -> None:
        self._invoke(model_profile="openai")
        assert self.create_service.call_args.kwargs["model_profile"] == "openai"

    def test_the_provider_reaches_the_service_factory(self, run: MagicMock) -> None:
        self._invoke(provider="google")
        assert self.create_service.call_args.kwargs["provider_override"] == "google"

    def test_the_preset_reaches_the_service_factory(self, run: MagicMock) -> None:
        self._invoke(preset="concise")
        assert self.create_service.call_args.kwargs["preset_name"] == "concise"

    def test_without_flags_the_service_gets_the_standard_preset(
        self, run: MagicMock
    ) -> None:
        self._invoke()
        self.create_service.assert_called_once_with(
            self.settings,
            provider_override=None,
            model_profile=None,
            preset_name="standard",
        )

    def test_only_the_cover_letter_stages_are_reported(self, run: MagicMock) -> None:
        self._invoke(model_profile="openai", preset="concise")
        run.assert_called_once_with(
            self.settings,
            preset_name="concise",
            model_profile="openai",
            provider_override=None,
            include_pipeline=False,
            include_cover_letter=True,
        )

    def test_warnings_are_printed(
        self, run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run.return_value = _report(
            ModelWarning(
                kind=ModelWarningKind.MISSING_API_KEY,
                stage=None,
                provider="openai",
                model=None,
                message="openai: no API key found (set OPENAI_API_KEY)",
            )
        )
        self._invoke()
        out = capsys.readouterr().out
        assert "Warning: openai: no API key found" in out
        assert "Run 'mkcv models' for recommended models per stage." in out

    def test_disabled_warnings_skip_the_report(self, run: MagicMock) -> None:
        self.settings.get.return_value = False
        self._invoke()
        run.assert_not_called()

    def test_a_configuration_error_exits_with_code_3_before_the_service_is_built(
        self, run: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run.side_effect = ConfigurationError("Unknown model profile 'nope'")
        with pytest.raises(SystemExit) as exit_info:
            self._invoke(model_profile="nope")
        assert exit_info.value.code == 3
        self.create_service.assert_not_called()
        assert "Unknown model profile 'nope'" in capsys.readouterr().out
