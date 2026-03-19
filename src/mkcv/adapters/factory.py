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
    from mkcv.core.services.batch_render import BatchRenderService

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.pdf_reader import PyPdfReader
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.renderers.rendercv import RenderCVAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.models.cover_letter_design import CoverLetterDesign
from mkcv.core.models.entry_layout import EntryLayout
from mkcv.core.models.header_layout import HeaderLayout
from mkcv.core.models.page_layout import PageLayout
from mkcv.core.models.profile_preset import Preset, resolve_preset
from mkcv.core.models.resume_design import ResumeDesign
from mkcv.core.models.section_title_layout import SectionTitleLayout
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.typography_layout import TypographyLayout
from mkcv.core.services.cover_letter import CoverLetterService
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.render import RenderService
from mkcv.core.services.validation import ValidationService
from mkcv.core.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)

_PROVIDER_ENV_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": "",  # Ollama doesn't require an API key
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


def _resolve_preset(
    name: str,
    config: Configuration,
) -> Preset | None:
    """Resolve a preset by name, applying provider overrides from config.

    Args:
        name: Preset or legacy profile name.
        config: Application configuration (for potential overrides).

    Returns:
        The resolved Preset, or None if name is "default" or unknown.
    """
    preset = resolve_preset(name)
    if preset is not None:
        logger.info("Using '%s' preset for all stages", preset.name)
    return preset


def _resolve_stage_configs(
    config: Configuration,
    preset_name: str = "default",
) -> dict[int, StageConfig]:
    """Read per-stage LLM configuration from settings or preset.

    When preset_name matches a built-in or legacy preset, the preset
    overrides config. When preset_name is "default", per-stage settings
    from config are used.

    Args:
        config: Application configuration.
        preset_name: Preset or legacy profile name.

    Returns:
        Dict mapping stage number (1-5) to StageConfig.
    """
    preset = _resolve_preset(preset_name, config)
    if preset is not None:
        return dict(preset.stage_configs)

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
    *,
    with_retry: bool = True,
) -> LLMPort:
    """Create an LLM adapter for a specific provider.

    Args:
        provider: Provider name ("anthropic", "openai", "stub").
        config: Application configuration.
        with_retry: Wrap with exponential backoff retry (default True).

    Returns:
        An object implementing LLMPort.
    """
    adapter: LLMPort

    if provider == "stub":
        from mkcv.adapters.llm.stub import StubLLMAdapter

        return StubLLMAdapter()

    if provider == "ollama":
        from mkcv.adapters.llm.ollama import OllamaAdapter

        inner: LLMPort = OllamaAdapter()
        if with_retry:
            inner = RetryingLLMAdapter(inner)
        return inner

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

        adapter = AnthropicAdapter(api_key=api_key)

    elif provider == "openai":
        from mkcv.adapters.llm.openai import OpenAIAdapter

        adapter = OpenAIAdapter(api_key=api_key)

    elif provider == "openrouter":
        from mkcv.adapters.llm.openai import OpenAIAdapter

        adapter = OpenAIAdapter(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    else:
        raise AuthenticationError(
            f"Unknown LLM provider: '{provider}'",
            provider=provider,
        )

    if with_retry:
        adapter = RetryingLLMAdapter(adapter)

    return adapter


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


def _build_resume_design(config: Configuration, theme: str) -> ResumeDesign:
    """Build a ResumeDesign from configuration settings.

    Reads both legacy flat fields and nested sub-model sections
    from config. Nested sections take precedence over flat fields.

    Args:
        config: Application configuration.
        theme: Resolved theme name.

    Returns:
        ResumeDesign populated from config rendering settings.
    """
    try:
        font = str(getattr(config.rendering, "font", "SourceSansPro"))
        font_size = str(getattr(config.rendering, "font_size", "10pt"))
        page_size = str(getattr(config.rendering, "page_size", "letterpaper"))
    except (AttributeError, TypeError):
        font = "SourceSansPro"
        font_size = "10pt"
        page_size = "letterpaper"

    colors: dict[str, str] = {"primary": "003366"}
    try:
        overrides = getattr(config.rendering, "overrides", None)
        if overrides is not None and not isinstance(overrides, str):
            primary = getattr(overrides, "primary_color", None)
            if primary and isinstance(primary, str):
                colors["primary"] = primary
            override_font = getattr(overrides, "font", None)
            if override_font and isinstance(override_font, str):
                font = override_font
            override_font_size = getattr(overrides, "font_size", None)
            if override_font_size and isinstance(override_font_size, str):
                font_size = override_font_size
            override_page_size = getattr(overrides, "page_size", None)
            if override_page_size and isinstance(override_page_size, str):
                page_size = override_page_size
    except (AttributeError, TypeError):
        pass

    # Read nested sub-model sections from config
    page = _read_page_layout(config)
    header = _read_header_layout(config)
    entries = _read_entry_layout(config)
    section_titles = _read_section_title_layout(config)
    typography = _read_typography_layout(config)

    try:
        return ResumeDesign(
            theme=theme,
            font=font,
            font_size=font_size,
            page_size=page_size,
            colors=colors,
            page=page,
            header=header,
            entries=entries,
            section_titles=section_titles,
            typography=typography,
        )
    except Exception:
        logger.warning(
            "Failed to build ResumeDesign from config; using defaults",
            exc_info=True,
        )
        return ResumeDesign(theme=theme)


def _read_sub_config(
    config: Configuration,
    section: str,
    fields: tuple[str, ...],
) -> dict[str, str]:
    """Read named fields from a nested config section.

    Returns a dict of non-None string field values.
    """
    result: dict[str, str] = {}
    try:
        rendering = getattr(config, "rendering", None)
        if rendering is None:
            return result
        sub = getattr(rendering, section, None)
        if sub is None or isinstance(sub, str):
            return result
        for field in fields:
            val = getattr(sub, field, None)
            if val is not None and isinstance(val, str) and val:
                result[field] = val
    except (AttributeError, TypeError):
        pass
    return result


def _read_page_layout(config: Configuration) -> PageLayout | None:
    """Read page layout from [rendering.page] config section."""
    fields = _read_sub_config(
        config, "page", ("top_margin", "bottom_margin", "left_margin", "right_margin")
    )
    return PageLayout(**fields) if fields else None


def _read_header_layout(config: Configuration) -> HeaderLayout | None:
    """Read header layout from [rendering.header] config section."""
    fields = _read_sub_config(
        config,
        "header",
        ("space_below_name", "space_below_headline", "space_below_connections"),
    )
    return HeaderLayout(**fields) if fields else None


def _read_entry_layout(config: Configuration) -> EntryLayout | None:
    """Read entry layout from [rendering.entries] config section."""
    fields = _read_sub_config(
        config,
        "entries",
        (
            "date_and_location_width",
            "left_and_right_margin",
            "horizontal_space_between_connections",
        ),
    )
    return EntryLayout(**fields) if fields else None


def _read_section_title_layout(config: Configuration) -> SectionTitleLayout | None:
    """Read section title layout from [rendering.section_titles] config."""
    fields = _read_sub_config(
        config, "section_titles", ("type", "space_above", "space_below")
    )
    return SectionTitleLayout(**fields) if fields else None


def _read_typography_layout(config: Configuration) -> TypographyLayout | None:
    """Read typography from [rendering.typography] config section."""
    fields = _read_sub_config(
        config,
        "typography",
        ("line_spacing", "alignment", "headline_size", "connections_size"),
    )
    return TypographyLayout(**fields) if fields else None


def _build_cover_letter_design(config: Configuration) -> CoverLetterDesign:
    """Build a CoverLetterDesign from configuration settings.

    Reads from [cover_letter.design] config section.

    Args:
        config: Application configuration.

    Returns:
        CoverLetterDesign populated from config, with model defaults
        for any missing values.
    """
    try:
        cl_section = getattr(config, "cover_letter", None)
        if cl_section is None:
            return CoverLetterDesign()
        design_section = getattr(cl_section, "design", None)
        if design_section is None or isinstance(design_section, str):
            return CoverLetterDesign()

        raw: dict[str, object] = {}
        for field_name in CoverLetterDesign.model_fields:
            val = getattr(design_section, field_name, None)
            if val is not None:
                raw[field_name] = val

        return CoverLetterDesign.model_validate(raw)
    except (AttributeError, TypeError):
        return CoverLetterDesign()


def create_pipeline_service(
    config: Configuration,
    preset_name: str = "default",
    *,
    provider_override: str | None = None,
    theme: str = "sb2nov",
) -> PipelineService:
    """Create a fully-wired PipelineService.

    Reads per-stage provider/model/temperature from config (or preset)
    and creates one LLM adapter per unique provider.

    Args:
        config: Application configuration.
        preset_name: Preset or legacy profile name.
        provider_override: When set, override the provider for all stages.

    Returns:
        PipelineService with per-stage LLM adapters.
    """
    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    preset = _resolve_preset(preset_name, config)
    stage_configs = (
        dict(preset.stage_configs)
        if preset is not None
        else _resolve_stage_configs(config, preset_name=preset_name)
    )

    if provider_override is not None:
        stage_configs = {
            num: StageConfig(
                provider=provider_override,
                model=sc.model,
                temperature=sc.temperature,
            )
            for num, sc in stage_configs.items()
        }

    providers = _create_providers(config, stage_configs)
    resume_design = _build_resume_design(config, theme)

    return PipelineService(
        providers=providers,
        prompts=prompt_loader,
        artifacts=artifact_store,
        stage_configs=stage_configs,
        preset=preset,
        resume_design=resume_design,
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

    pdf_reader = PyPdfReader()
    return ValidationService(llm=llm, prompts=prompt_loader, pdf_reader=pdf_reader)


def create_workspace_service() -> WorkspaceService:
    """Create a fully-wired WorkspaceService.

    Returns:
        WorkspaceService with WorkspaceManager adapter connected.
    """
    manager = WorkspaceManager()
    return WorkspaceService(workspace=manager)


_CL_STAGE_CONFIG_KEYS: dict[int, str] = {
    1: "generate",
    2: "review",
}


def _resolve_cl_stage_configs(
    config: Configuration,
) -> dict[int, StageConfig]:
    """Read cover letter stage configs from settings.

    Falls back to sensible defaults if ``[cover_letter.stages.*]``
    is not configured.

    Args:
        config: Application configuration.

    Returns:
        Dict mapping CL stage number (1-2) to StageConfig.
    """
    stage_configs: dict[int, StageConfig] = {}
    default_temps = {1: 0.6, 2: 0.2}

    for stage_num, key in _CL_STAGE_CONFIG_KEYS.items():
        try:
            cl_section = getattr(config, "cover_letter", None)
            if cl_section is not None:
                stages = getattr(cl_section, "stages", None)
                if stages is not None:
                    stage_section = getattr(stages, key)
                    provider = str(getattr(stage_section, "provider", "anthropic"))
                    model = str(
                        getattr(
                            stage_section,
                            "model",
                            "claude-sonnet-4-20250514",
                        )
                    )
                    temperature = float(
                        getattr(
                            stage_section,
                            "temperature",
                            default_temps[stage_num],
                        )
                    )
                    stage_configs[stage_num] = StageConfig(
                        provider=provider,
                        model=model,
                        temperature=temperature,
                    )
                    continue
        except AttributeError:
            pass

        # Default fallback
        stage_configs[stage_num] = StageConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=default_temps[stage_num],
        )

    return stage_configs


def create_cover_letter_service(
    config: Configuration,
    *,
    provider_override: str | None = None,
) -> CoverLetterService:
    """Create a fully-wired CoverLetterService.

    Args:
        config: Application configuration.
        provider_override: Override provider for all CL stages.

    Returns:
        CoverLetterService with LLM, prompt, artifact, and renderer adapters.
    """
    from mkcv.adapters.renderers.typst_cover_letter import (
        TypstCoverLetterRenderer,
    )

    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    renderer = TypstCoverLetterRenderer()
    stage_configs = _resolve_cl_stage_configs(config)

    if provider_override is not None:
        stage_configs = {
            num: StageConfig(
                provider=provider_override,
                model=sc.model,
                temperature=sc.temperature,
            )
            for num, sc in stage_configs.items()
        }

    providers = _create_providers(config, stage_configs)
    design = _build_cover_letter_design(config)

    return CoverLetterService(
        providers=providers,
        prompts=prompt_loader,
        artifacts=artifact_store,
        renderer=renderer,
        stage_configs=stage_configs,
        design=design,
    )


def create_batch_render_service(
    config: Configuration,
) -> BatchRenderService:
    """Create a fully-wired BatchRenderService.

    Args:
        config: Application configuration.

    Returns:
        BatchRenderService with RenderService and YamlPostProcessor.
    """
    from mkcv.core.services.batch_render import BatchRenderService
    from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

    render_service = create_render_service(config)
    postprocessor = YamlPostProcessor()
    return BatchRenderService(
        render_service=render_service,
        postprocessor=postprocessor,
    )


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
