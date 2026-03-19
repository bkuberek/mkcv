"""Preset definitions for resume generation.

Each preset controls both model selection (via stage_configs) and
content density parameters passed to prompt templates.
"""

from enum import StrEnum

from pydantic import BaseModel

from mkcv.core.models.stage_config import StageConfig


class ContentDensity(StrEnum):
    """Controls how much content the pipeline produces."""

    CONCISE = "concise"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class Preset(BaseModel):
    """A named preset that controls model selection and content density."""

    name: str
    description: str
    density: ContentDensity
    page_budget: str
    max_roles: int
    max_bullets_primary: int
    max_bullets_secondary: int
    include_earlier_experience: bool
    max_tokens: int = 8192
    stage_configs: dict[int, StageConfig]


_SONNET_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.2
    ),
    2: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.3
    ),
    3: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.5
    ),
    4: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.1
    ),
    5: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.3
    ),
}

_OPUS_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(
        provider="anthropic", model="claude-opus-4-20250514", temperature=0.2
    ),
    2: StageConfig(
        provider="anthropic", model="claude-opus-4-20250514", temperature=0.3
    ),
    3: StageConfig(
        provider="anthropic", model="claude-opus-4-20250514", temperature=0.5
    ),
    4: StageConfig(
        provider="anthropic", model="claude-opus-4-20250514", temperature=0.1
    ),
    5: StageConfig(
        provider="anthropic", model="claude-opus-4-20250514", temperature=0.3
    ),
}

_OLLAMA_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.2),
    2: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.3),
    3: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.5),
    4: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.1),
    5: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.3),
}

BUILT_IN_PRESETS: dict[str, Preset] = {
    "concise": Preset(
        name="concise",
        description="1-page resume with highlights only",
        density=ContentDensity.CONCISE,
        page_budget="1",
        max_roles=3,
        max_bullets_primary=4,
        max_bullets_secondary=2,
        include_earlier_experience=False,
        stage_configs=dict(_SONNET_STAGE_CONFIGS),
    ),
    "standard": Preset(
        name="standard",
        description="1-2 page balanced resume",
        density=ContentDensity.STANDARD,
        page_budget="1-2",
        max_roles=4,
        max_bullets_primary=5,
        max_bullets_secondary=3,
        include_earlier_experience=True,
        stage_configs=dict(_SONNET_STAGE_CONFIGS),
    ),
    "comprehensive": Preset(
        name="comprehensive",
        description="2+ page resume with full career detail",
        density=ContentDensity.COMPREHENSIVE,
        page_budget="2+",
        max_roles=6,
        max_bullets_primary=7,
        max_bullets_secondary=5,
        include_earlier_experience=True,
        max_tokens=16384,
        stage_configs=dict(_OPUS_STAGE_CONFIGS),
    ),
}

VALID_PRESET_NAMES: frozenset[str] = frozenset(BUILT_IN_PRESETS.keys())

# Backward compatibility: map old profile names to preset names.
_LEGACY_PROFILE_MAP: dict[str, str] = {
    "budget": "concise",
    "premium": "standard",
}


def _build_budget_preset() -> Preset:
    """Build a 'budget' preset: concise density with ollama models."""
    concise = BUILT_IN_PRESETS["concise"]
    return concise.model_copy(
        update={
            "name": "budget",
            "description": "Budget preset using local Ollama models",
            "stage_configs": dict(_OLLAMA_STAGE_CONFIGS),
        }
    )


# Include legacy presets so old profile names still resolve.
_LEGACY_PRESETS: dict[str, Preset] = {
    "budget": _build_budget_preset(),
    "premium": BUILT_IN_PRESETS["standard"],
}

# All valid profile names (new presets + legacy names + "default").
VALID_PROFILES: frozenset[str] = frozenset(
    {*BUILT_IN_PRESETS.keys(), *_LEGACY_PRESETS.keys(), "default"}
)


def resolve_preset(name: str) -> Preset | None:
    """Resolve a preset by name, supporting both new and legacy names.

    Args:
        name: Preset or legacy profile name.

    Returns:
        The resolved Preset, or None if the name is "default" or unknown.
    """
    if name in BUILT_IN_PRESETS:
        return BUILT_IN_PRESETS[name]
    if name in _LEGACY_PRESETS:
        return _LEGACY_PRESETS[name]
    return None
