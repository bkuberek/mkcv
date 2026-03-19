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
