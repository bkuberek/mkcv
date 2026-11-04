"""What each LLM-backed stage needs from a model.

Token estimates are rough planning numbers that include typical thinking
output. They feed cost estimates only; measured medians from an eval run
replace them in the eval report.
"""

from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.stage_requirement import StageRequirement

STAGE_REQUIREMENTS: dict[StageKey, StageRequirement] = {
    requirement.stage: requirement
    for requirement in (
        StageRequirement(
            stage=StageKey.ANALYZE,
            config_path="pipeline.stages.analyze",
            default_temperature=0.2,
            min_tier=ModelTier.EFFICIENT,
            est_input_tokens=4000,
            est_output_tokens=2000,
            label="Analyze JD",
        ),
        StageRequirement(
            stage=StageKey.SELECT,
            config_path="pipeline.stages.select",
            default_temperature=0.3,
            min_tier=ModelTier.STRONG,
            est_input_tokens=12000,
            est_output_tokens=3000,
            label="Select experience",
        ),
        StageRequirement(
            stage=StageKey.TAILOR,
            config_path="pipeline.stages.tailor",
            default_temperature=0.5,
            min_tier=ModelTier.STRONG,
            est_input_tokens=15000,
            est_output_tokens=8000,
            label="Tailor content",
        ),
        StageRequirement(
            stage=StageKey.STRUCTURE,
            config_path="pipeline.stages.structure",
            default_temperature=0.1,
            min_tier=ModelTier.EFFICIENT,
            est_input_tokens=10000,
            est_output_tokens=6000,
            label="Structure YAML",
        ),
        StageRequirement(
            stage=StageKey.REVIEW,
            config_path="pipeline.stages.review",
            default_temperature=0.3,
            min_tier=ModelTier.STRONG,
            est_input_tokens=12000,
            est_output_tokens=4000,
            label="Review",
        ),
        StageRequirement(
            stage=StageKey.COVER_LETTER_GENERATE,
            config_path="cover_letter.stages.generate",
            default_temperature=0.6,
            min_tier=ModelTier.STRONG,
            est_input_tokens=12000,
            est_output_tokens=3000,
            label="Cover letter",
        ),
        StageRequirement(
            stage=StageKey.COVER_LETTER_REVIEW,
            config_path="cover_letter.stages.review",
            default_temperature=0.2,
            min_tier=ModelTier.EFFICIENT,
            est_input_tokens=5000,
            est_output_tokens=2000,
            label="Cover letter review",
        ),
        StageRequirement(
            stage=StageKey.KB,
            config_path="kb",
            default_temperature=0.3,
            min_tier=ModelTier.STRONG,
            est_input_tokens=30000,
            est_output_tokens=8000,
            label="KB generation",
        ),
        StageRequirement(
            stage=StageKey.VALIDATE,
            config_path="validate",
            default_temperature=0.3,
            min_tier=ModelTier.EFFICIENT,
            est_input_tokens=8000,
            est_output_tokens=3000,
            label="Validate",
        ),
    )
}
