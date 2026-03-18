"""Factory functions for dependency injection wiring.

These functions create fully-wired service instances by assembling
the appropriate adapters based on configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from mkcv.config.configuration import Configuration

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.adapters.renderers.stub import StubRenderer
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.render import RenderService
from mkcv.core.services.validation import ValidationService
from mkcv.core.services.workspace import WorkspaceService


def create_pipeline_service(config: Configuration) -> PipelineService:
    """Create a fully-wired PipelineService.

    Args:
        config: Application configuration.

    Returns:
        PipelineService with all adapters connected.
    """
    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    llm = StubLLMAdapter()  # TODO: select based on config.pipeline.stages.*.provider
    return PipelineService(llm=llm, prompts=prompt_loader, artifacts=artifact_store)


def create_render_service(config: Configuration) -> RenderService:
    """Create a fully-wired RenderService.

    Args:
        config: Application configuration.

    Returns:
        RenderService with renderer adapter connected.
    """
    renderer = StubRenderer()  # TODO: select based on config
    return RenderService(renderer=renderer)


def create_validation_service(config: Configuration) -> ValidationService:
    """Create a fully-wired ValidationService.

    Args:
        config: Application configuration.

    Returns:
        ValidationService with LLM and prompt adapters connected.
    """
    prompt_loader = _create_prompt_loader(config)
    llm = StubLLMAdapter()
    return ValidationService(llm=llm, prompts=prompt_loader)


def create_workspace_manager() -> WorkspaceManager:
    """Create a WorkspaceManager instance.

    Returns:
        WorkspaceManager for filesystem operations.
    """
    return WorkspaceManager()


def create_workspace_service() -> WorkspaceService:
    """Create a WorkspaceService.

    Note: WorkspaceService currently has no dependencies.
    When it gains a WorkspaceManager dependency, wire it here.

    Returns:
        WorkspaceService instance.
    """
    return WorkspaceService()


def _create_prompt_loader(config: Configuration) -> FileSystemPromptLoader:
    """Create a prompt loader with optional user template overrides.

    Args:
        config: Application configuration.

    Returns:
        FileSystemPromptLoader configured with override paths.
    """
    override_dir: Path | None = None

    if config.in_workspace and config.workspace_root:
        templates_dir = config.workspace_root / config.workspace.templates_dir
        if templates_dir.is_dir():
            override_dir = templates_dir

    return FileSystemPromptLoader(override_dir=override_dir)
