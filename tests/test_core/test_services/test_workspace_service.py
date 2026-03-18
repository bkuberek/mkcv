"""Tests for core service stubs."""

from pathlib import Path

import pytest

from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.workspace import WorkspaceService


class TestWorkspaceService:
    """Tests for WorkspaceService stub methods."""

    def test_init_workspace_raises_not_implemented(self, tmp_path: Path) -> None:
        svc = WorkspaceService()
        with pytest.raises(NotImplementedError):
            svc.init_workspace(tmp_path)

    def test_setup_application_raises_not_implemented(self, tmp_path: Path) -> None:
        svc = WorkspaceService()
        jd_path = tmp_path / "jd.txt"
        jd_path.write_text("test jd")
        with pytest.raises(NotImplementedError):
            svc.setup_application(
                workspace_root=tmp_path,
                company="DeepL",
                position="Staff Engineer",
                jd_path=jd_path,
            )


class TestPipelineService:
    """Tests for PipelineService stub methods."""

    async def test_generate_raises_not_implemented(self, tmp_path: Path) -> None:
        from mkcv.adapters.filesystem.artifact_store import (
            FileSystemArtifactStore,
        )
        from mkcv.adapters.filesystem.prompt_loader import (
            FileSystemPromptLoader,
        )
        from mkcv.adapters.llm.stub import StubLLMAdapter

        svc = PipelineService(
            llm=StubLLMAdapter(),
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )
        jd = tmp_path / "jd.txt"
        kb = tmp_path / "kb.md"
        jd.write_text("test jd")
        kb.write_text("test kb")

        with pytest.raises(NotImplementedError):
            await svc.generate(
                jd_path=jd,
                kb_path=kb,
                output_dir=tmp_path / "output",
            )
