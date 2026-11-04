"""The stages the harness evaluates, in report order, and the ones it cannot."""

from mkcv.core.models.stage_key import COVER_LETTER_STAGES, PIPELINE_STAGES, StageKey

EVALUATED_STAGES: tuple[StageKey, ...] = (*PIPELINE_STAGES, *COVER_LETTER_STAGES)
"""The five resume pipeline stages, then the two cover letter stages."""

STAGE_ORDER: dict[StageKey, int] = {
    stage: position for position, stage in enumerate(EVALUATED_STAGES)
}
"""Each evaluated stage's position, for sorting summaries and recommendations."""

NOT_EVALUATED: dict[StageKey, str] = {
    StageKey.KB: (
        "not evaluated: needs source-document fixtures and a knowledge base "
        "grader the harness does not have yet"
    ),
    StageKey.VALIDATE: (
        "not evaluated: needs rendered PDF fixtures and a grader for "
        "validation findings the harness does not have yet"
    ),
}
"""Stages that call a model but that this harness cannot score, and why."""


def stage_position(stage: StageKey) -> int:
    """Return where ``stage`` sorts; stages the harness does not run sort last."""
    return STAGE_ORDER.get(stage, len(STAGE_ORDER))
