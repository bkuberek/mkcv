"""Preset definitions for resume generation.

A preset controls content density (how much the resume says). Which models
write it is a separate choice made by the stage resolver; a preset only says
whether to prefer the economy variant of a model profile and, for the legacy
``budget`` preset, which provider to use.
"""

from enum import StrEnum

from pydantic import BaseModel


class ContentDensity(StrEnum):
    """Controls how much content the pipeline produces."""

    CONCISE = "concise"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class Preset(BaseModel):
    """A named preset that controls content density.

    ``economy`` asks the stage resolver for the economy variant of a model
    profile. ``provider`` pins every stage to one provider (the legacy
    ``budget`` preset pins ``ollama``).
    """

    name: str
    description: str
    density: ContentDensity
    page_budget: str
    max_roles: int
    max_bullets_primary: int
    max_bullets_secondary: int
    include_earlier_experience: bool
    max_tokens: int = 8192
    economy: bool = False
    provider: str | None = None


BUILT_IN_PRESETS: dict[str, Preset] = {
    "concise": Preset(
        name="concise",
        description="1-page resume with highlights only (economy models)",
        density=ContentDensity.CONCISE,
        page_budget="1",
        max_roles=3,
        max_bullets_primary=4,
        max_bullets_secondary=2,
        include_earlier_experience=False,
        economy=True,
    ),
    "standard": Preset(
        name="standard",
        description="1-2 page balanced resume (recommended models)",
        density=ContentDensity.STANDARD,
        page_budget="1-2",
        max_roles=4,
        max_bullets_primary=5,
        max_bullets_secondary=3,
        include_earlier_experience=True,
    ),
    "comprehensive": Preset(
        name="comprehensive",
        description="2+ page resume with full career detail (recommended models)",
        density=ContentDensity.COMPREHENSIVE,
        page_budget="2+",
        max_roles=6,
        max_bullets_primary=7,
        max_bullets_secondary=5,
        include_earlier_experience=True,
        max_tokens=16384,
    ),
}

VALID_PRESET_NAMES: frozenset[str] = frozenset(BUILT_IN_PRESETS.keys())

# Backward compatibility: map old profile names to preset names.
_LEGACY_PROFILE_MAP: dict[str, str] = {
    "budget": "concise",
    "premium": "standard",
}


def _build_budget_preset() -> Preset:
    """Build the legacy 'budget' preset: concise density on local Ollama models."""
    concise = BUILT_IN_PRESETS["concise"]
    return concise.model_copy(
        update={
            "name": "budget",
            "description": "Concise resume on local Ollama models (legacy name)",
            "provider": "ollama",
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
