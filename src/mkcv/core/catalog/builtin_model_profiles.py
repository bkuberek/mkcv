"""Built-in model profiles: recommended models per stage for each provider.

Every profile is provisional. The stage-to-model choices come from model
vendors' positioning and published prices (``docs/changes/multi-provider-
support/design.md`` section 12), not from measurements; an eval run replaces
the evidence and the models.

The ``anthropic`` and ``anthropic-economy`` rows reproduce the models mkcv
used before profiles existed, and ``local`` reproduces the legacy ``budget``
preset.
"""

from mkcv.core.models.model_profile import ModelProfile
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

_S = StageKey


def _stages(*models: str) -> dict[StageKey, str]:
    """Pair models with stages, in ``StageKey`` declaration order."""
    return dict(zip(StageKey, models, strict=True))


def _pipeline_stages(*models: str) -> dict[StageKey, str]:
    """Pair models with the five pipeline stages."""
    return dict(zip(PIPELINE_STAGES, models, strict=True))


BUILTIN_MODEL_PROFILES: dict[str, ModelProfile] = {
    profile.name: profile
    for profile in (
        ModelProfile(
            name="anthropic",
            description=(
                "Recommended Claude mix: Haiku for extraction, Opus for "
                "decisions and writing, Sonnet for YAML."
            ),
            provider="anthropic",
            stages=_stages(
                "claude-haiku-5-5",  # analyze
                "claude-opus-5-5",  # select
                "claude-opus-5-5",  # tailor
                "claude-sonnet-5-5",  # structure
                "claude-opus-5-5",  # review
                "claude-opus-5-5",  # cover_letter.generate
                "claude-haiku-5-5",  # cover_letter.review
                "claude-sonnet-5-5",  # kb
                "claude-sonnet-5-5",  # validate
            ),
        ),
        ModelProfile(
            name="anthropic-economy",
            description="Claude Haiku for every resume stage (fast, low cost).",
            provider="anthropic",
            economy=True,
            extends="anthropic",
            stages=_pipeline_stages(*("claude-haiku-5-5",) * 5),
        ),
        ModelProfile(
            name="openai",
            description=(
                "Recommended OpenAI mix: Luna for extraction, Astra for "
                "writing, Sol for decisions, Terra for YAML."
            ),
            provider="openai",
            stages=_stages(
                "gpt-6-luna",  # analyze
                "gpt-6.1-sol",  # select
                "gpt-6-astra",  # tailor
                "gpt-6.1-terra",  # structure
                "gpt-6.1-sol",  # review
                "gpt-6-astra",  # cover_letter.generate
                "gpt-6-luna",  # cover_letter.review
                "gpt-6.1-sol",  # kb
                "gpt-6.1-terra",  # validate
            ),
        ),
        ModelProfile(
            name="openai-economy",
            description="Low-cost OpenAI mix: Luna and Terra.",
            provider="openai",
            economy=True,
            extends="openai",
            stages=_pipeline_stages(
                "gpt-6-luna",  # analyze
                "gpt-6.1-terra",  # select
                "gpt-6.1-terra",  # tailor
                "gpt-6-luna",  # structure
                "gpt-6.1-terra",  # review
            ),
        ),
        ModelProfile(
            name="google",
            description=(
                "Recommended Gemini mix: Flash-Lite for extraction, Argon for "
                "decisions and writing, Flash for YAML."
            ),
            provider="google",
            stages=_stages(
                "gemini-3.5-flash-lite",  # analyze
                "gemini-4-argon",  # select
                "gemini-4-argon",  # tailor
                "gemini-3.8-flash",  # structure
                "gemini-4-argon",  # review
                "gemini-4-argon",  # cover_letter.generate
                "gemini-3.5-flash-lite",  # cover_letter.review
                "gemini-3.8-flash",  # kb
                "gemini-3.8-flash",  # validate
            ),
        ),
        ModelProfile(
            name="google-economy",
            description="Low-cost Gemini mix: Flash-Lite and Flash.",
            provider="google",
            economy=True,
            extends="google",
            stages=_pipeline_stages(
                "gemini-3.5-flash-lite",  # analyze
                "gemini-3.8-flash",  # select
                "gemini-3.8-flash",  # tailor
                "gemini-3.5-flash-lite",  # structure
                "gemini-3.8-flash",  # review
            ),
        ),
        ModelProfile(
            name="local",
            description=(
                "Local Ollama model for every stage (free, offline, lowest quality)."
            ),
            provider="ollama",
            stages=_stages(*("llama3.1:8b",) * len(StageKey)),
        ),
    )
}


def get_profile(name: str) -> ModelProfile | None:
    """Return the built-in profile called ``name``, or None."""
    return BUILTIN_MODEL_PROFILES.get(name)


def profile_stage_model(profile: ModelProfile, stage: StageKey) -> str | None:
    """Return the profile's model for ``stage``.

    An economy profile that does not list the stage defers to the profile it
    extends. Returns None when no model is named.
    """
    model = profile.stages.get(stage)
    if model is not None or profile.extends is None:
        return model
    base = get_profile(profile.extends)
    return profile_stage_model(base, stage) if base is not None else None


def profile_for_provider(provider: str, *, economy: bool) -> ModelProfile | None:
    """Return the built-in profile that runs every stage on ``provider``.

    With ``economy`` the economy variant is preferred; a provider with no
    economy variant (``ollama``) falls back to its regular profile. Providers
    without a built-in profile give None.
    """
    matching = [p for p in BUILTIN_MODEL_PROFILES.values() if p.provider == provider]
    for profile in matching:
        if profile.economy == economy:
            return profile
    if economy:
        return next((p for p in matching if not p.economy), None)
    return None
