"""Tests for workspace discovery utilities."""

from pathlib import Path

from mkcv.config.workspace import find_workspace_root, is_workspace


class TestFindWorkspaceRoot:
    """Tests for find_workspace_root function."""

    def test_returns_none_when_no_workspace(self, tmp_path: Path) -> None:
        result = find_workspace_root(start=tmp_path)
        assert result is None

    def test_finds_workspace_in_current_dir(self, tmp_path: Path) -> None:
        (tmp_path / "mkcv.toml").write_text("[workspace]\n")
        result = find_workspace_root(start=tmp_path)
        assert result == tmp_path.resolve()

    def test_finds_workspace_in_parent_dir(self, tmp_path: Path) -> None:
        (tmp_path / "mkcv.toml").write_text("[workspace]\n")
        child = tmp_path / "subdir" / "deep"
        child.mkdir(parents=True)
        result = find_workspace_root(start=child)
        assert result == tmp_path.resolve()

    def test_does_not_find_workspace_in_sibling(self, tmp_path: Path) -> None:
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        (sibling / "mkcv.toml").write_text("[workspace]\n")

        search_dir = tmp_path / "other"
        search_dir.mkdir()
        result = find_workspace_root(start=search_dir)
        assert result is None


class TestIsWorkspace:
    """Tests for is_workspace function."""

    def test_returns_true_for_workspace_dir(self, tmp_path: Path) -> None:
        (tmp_path / "mkcv.toml").write_text("[workspace]\n")
        assert is_workspace(tmp_path) is True

    def test_returns_false_for_non_workspace_dir(self, tmp_path: Path) -> None:
        assert is_workspace(tmp_path) is False

    def test_returns_false_for_dir_with_other_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool]\n")
        assert is_workspace(tmp_path) is False
