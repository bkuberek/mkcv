"""Factory functions for dependency injection wiring.

These functions create fully-wired service instances by assembling
the appropriate adapters based on configuration.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from mkcv.config.configuration import Configuration
    from mkcv.core.ports.llm import LLMPort

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.renderers.rendercv import RenderCVAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.render import RenderService
from mkcv.core.services.validation import ValidationService
from mkcv.core.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)

_PROVIDER_ENV_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _resolve_api_key(provider: str, config: Configuration) -> str | None:
    """Resolve the API key for a provider from config or environment.

    Args:
        provider: Provider name (e.g. "anthropic", "openai").
        config: Application configuration.

    Returns:
        The API key string, or None if not found.
    """
    # Try config first: config.providers.<provider>.api_key
    try:
        providers_section = getattr(config, "providers", None)
        if providers_section is not None:
            provider_section = getattr(providers_section, provider, None)
            if provider_section is not None:
                api_key = getattr(provider_section, "api_key", None)
                if api_key:
                    return str(api_key)
    except (AttributeError, KeyError):
        pass

    # Fall back to environment variable
    env_key = _PROVIDER_ENV_KEYS.get(provider)
    if env_key:
        return os.environ.get(env_key)

    return None


def _resolve_provider_name(config: Configuration) -> str:
    """Read the default provider name from config.

    Reads from ``config.pipeline.stages.analyze.provider`` as the
    default provider for all LLM calls.

    Args:
        config: Application configuration.

    Returns:
        Provider name string (e.g. "anthropic", "openai", "stub").
    """
    try:
        return str(config.pipeline.stages.analyze.provider)
    except AttributeError:
        return "stub"


def _create_llm_adapter(config: Configuration) -> LLMPort:
    """Create the appropriate LLM adapter based on configuration.

    Provider selection logic:
        1. Read provider name from config (default: analyze stage provider).
        2. Resolve API key from config or environment.
        3. Instantiate the matching adapter.
        4. Fall back to StubLLMAdapter if no key is available for dev/test.

    Args:
        config: Application configuration.

    Returns:
        An object implementing LLMPort.

    Raises:
        AuthenticationError: If a real provider is selected but no API key
            is found and the provider is not "stub".
    """
    provider = _resolve_provider_name(config)

    if provider == "stub":
        from mkcv.adapters.llm.stub import StubLLMAdapter

        return StubLLMAdapter()

    api_key = _resolve_api_key(provider, config)

    if not api_key:
        logger.warning(
            "No API key found for provider '%s'; falling back to stub adapter.",
            provider,
        )
        from mkcv.adapters.llm.stub import StubLLMAdapter

        return StubLLMAdapter()

    if provider == "anthropic":
        from mkcv.adapters.llm.anthropic import AnthropicAdapter

        return AnthropicAdapter(api_key=api_key)

    if provider == "openai":
        from mkcv.adapters.llm.openai import OpenAIAdapter

        return OpenAIAdapter(api_key=api_key)

    raise AuthenticationError(
        f"Unknown LLM provider: '{provider}'",
        provider=provider,
    )


def create_pipeline_service(config: Configuration) -> PipelineService:
    """Create a fully-wired PipelineService.

    Args:
        config: Application configuration.

    Returns:
        PipelineService with all adapters connected.
    """
    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    llm = _create_llm_adapter(config)
    return PipelineService(llm=llm, prompts=prompt_loader, artifacts=artifact_store)


def create_render_service(config: Configuration) -> RenderService:
    """Create a fully-wired RenderService.

    Args:
        config: Application configuration.

    Returns:
        RenderService with renderer adapter connected.
    """
    renderer = RenderCVAdapter()
    return RenderService(renderer=renderer)


def create_validation_service(config: Configuration) -> ValidationService:
    """Create a fully-wired ValidationService.

    Args:
        config: Application configuration.

    Returns:
        ValidationService with LLM and prompt adapters connected.
    """
    prompt_loader = _create_prompt_loader(config)
    llm = _create_llm_adapter(config)
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
