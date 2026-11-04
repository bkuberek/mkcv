"""Turn recommendations into suggested profiles; nothing applies them."""

from collections.abc import Sequence

from evals.models.profile_choice import ProfileChoice
from evals.models.recommendation import OVERALL, Recommendation
from evals.models.stage_summary import StageSummary
from evals.models.suggested_profile import SuggestedProfile
from evals.stages import EVALUATED_STAGES, NOT_EVALUATED, stage_position
from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    profile_stage_model,
)
from mkcv.core.models.stage_key import StageKey

RECOMMENDED_PROFILE = "recommended"
"""The cross-provider profile: the best model of every stage, any provider."""


def suggest_profiles(
    recommendations: Sequence[Recommendation],
) -> list[SuggestedProfile]:
    """Return the built-in provider profiles, then ``recommended``.

    A provider profile follows that provider's best model at every stage that
    has one; profiles of providers the run did not evaluate, and economy
    profiles, are left out. ``recommended`` takes each stage's overall winner.
    """
    ordered = sorted(recommendations, key=lambda r: stage_position(r.stage))
    profiles: list[SuggestedProfile] = []
    for profile in BUILTIN_MODEL_PROFILES.values():
        if profile.economy:
            continue
        choices = [
            _choice(rec, current=profile_stage_model(profile, rec.stage))
            for rec in ordered
            if rec.scope == profile.provider and rec.model is not None
        ]
        if choices:
            profiles.append(
                SuggestedProfile(
                    name=profile.name, provider=profile.provider, choices=choices
                )
            )
    recommended = [
        _choice(rec, current=None)
        for rec in ordered
        if rec.scope == OVERALL and rec.model is not None
    ]
    if recommended:
        profiles.append(SuggestedProfile(name=RECOMMENDED_PROFILE, choices=recommended))
    return profiles


def not_evaluated(summaries: Sequence[StageSummary]) -> dict[StageKey, str]:
    """Every model-backed stage without a result in ``summaries``, and why."""
    ran = {summary.stage for summary in summaries}
    missing: dict[StageKey, str] = {
        stage: "not in this run" for stage in EVALUATED_STAGES if stage not in ran
    }
    missing.update(NOT_EVALUATED)
    return missing


def _choice(rec: Recommendation, *, current: str | None) -> ProfileChoice:
    assert rec.provider is not None and rec.model is not None
    return ProfileChoice(
        stage=rec.stage,
        provider=rec.provider,
        model=rec.model,
        current=current,
        score=rec.score,
        too_close_to_call=rec.too_close_to_call,
    )
