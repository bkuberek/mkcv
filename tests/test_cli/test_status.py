"""Tests for the mkcv status command."""

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import tomli_w

from mkcv.cli.commands.status import (
    _build_application_table,
    _print_no_workspace,
    _read_application_metadata,
    status_command,
)
from mkcv.core.models.application_metadata import ApplicationMetadata

_FIND_WORKSPACE = "mkcv.cli.commands.status.find_workspace_root"


def _write_application_toml(app_dir: Path, metadata: ApplicationMetadata) -> None:
    """Write an application.toml file for testing."""
    data = {
        "application": {
            "company": metadata.company,
            "position": metadata.position,
            "date": metadata.date.isoformat(),
            "status": metadata.status,
            "url": metadata.url or "",
            "created_at": metadata.created_at.isoformat(),
        },
    }
    toml_path = app_dir / "application.toml"
    with toml_path.open("wb") as f:
        tomli_w.dump(data, f)


def _make_application(
    workspace_root: Path,
    company: str,
    position: str,
    *,
    has_yaml: bool = False,
    has_pdf: bool = False,
    status: str = "draft",
) -> Path:
    """Create a fake application directory with optional artifacts."""
    app_dir = workspace_root / "applications" / company / position
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / ".mkcv").mkdir(exist_ok=True)

    metadata = ApplicationMetadata(
        company=company,
        position=position,
        date=date(2025, 6, 15),
        status=status,
        created_at=datetime(2025, 6, 15, 10, 0, 0, tzinfo=UTC),
    )
    _write_application_toml(app_dir, metadata)

    if has_yaml:
        (app_dir / "resume.yaml").write_text("cv: {}")
    if has_pdf:
        (app_dir / "resume.pdf").write_bytes(b"%PDF-fake")

    return app_dir


class TestStatusWithWorkspace:
    """Tests for status command when a workspace is found."""

    def test_status_shows_workspace_root(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Root:" in captured.out
        assert workspace_dir.name in captured.out

    def test_status_shows_config_path(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "mkcv.toml" in captured.out

    def test_status_shows_knowledge_base_exists(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "exists" in captured.out

    def test_status_shows_knowledge_base_missing(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        kb_path = workspace_dir / "knowledge-base" / "career.md"
        kb_path.unlink()

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "missing" in captured.out

    def test_status_shows_application_count(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        _make_application(workspace_dir, "acme", "2025-06-engineer")
        _make_application(workspace_dir, "globex", "2025-06-developer")

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "2" in captured.out


class TestStatusNoWorkspace:
    """Tests for status command when no workspace is found."""

    def test_status_suggests_init(self, capsys: object) -> None:
        with patch(_FIND_WORKSPACE, return_value=None):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "No mkcv workspace found" in captured.out

    def test_status_shows_init_command(self, capsys: object) -> None:
        with patch(_FIND_WORKSPACE, return_value=None):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "mkcv init" in captured.out


class TestStatusApplicationListing:
    """Tests for the application listing in status output."""

    def test_status_lists_applications(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        _make_application(workspace_dir, "acme", "2025-06-engineer")

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "acme" in captured.out
        assert "2025-06-engineer" in captured.out

    def test_status_shows_yaml_check(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        _make_application(
            workspace_dir,
            "acme",
            "2025-06-engineer",
            has_yaml=True,
        )

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "\u2713" in captured.out

    def test_status_shows_pdf_check(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        _make_application(
            workspace_dir,
            "acme",
            "2025-06-engineer",
            has_pdf=True,
        )

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "\u2713" in captured.out

    def test_status_shows_most_recent_application(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        _make_application(workspace_dir, "acme", "2025-03-old-role")
        _make_application(workspace_dir, "globex", "2025-06-new-role")

        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Most recent" in captured.out


class TestStatusEmptyWorkspace:
    """Tests for status with a workspace but no applications."""

    def test_status_shows_zero_applications(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "0" in captured.out

    def test_status_suggests_generate(
        self,
        workspace_dir: Path,
        capsys: object,
    ) -> None:
        with patch(_FIND_WORKSPACE, return_value=workspace_dir):
            status_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "mkcv generate" in captured.out


class TestBuildApplicationTable:
    """Tests for the _build_application_table helper."""

    def test_table_has_eight_columns(self, workspace_dir: Path) -> None:
        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        table = _build_application_table([app_dir])
        assert len(table.columns) == 8

    def test_table_has_correct_row_count(self, workspace_dir: Path) -> None:
        app1 = _make_application(workspace_dir, "acme", "2025-06-engineer")
        app2 = _make_application(workspace_dir, "globex", "2025-06-dev")
        table = _build_application_table([app1, app2])
        assert table.row_count == 2


class TestDetectResumeArtifacts:
    """Tests for _detect_resume_artifacts helper."""

    def test_detects_resume_in_versioned_layout(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _detect_resume_artifacts

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        version_dir = app_dir / "resumes" / "v1"
        version_dir.mkdir(parents=True)
        (version_dir / "resume.yaml").write_text("cv: {}")
        (version_dir / "resume.pdf").write_bytes(b"%PDF")

        has_yaml, has_pdf = _detect_resume_artifacts(app_dir)
        assert has_yaml is True
        assert has_pdf is True

    def test_detects_resume_in_old_layout(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _detect_resume_artifacts

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        (app_dir / "resume.yaml").write_text("cv: {}")
        (app_dir / "resume.pdf").write_bytes(b"%PDF")

        has_yaml, has_pdf = _detect_resume_artifacts(app_dir)
        assert has_yaml is True
        assert has_pdf is True

    def test_no_artifacts_detected(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _detect_resume_artifacts

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")

        has_yaml, has_pdf = _detect_resume_artifacts(app_dir)
        assert has_yaml is False
        assert has_pdf is False


class TestCountVersions:
    """Tests for _count_versions helper."""

    def test_counts_version_directories(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _count_versions

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        resumes_dir = app_dir / "resumes"
        resumes_dir.mkdir()
        (resumes_dir / "v1").mkdir()
        (resumes_dir / "v2").mkdir()
        (resumes_dir / "v3").mkdir()

        assert _count_versions(resumes_dir) == 3

    def test_returns_zero_for_empty_dir(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _count_versions

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        resumes_dir = app_dir / "resumes"
        resumes_dir.mkdir()

        assert _count_versions(resumes_dir) == 0

    def test_returns_zero_for_nonexistent_dir(self, tmp_path: Path) -> None:
        from mkcv.cli.commands.status import _count_versions

        assert _count_versions(tmp_path / "nonexistent") == 0

    def test_ignores_non_version_directories(self, workspace_dir: Path) -> None:
        from mkcv.cli.commands.status import _count_versions

        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        resumes_dir = app_dir / "resumes"
        resumes_dir.mkdir()
        (resumes_dir / "v1").mkdir()
        (resumes_dir / ".mkcv").mkdir()
        (resumes_dir / "old-stuff").mkdir()

        assert _count_versions(resumes_dir) == 1


class TestReadApplicationMetadata:
    """Tests for _read_application_metadata."""

    def test_reads_valid_toml(self, workspace_dir: Path) -> None:
        app_dir = _make_application(workspace_dir, "acme", "2025-06-engineer")
        metadata = _read_application_metadata(app_dir)
        assert metadata is not None
        assert metadata.company == "acme"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert _read_application_metadata(tmp_path) is None

    def test_returns_none_for_malformed_toml(self, tmp_path: Path) -> None:
        toml_path = tmp_path / "application.toml"
        toml_path.write_text("not valid toml {{{{", encoding="utf-8")
        assert _read_application_metadata(tmp_path) is None


class TestPrintNoWorkspace:
    """Tests for _print_no_workspace helper."""

    def test_contains_no_workspace_message(self, capsys: object) -> None:
        _print_no_workspace()
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "No mkcv workspace found" in captured.out
