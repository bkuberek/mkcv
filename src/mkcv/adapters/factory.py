"""Factory functions for dependency injection wiring.

These functions create fully-wired service instances by assembling
the appropriate adapters based on configuration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from mkcv.config.configuration import Configuration
    from mkcv.core.models.model_report import ModelReport
    from mkcv.core.models.stage_config import StageConfig
    from mkcv.core.ports.llm import LLMPort
    from mkcv.core.services.batch_render import BatchRenderService
    from mkcv.core.services.kb_generation_service import KBGenerationService
    from mkcv.core.services.regeneration import RegenerationService

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.config_bootstrap import ConfigBootstrap
from mkcv.adapters.filesystem.pdf_reader import PyPdfReader
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.resolution_request import ResolutionRequest
from mkcv.adapters.llm.stage_resolver import StageResolver
from mkcv.adapters.renderers.rendercv import RenderCVAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.cover_letter_design import CoverLetterDesign
from mkcv.core.models.entry_layout import EntryLayout
from mkcv.core.models.header_layout import HeaderLayout
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.page_layout import PageLayout
from mkcv.core.models.profile_preset import resolve_preset
from mkcv.core.models.resume_design import ResumeDesign
from mkcv.core.models.section_title_layout import SectionTitleLayout
from mkcv.core.models.stage_key import (
    COVER_LETTER_STAGES,
    PIPELINE_STAGES,
    StageKey,
)
from mkcv.core.models.typography_layout import TypographyLayout
from mkcv.core.services.cover_letter import CoverLetterService
from mkcv.core.services.model_advisor import ModelAdvisor
from mkcv.core.services.pipeline import PipelineService
from mkcv.core.services.render import RenderService
from mkcv.core.services.validation import ValidationService
from mkcv.core.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)


def _registry(config: Configuration) -> ProviderRegistry:
    """Build the provider registry for the current configuration.

    Built on every call, not cached: configuration can change between
    commands (and between tests).

    Raises:
        ConfigurationError: If the provider or model-catalog settings are invalid.
    """
    return ProviderRegistry.from_config(config, load_model_catalog(config))


def create_provider_registry(config: Configuration) -> ProviderRegistry:
    """Return the provider registry for ``config``.

    Lets the CLI list providers and the model catalog (built-in entries plus
    the user's ``[[default.model_catalog]]`` overrides).

    Raises:
        ConfigurationError: If the provider or model-catalog settings are invalid.
    """
    return _registry(config)


def _create_llm_adapter(
    provider: str,
    config: Configuration,
    *,
    with_retry: bool = True,
) -> LLMPort:
    """Create an LLM adapter for a specific provider.

    Args:
        provider: Provider name, built in or defined under
            ``[default.providers.<name>]``.
        config: Application configuration.
        with_retry: Wrap with exponential backoff retry (default True).

    Returns:
        An object implementing LLMPort.

    Raises:
        ConfigurationError: If the provider is unknown or misconfigured.
    """
    return _registry(config).create_adapter(provider, with_retry=with_retry)


def _create_providers(
    config: Configuration,
    stage_configs: dict[int, StageConfig],
    registry: ProviderRegistry | None = None,
) -> dict[str, LLMPort]:
    """Create one LLM adapter per unique provider in the stage configs.

    Args:
        config: Application configuration.
        stage_configs: Per-stage LLM configuration.
        registry: Provider registry to create adapters from; built from
            ``config`` when omitted.

    Returns:
        Dict mapping provider name to LLMPort adapter.
    """
    registry = registry or _registry(config)
    unique_providers = {sc.provider for sc in stage_configs.values()}
    return {name: registry.create_adapter(name) for name in unique_providers}


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
    model_profile: str | None = None,
    theme: str = "sb2nov",
) -> PipelineService:
    """Create a fully-wired PipelineService.

    The preset sets content density; each stage's provider, model, and
    temperature come from the stage resolver (command-line flags, then
    per-stage config, then the model profile). One LLM adapter is created per
    unique provider.

    Args:
        config: Application configuration.
        preset_name: Preset or legacy profile name.
        provider_override: When set, run every stage on this provider.
        model_profile: When set, run every stage on this model profile.
        theme: Resolved theme name.

    Returns:
        PipelineService with per-stage LLM adapters.

    Raises:
        ConfigurationError: If a stage cannot be resolved.
    """
    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        PIPELINE_STAGES,
        ResolutionRequest(
            preset_name=preset_name,
            model_profile=model_profile,
            provider_override=provider_override,
        ),
    )
    return _assemble_pipeline_service(
        config,
        registry,
        resolved.pipeline_stage_configs(),
        preset_name=preset_name,
        theme=theme,
    )


def create_pipeline_service_for_stage_configs(
    config: Configuration,
    stage_configs: dict[int, StageConfig],
    *,
    preset_name: str = "standard",
    theme: str = "sb2nov",
) -> PipelineService:
    """Create a PipelineService that runs exactly the given stage configs.

    Nothing is resolved: no profile, per-stage config, or command-line flag
    changes which provider or model a stage uses. The eval harness uses this
    to pin every stage to the model under evaluation. A new service creates
    its own LLM adapters, so concurrent services never share token usage.

    Args:
        config: Application configuration (providers, keys, catalog).
        stage_configs: Provider, model, and temperature for stages 1 to 5.
        preset_name: Preset or legacy profile name (content density only).
        theme: Resolved theme name.

    Returns:
        PipelineService with one LLM adapter per provider in ``stage_configs``.

    Raises:
        ConfigurationError: If a provider is unknown or the provider or
            model-catalog settings are invalid.
    """
    return _assemble_pipeline_service(
        config,
        _registry(config),
        stage_configs,
        preset_name=preset_name,
        theme=theme,
    )


def _assemble_pipeline_service(
    config: Configuration,
    registry: ProviderRegistry,
    stage_configs: dict[int, StageConfig],
    *,
    preset_name: str,
    theme: str,
) -> PipelineService:
    """Wire a PipelineService from already-decided stage configs."""
    return PipelineService(
        providers=_create_providers(config, stage_configs, registry),
        prompts=_create_prompt_loader(config),
        artifacts=FileSystemArtifactStore(),
        stage_configs=stage_configs,
        preset=resolve_preset(preset_name),
        resume_design=_build_resume_design(config, theme),
        catalog=registry.catalog,
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

    Validation resolves its own ``validate`` stage rather than borrowing the
    analyze stage's provider.

    Args:
        config: Application configuration.

    Returns:
        ValidationService with LLM and prompt adapters connected.

    Raises:
        ConfigurationError: If the validate stage cannot be resolved.
    """
    prompt_loader = _create_prompt_loader(config)
    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        (StageKey.VALIDATE,), ResolutionRequest()
    )
    assignment = resolved.assignments[StageKey.VALIDATE]

    return ValidationService(
        llm=registry.create_adapter(assignment.provider),
        prompts=prompt_loader,
        pdf_reader=PyPdfReader(),
        model=assignment.model,
        temperature=assignment.temperature,
    )


def create_config_bootstrap() -> ConfigBootstrap:
    """Create the writer of the first-run config files.

    Returns:
        ConfigBootstrap that honours ``MKCV_NO_USER_CONFIG``.
    """
    return ConfigBootstrap()


def create_workspace_service() -> WorkspaceService:
    """Create a fully-wired WorkspaceService.

    Returns:
        WorkspaceService with WorkspaceManager adapter connected.
    """
    manager = WorkspaceManager()
    return WorkspaceService(workspace=manager)


_COVER_LETTER_STAGE_NUMBERS: dict[StageKey, int] = {
    StageKey.COVER_LETTER_GENERATE: 1,
    StageKey.COVER_LETTER_REVIEW: 2,
}


def create_cover_letter_service(
    config: Configuration,
    *,
    provider_override: str | None = None,
    model_profile: str | None = None,
    preset_name: str = "default",
) -> CoverLetterService:
    """Create a fully-wired CoverLetterService.

    Args:
        config: Application configuration.
        provider_override: Run both cover letter stages on this provider.
        model_profile: Run both cover letter stages on this model profile.
        preset_name: Preset or legacy profile name (selects the economy
            variant of a profile for economy presets).

    Returns:
        CoverLetterService with LLM, prompt, artifact, and renderer adapters.

    Raises:
        ConfigurationError: If a stage cannot be resolved.
    """
    from mkcv.adapters.renderers.typst_cover_letter import (
        TypstCoverLetterRenderer,
    )

    prompt_loader = _create_prompt_loader(config)
    artifact_store = FileSystemArtifactStore()
    renderer = TypstCoverLetterRenderer()
    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        COVER_LETTER_STAGES,
        ResolutionRequest(
            preset_name=preset_name,
            model_profile=model_profile,
            provider_override=provider_override,
        ),
    )
    stage_configs = {
        number: resolved.assignments[stage].to_stage_config()
        for stage, number in _COVER_LETTER_STAGE_NUMBERS.items()
    }
    providers = _create_providers(config, stage_configs, registry)
    design = _build_cover_letter_design(config)

    return CoverLetterService(
        providers=providers,
        prompts=prompt_loader,
        artifacts=artifact_store,
        renderer=renderer,
        stage_configs=stage_configs,
        design=design,
        catalog=registry.catalog,
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


def create_regeneration_service(
    config: Configuration,
    preset_name: str = "default",
    *,
    provider_override: str | None = None,
    model_profile: str | None = None,
) -> RegenerationService:
    """Create a fully-wired RegenerationService.

    Uses the tailor stage's configuration since regeneration is
    fundamentally the same operation as the tailor stage, just
    scoped to one section.

    Args:
        config: Application configuration.
        preset_name: Preset or legacy profile name.
        provider_override: When set, run on this provider.
        model_profile: When set, use this model profile's tailor model.

    Returns:
        RegenerationService with LLM and prompt adapters connected.

    Raises:
        ConfigurationError: If the tailor stage cannot be resolved.
    """
    from mkcv.core.services.regeneration import RegenerationService

    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        (StageKey.TAILOR,),
        ResolutionRequest(
            preset_name=preset_name,
            model_profile=model_profile,
            provider_override=provider_override,
        ),
    )
    tailor = resolved.assignments[StageKey.TAILOR]

    return RegenerationService(
        llm=registry.create_adapter(tailor.provider),
        prompts=_create_prompt_loader(config),
        model=tailor.model,
        temperature=tailor.temperature,
    )


def create_model_report(
    config: Configuration,
    *,
    preset_name: str = "default",
    model_profile: str | None = None,
    provider_override: str | None = None,
    include_pipeline: bool = True,
    include_cover_letter: bool = False,
    extra_stages: Sequence[StageKey] = (),
) -> ModelReport:
    """Report which model every requested stage will use, with warnings.

    Resolves the stages exactly as the matching ``create_*`` functions do, so
    the report describes what a run would use. Nothing is called on a provider.

    Args:
        config: Application configuration.
        preset_name: Preset or legacy profile name.
        model_profile: ``--model-profile`` value, if given.
        provider_override: ``--provider`` value, if given.
        include_pipeline: Include the five resume pipeline stages.
        include_cover_letter: Include the two cover letter stages.
        extra_stages: Further stages to include (for example KB and validate).

    Returns:
        A ``ModelReport`` with per-stage advice, provider-level warnings first,
        and a cost estimate.

    Raises:
        ConfigurationError: If a stage cannot be resolved.
    """
    stages: list[StageKey] = []
    if include_pipeline:
        stages.extend(PIPELINE_STAGES)
    if include_cover_letter:
        stages.extend(COVER_LETTER_STAGES)
    stages.extend(extra_stages)
    ordered = tuple(dict.fromkeys(stages))

    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        ordered,
        ResolutionRequest(
            preset_name=preset_name,
            model_profile=model_profile,
            provider_override=provider_override,
        ),
    )
    assignments = [resolved.assignments[stage] for stage in ordered]
    providers = tuple(dict.fromkeys(a.provider for a in assignments))

    return ModelAdvisor(registry.catalog).advise(
        assignments,
        profile=resolved.profile,
        profile_source=resolved.profile_source,
        preset_name=resolved.preset_name,
        provider_warnings=[
            _missing_key_warning(registry, name)
            for name in providers
            if not registry.has_credentials(name)
        ],
        provider_defaults={name: registry.defaults_for(name) for name in providers},
    )


def _missing_key_warning(registry: ProviderRegistry, provider: str) -> ModelWarning:
    """Build the warning for a provider whose credentials cannot be found."""
    hint = registry.credential_hint(provider)
    found = (
        f"no Application Default Credentials found ({hint})"
        if registry.uses_vertex(provider)
        else f"no API key found (set {hint})"
    )
    return ModelWarning(
        kind=ModelWarningKind.MISSING_API_KEY,
        stage=None,
        provider=provider,
        model=None,
        message=(
            f"{provider}: {found}; a run that uses it stops with a configuration error."
        ),
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


_DEFAULT_KB_MAX_TOKENS = 8192
_DEFAULT_KB_CHUNK_THRESHOLD = 100000


def create_kb_generation_service(
    config: Configuration,
    *,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> KBGenerationService:
    """Create a fully-wired KBGenerationService.

    The provider, model, and temperature come from the ``kb`` stage;
    ``max_tokens`` and ``chunk_threshold`` are read from the ``[kb]`` section.

    Args:
        config: Application configuration.
        provider_override: When set, run on this provider.
        model_override: When set, use this model.

    Returns:
        KBGenerationService with all dependencies wired.

    Raises:
        ConfigurationError: If the stage cannot be resolved or a limit is
            not an integer.
    """
    from mkcv.adapters.filesystem.document_reader import MultiFormatDocumentReader
    from mkcv.core.services.kb_generation_service import KBGenerationService

    registry = _registry(config)
    resolved = StageResolver(config, registry).resolve(
        (StageKey.KB,),
        ResolutionRequest(
            provider_override=provider_override, model_override=model_override
        ),
    )
    assignment = resolved.assignments[StageKey.KB]
    kb_section = config.get("kb") or {}

    return KBGenerationService(
        document_reader=MultiFormatDocumentReader(),
        llm=registry.create_adapter(assignment.provider),
        prompts=_create_prompt_loader(config),
        model=assignment.model,
        temperature=assignment.temperature,
        max_tokens=_integer_setting(kb_section, "max_tokens", _DEFAULT_KB_MAX_TOKENS),
        chunk_threshold=_integer_setting(
            kb_section, "chunk_threshold", _DEFAULT_KB_CHUNK_THRESHOLD
        ),
    )


def _integer_setting(section: Mapping[str, Any], key: str, default: int) -> int:
    """Read an integer from the ``[kb]`` section, falling back to ``default``."""
    value = section.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{key} in [default.kb] must be an integer") from None
