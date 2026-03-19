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
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.render import RenderService
from mkcv.core.services.validation import ValidationService
from mkcv.core.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)

_PROVIDER_ENV_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_STAGE_CONFIG_KEYS: dict[int, str] = {
    1: "analyze",
    2: "select",
    3: "tailor",
    4: "structure",
    5: "review",
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


def _resolve_stage_configs(
    config: Configuration,
) -> dict[int, StageConfig]:
    """Read per-stage LLM configuration from settings.

    Args:
        config: Application configuration.

    Returns:
        Dict mapping stage number (1-5) to StageConfig.
    """
    stage_configs: dict[int, StageConfig] = {}

    for stage_num, key in _STAGE_CONFIG_KEYS.items():
        try:
            stage_section = getattr(config.pipeline.stages, key)
            provider = str(getattr(stage_section, "provider", "anthropic"))
            model = str(getattr(stage_section, "model", "claude-sonnet-4-20250514"))
            temperature = float(getattr(stage_section, "temperature", 0.3))
        except AttributeError:
            provider = "anthropic"
            model = "claude-sonnet-4-20250514"
            temperature = 0.3

        stage_configs[stage_num] = StageConfig(
            provider=provider,
            model=model,
            temperature=temperature,
        )

    return stage_configs


def _create_llm_adapter(
    provider: str,
    config: Configuration,
) -> LLMPort:
    """Create an LLM adapter for a specific provider.

    Args:
        provider: Provider name ("anthropic", "openai", "stub").
        config: Application configuration.

    Returns:
        An object implementing LLMPort.
    """
    if provider == "stub":
        from mkcv.adapters.llm.stub import StubLLMAdapter

        return StubLLMAdapter()

    api_key = _resolve_api_key(provider, config)

    if not api_key:
        logger.warning(
            "No API key for provider '%s'; falling back to stub.",
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


def _create_providers(
    config: Configuration,
    stage_configs: dict[int, StageConfig],
) -> dict[str, LLMPort]:
    """Create one LLM adapter per unique provider in the stage configs.

    Args:
        config: Application configuration.
        stage_configs: Per-stage LLM configuration.

    Returns:
        Dict mapping provider name to LLMPort adapter.
    """
    unique_providers = {sc.provider for sc in stage_configs.values()}
    providers: dict[str, LLMPort] = {}

    for provider_name in unique_providers:
        providers[provider_name] = _create_llm_adapter(provider_name, config)

    return providers


def create_pipeline_service(config: Configuration) -> PipelineService:
    """Create a fully-wired PipelineService.

    Reads per-stage provider/model/temperature from config and
    creates one LLM adapter per unique provider.

    Args:
        config: Application configuration.

    Returns:
        PipelineService with per-stage LLM adapters.
    """
    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    stage_configs = _resolve_stage_configs(config)
    providers = _create_providers(config, stage_configs)

    return PipelineService(
        providers=providers,
        prompts=prompt_loader,
        artifacts=artifact_store,
        stage_configs=stage_configs,
    )


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

    # Validation uses the analyze stage provider for JD analysis
    # and the review stage provider for resume review
    stage_configs = _resolve_stage_configs(config)
    analyze_provider = stage_configs[1].provider
    llm = _create_llm_adapter(analyze_provider, config)

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
