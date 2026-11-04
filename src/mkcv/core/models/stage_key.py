"""Identifiers for the stages that call an LLM."""

from enum import StrEnum


class StageKey(StrEnum):
    """An LLM-backed stage, named as it appears in configuration and output."""

    ANALYZE = "analyze"
    SELECT = "select"
    TAILOR = "tailor"
    STRUCTURE = "structure"
    REVIEW = "review"
    COVER_LETTER_GENERATE = "cover_letter.generate"
    COVER_LETTER_REVIEW = "cover_letter.review"
    KB = "kb"
    VALIDATE = "validate"


PIPELINE_STAGES: tuple[StageKey, ...] = (
    StageKey.ANALYZE,
    StageKey.SELECT,
    StageKey.TAILOR,
    StageKey.STRUCTURE,
    StageKey.REVIEW,
)
"""The five resume pipeline stages, in execution order."""

COVER_LETTER_STAGES: tuple[StageKey, ...] = (
    StageKey.COVER_LETTER_GENERATE,
    StageKey.COVER_LETTER_REVIEW,
)
"""The cover letter stages, in execution order."""

PIPELINE_STAGE_NUMBERS: dict[StageKey, int] = {
    stage: number for number, stage in enumerate(PIPELINE_STAGES, start=1)
}
"""Pipeline stage to its 1-based number (the ``from_stage`` numbering)."""
