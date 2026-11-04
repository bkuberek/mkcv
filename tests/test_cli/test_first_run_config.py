"""Tests that any mkcv command creates the commented config files on first run."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

USER_FILE = Path(".config") / "mkcv" / "settings.toml"
CREATED_LINE = (
    "Created ~/.config/mkcv/settings.toml"
    " — add your API key there (see docs/models.md#api-keys)."
)


def _run(
    *args: str, home: Path, cwd: Path | None = None, **env: str
) -> subprocess.CompletedProcess[str]:
    """Run the CLI in a subprocess whose HOME is ``home``."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MKCV_NO_USER_CONFIG", "NO_COLOR"}
    }
    environment.update({"HOME": str(home), "USERPROFILE": str(home), **env})
    return subprocess.run(
        [sys.executable, "-c", "from mkcv.cli.app import main; main()", *args],
        capture_output=True,
        text=True,
        cwd=cwd or home,
        env=environment,
        timeout=60,
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "fresh-home"
    path.mkdir()
    return path


class TestFirstRun:
    def test_help_creates_the_user_config(self, home: Path) -> None:
        assert _run("--help", home=home).returncode == 0
        assert "[default.providers.anthropic]" in (home / USER_FILE).read_text()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_the_file_is_private(self, home: Path) -> None:
        _run("--help", home=home)
        assert stat.S_IMODE((home / USER_FILE).stat().st_mode) == 0o600

    def test_one_line_goes_to_stderr(self, home: Path) -> None:
        result = _run("--help", home=home)
        assert result.stderr.strip() == CREATED_LINE

    def test_nothing_is_added_to_stdout(self, home: Path) -> None:
        first = _run("--help", home=home).stdout
        assert "Created" not in first
        assert first == _run("--help", home=home).stdout

    def test_a_second_run_stays_quiet(self, home: Path) -> None:
        _run("--help", home=home)
        assert _run("--help", home=home).stderr == ""

    def test_a_file_with_content_is_never_touched(self, home: Path) -> None:
        (home / USER_FILE).parent.mkdir(parents=True)
        (home / USER_FILE).write_text("[default.general]\nverbose = false\n")
        result = _run("--help", home=home)
        assert result.stderr == ""
        assert (home / USER_FILE).read_text() == "[default.general]\nverbose = false\n"

    def test_an_empty_file_is_filled(self, home: Path) -> None:
        (home / USER_FILE).parent.mkdir(parents=True)
        (home / USER_FILE).write_text("\n")
        assert _run("--help", home=home).stderr.strip() == CREATED_LINE


class TestQuietInvocations:
    def test_version_creates_nothing(self, home: Path) -> None:
        result = _run("--version", home=home)
        assert result.returncode == 0
        assert not (home / ".config").exists()
        assert result.stderr == ""

    def test_the_opt_out_creates_nothing(self, home: Path) -> None:
        result = _run("--help", home=home, MKCV_NO_USER_CONFIG="1")
        assert result.returncode == 0
        assert not (home / ".config").exists()
        assert result.stderr == ""

    def test_an_unwritable_home_does_not_crash(self, tmp_path: Path) -> None:
        not_a_directory = tmp_path / "home-file"
        not_a_directory.write_text("x")
        result = _run("--help", home=not_a_directory, cwd=tmp_path)
        assert result.returncode == 0
        assert result.stderr == ""


class TestJsonOutput:
    def test_models_json_stays_parseable_on_the_first_run(self, home: Path) -> None:
        result = _run("models", "--json", home=home)
        assert result.returncode == 0
        json.loads(result.stdout)
        assert CREATED_LINE in result.stderr

    def test_models_works_with_the_created_file(self, home: Path) -> None:
        _run("--help", home=home)
        assert _run("models", home=home).returncode == 0


class TestWorkspaceFile:
    def test_an_empty_mkcv_toml_is_filled_and_reported(self, home: Path) -> None:
        workspace = home / "cv"
        workspace.mkdir()
        (workspace / "mkcv.toml").write_text("")
        result = _run("status", home=home, cwd=workspace)
        assert "[default.workspace]" in (workspace / "mkcv.toml").read_text()
        assert str(workspace / "mkcv.toml") in result.stderr.replace("\n", "")

    def test_a_missing_mkcv_toml_is_not_created(self, home: Path) -> None:
        workspace = home / "cv"
        workspace.mkdir()
        _run("--help", home=home, cwd=workspace)
        assert not (workspace / "mkcv.toml").exists()

    def test_init_writes_the_workspace_template(self, home: Path) -> None:
        _run("init", str(home / "cv"), home=home)
        assert "[default.paths]" in (home / "cv" / "mkcv.toml").read_text()
