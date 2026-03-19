"""Tests for WorkspaceService."""

from pathlib import Path

import pytest

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.exceptions.workspace import WorkspaceExistsError
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.workspace import WorkspaceService


class TestWorkspaceService:
    """Tests for WorkspaceService delegating to WorkspacePort."""

    def test_init_workspace_creates_directory(self, tmp_path: Path) -> None:
        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        target = tmp_path / "ws"
        result = svc.init_workspace(target)
        assert result == target.resolve()
        assert (target / "mkcv.toml").is_file()

    def test_init_workspace_raises_for_existing(self, tmp_path: Path) -> None:
        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        target = tmp_path / "ws"
        svc.init_workspace(target)
        with pytest.raises(WorkspaceExistsError):
            svc.init_workspace(target)

    def test_setup_application_creates_dir(self, tmp_path: Path) -> None:
        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)

        jd = tmp_path / "jd.txt"
        jd.write_text("test jd")

        app_dir = svc.setup_application(
            workspace_root=ws,
            company="DeepL",
            position="Staff Engineer",
            jd_source=jd,
        )
        assert app_dir.is_dir()
        assert (app_dir / "jd.txt").is_file()
        assert (app_dir / "application.toml").is_file()

    def test_list_applications_returns_dirs(self, tmp_path: Path) -> None:
        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)

        jd = tmp_path / "jd.txt"
        jd.write_text("test jd")

        svc.setup_application(
            workspace_root=ws,
            company="Acme",
            position="Engineer",
            jd_source=jd,
        )
        apps = svc.list_applications(ws)
        assert len(apps) == 1


class TestWorkspaceInitSafety:
    """Tests that init never overwrites existing user files."""

    def test_init_preserves_existing_career_md(self, tmp_path: Path) -> None:
        """Existing career.md must NEVER be overwritten."""
        ws = tmp_path / "ws"
        ws.mkdir()
        kb_dir = ws / "knowledge-base"
        kb_dir.mkdir()
        career = kb_dir / "career.md"
        career.write_text("My precious career data")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        assert career.read_text() == "My precious career data"

    def test_init_preserves_existing_voice_md(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        kb_dir = ws / "knowledge-base"
        kb_dir.mkdir()
        voice = kb_dir / "voice.md"
        voice.write_text("My custom voice")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        assert voice.read_text() == "My custom voice"

    def test_init_preserves_existing_gitignore(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        gitignore = ws / ".gitignore"
        gitignore.write_text("my-custom-ignore")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        assert gitignore.read_text() == "my-custom-ignore"

    def test_init_preserves_existing_readme(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        readme = ws / "README.md"
        readme.write_text("My custom readme")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        assert readme.read_text() == "My custom readme"

    def test_init_preserves_existing_applications(self, tmp_path: Path) -> None:
        """Existing application dirs must survive re-init."""
        ws = tmp_path / "ws"
        ws.mkdir()
        apps = ws / "applications" / "acme" / "2026-03-engineer"
        apps.mkdir(parents=True)
        jd = apps / "jd.txt"
        jd.write_text("important JD")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        assert jd.read_text() == "important JD"

    def test_init_creates_missing_files_alongside_existing(
        self, tmp_path: Path
    ) -> None:
        """When some files exist, init creates only the missing ones."""
        ws = tmp_path / "ws"
        ws.mkdir()
        kb_dir = ws / "knowledge-base"
        kb_dir.mkdir()
        career = kb_dir / "career.md"
        career.write_text("existing career")

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        svc.init_workspace(ws)

        # career.md preserved
        assert career.read_text() == "existing career"
        # voice.md created (was missing)
        assert (kb_dir / "voice.md").is_file()
        # mkcv.toml created
        assert (ws / "mkcv.toml").is_file()


class TestWorkspaceReadme:
    """Tests that the generated workspace README stays in sync."""

    def test_readme_created_on_init(self, tmp_path: Path) -> None:
        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)
        assert (ws / "README.md").is_file()

    def test_readme_contains_version(self, tmp_path: Path) -> None:
        from mkcv import __version__

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)
        content = (ws / "README.md").read_text()
        assert __version__ in content

    def test_readme_mentions_all_providers(self, tmp_path: Path) -> None:
        from mkcv.adapters.factory import _PROVIDER_ENV_KEYS

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)
        content = (ws / "README.md").read_text().lower()
        for provider in _PROVIDER_ENV_KEYS:
            assert provider in content, (
                f"Provider '{provider}' missing from workspace README"
            )

    def test_readme_mentions_all_commands(self, tmp_path: Path) -> None:
        from mkcv.cli.app import app as cli_app

        manager = WorkspaceManager()
        svc = WorkspaceService(workspace=manager)
        ws = tmp_path / "ws"
        svc.init_workspace(ws)
        content = (ws / "README.md").read_text()
        for name in cli_app._commands:
            if name.startswith("-"):
                continue
            assert f"mkcv {name}" in content, (
                f"Command 'mkcv {name}' missing from workspace README"
            )


class TestPipelineService:
    """Tests for PipelineService with unconfigured stub."""

    async def test_generate_raises_pipeline_stage_error_without_responses(
        self, tmp_path: Path
    ) -> None:
        from mkcv.adapters.filesystem.artifact_store import (
            FileSystemArtifactStore,
        )
        from mkcv.adapters.filesystem.prompt_loader import (
            FileSystemPromptLoader,
        )
        from mkcv.adapters.llm.stub import StubLLMAdapter

        svc = PipelineService(
            providers={"default": StubLLMAdapter()},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )
        jd = tmp_path / "jd.txt"
        kb = tmp_path / "kb.md"
        jd.write_text("test jd")
        kb.write_text("test kb")

        with pytest.raises(PipelineStageError):
            await svc.generate(
                jd_path=jd,
                kb_path=kb,
                output_dir=tmp_path / "output",
            )
