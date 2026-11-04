"""Tests for creating the user and workspace config files on first run."""

import os
import stat
from pathlib import Path

import pytest

from mkcv import __version__
from mkcv.adapters.filesystem.config_bootstrap import ConfigBootstrap
from mkcv.adapters.filesystem.config_scope import ConfigScope
from mkcv.adapters.filesystem.config_template import render_config_template


@pytest.fixture
def bootstrap() -> ConfigBootstrap:
    return ConfigBootstrap(environ={})


@pytest.fixture
def user_config(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".config" / "mkcv" / "settings.toml"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class TestUserConfigCreation:
    def test_creates_a_missing_file_from_the_template(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        assert bootstrap.ensure_user_config(user_config) is True
        assert user_config.read_text(encoding="utf-8") == render_config_template(
            ConfigScope.USER
        )

    def test_creates_the_parent_directories(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        bootstrap.ensure_user_config(user_config)
        assert user_config.parent.is_dir()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_creates_the_file_private_to_the_owner(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        bootstrap.ensure_user_config(user_config)
        assert _mode(user_config) == 0o600

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_is_private_from_the_start_even_under_a_permissive_umask(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        previous = os.umask(0)
        try:
            bootstrap.ensure_user_config(user_config)
        finally:
            os.umask(previous)
        assert _mode(user_config) == 0o600

    @pytest.mark.parametrize("blank", ["", " ", "\n", " \n\t\r\n  "])
    def test_fills_an_empty_or_whitespace_file(
        self, bootstrap: ConfigBootstrap, user_config: Path, blank: str
    ) -> None:
        user_config.parent.mkdir(parents=True)
        user_config.write_text(blank)
        assert bootstrap.ensure_user_config(user_config) is True
        assert "[default.providers.anthropic]" in user_config.read_text()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_keeps_the_permissions_of_an_existing_empty_file(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        user_config.parent.mkdir(parents=True)
        user_config.write_text("")
        user_config.chmod(0o644)
        bootstrap.ensure_user_config(user_config)
        assert _mode(user_config) == 0o644

    @pytest.mark.parametrize(
        "content", ["# just a comment\n", "[default.general]\nverbose = true\n", "x"]
    )
    def test_never_changes_a_file_with_content(
        self, bootstrap: ConfigBootstrap, user_config: Path, content: str
    ) -> None:
        user_config.parent.mkdir(parents=True)
        user_config.write_text(content)
        assert bootstrap.ensure_user_config(user_config) is False
        assert user_config.read_text() == content

    def test_a_second_call_changes_nothing(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        bootstrap.ensure_user_config(user_config)
        user_config.write_text(user_config.read_text() + "# mine\n")
        assert bootstrap.ensure_user_config(user_config) is False
        assert user_config.read_text().endswith("# mine\n")


class TestOptOut:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_the_environment_variable_skips_creation(
        self, user_config: Path, value: str
    ) -> None:
        skipped = ConfigBootstrap(environ={"MKCV_NO_USER_CONFIG": value})
        assert skipped.ensure_user_config(user_config) is False
        assert not user_config.exists()

    @pytest.mark.parametrize("value", ["", "0", "false", "no"])
    def test_a_falsy_value_does_not_opt_out(
        self, user_config: Path, value: str
    ) -> None:
        enabled = ConfigBootstrap(environ={"MKCV_NO_USER_CONFIG": value})
        assert enabled.ensure_user_config(user_config) is True

    def test_the_opt_out_also_leaves_an_empty_workspace_file_alone(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "mkcv.toml").write_text("")
        skipped = ConfigBootstrap(environ={"MKCV_NO_USER_CONFIG": "1"})
        assert skipped.ensure_workspace_config(tmp_path) is False
        assert (tmp_path / "mkcv.toml").read_text() == ""


class TestWriteFailures:
    def test_a_parent_that_is_a_file_is_swallowed(
        self,
        bootstrap: ConfigBootstrap,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        (tmp_path / "blocker").write_text("not a directory")
        with caplog.at_level("DEBUG"):
            created = bootstrap.ensure_user_config(
                tmp_path / "blocker" / "mkcv" / "settings.toml"
            )
        assert created is False
        assert "settings.toml" in caplog.text

    @pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0, reason="needs POSIX non-root"
    )
    def test_a_read_only_home_is_swallowed(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        home = tmp_path / "ro"
        home.mkdir()
        home.chmod(0o500)
        try:
            created = bootstrap.ensure_user_config(home / ".config" / "mkcv" / "s.toml")
        finally:
            home.chmod(0o700)
        assert created is False

    def test_a_directory_in_the_way_is_swallowed(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        user_config.mkdir(parents=True)
        assert bootstrap.ensure_user_config(user_config) is False

    def test_a_file_that_is_not_text_is_left_alone(
        self, bootstrap: ConfigBootstrap, user_config: Path
    ) -> None:
        user_config.parent.mkdir(parents=True)
        user_config.write_bytes(b"\xff\xfe\x00binary")
        assert bootstrap.ensure_user_config(user_config) is False
        assert user_config.read_bytes() == b"\xff\xfe\x00binary"


class TestWorkspaceConfig:
    def test_fills_an_empty_mkcv_toml_from_the_workspace_template(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        (tmp_path / "mkcv.toml").write_text(" \n")
        assert bootstrap.ensure_workspace_config(tmp_path) is True
        assert (tmp_path / "mkcv.toml").read_text() == render_config_template(
            ConfigScope.WORKSPACE, version=__version__
        )

    def test_never_creates_a_missing_mkcv_toml(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        assert bootstrap.ensure_workspace_config(tmp_path) is False
        assert not (tmp_path / "mkcv.toml").exists()

    def test_never_changes_a_non_empty_mkcv_toml(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        (tmp_path / "mkcv.toml").write_text("[default.general]\nverbose = true\n")
        assert bootstrap.ensure_workspace_config(tmp_path) is False
        assert (tmp_path / "mkcv.toml").read_text() == (
            "[default.general]\nverbose = true\n"
        )

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_keeps_the_permissions_of_the_file(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        target = tmp_path / "mkcv.toml"
        target.write_text("")
        target.chmod(0o664)
        bootstrap.ensure_workspace_config(tmp_path)
        assert _mode(target) == 0o664

    @pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0, reason="needs POSIX non-root"
    )
    def test_a_read_only_file_is_swallowed(
        self, bootstrap: ConfigBootstrap, tmp_path: Path
    ) -> None:
        target = tmp_path / "mkcv.toml"
        target.write_text("")
        target.chmod(0o400)
        assert bootstrap.ensure_workspace_config(tmp_path) is False
