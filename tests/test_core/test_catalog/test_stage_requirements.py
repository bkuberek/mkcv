"""Tests for the built-in stage requirements (design section 6.1)."""

import pytest
from pydantic import ValidationError

from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.stage_requirement import StageRequirement

_EFFICIENT = ModelTier.EFFICIENT
_STRONG = ModelTier.STRONG

# stage -> (config_path, default_temperature, min_tier, est_input, est_output, label)
_TABLE: dict[StageKey, tuple[str, float, ModelTier, int, int, str]] = {
    StageKey.ANALYZE: (
        "pipeline.stages.analyze",
        0.2,
        _EFFICIENT,
        4000,
        2000,
        "Analyze JD",
    ),
    StageKey.SELECT: (
        "pipeline.stages.select",
        0.3,
        _STRONG,
        12000,
        3000,
        "Select experience",
    ),
    StageKey.TAILOR: (
        "pipeline.stages.tailor",
        0.5,
        _STRONG,
        15000,
        8000,
        "Tailor content",
    ),
    StageKey.STRUCTURE: (
        "pipeline.stages.structure",
        0.1,
        _EFFICIENT,
        10000,
        6000,
        "Structure YAML",
    ),
    StageKey.REVIEW: (
        "pipeline.stages.review",
        0.3,
        _STRONG,
        12000,
        4000,
        "Review",
    ),
    StageKey.COVER_LETTER_GENERATE: (
        "cover_letter.stages.generate",
        0.6,
        _STRONG,
        12000,
        3000,
        "Cover letter",
    ),
    StageKey.COVER_LETTER_REVIEW: (
        "cover_letter.stages.review",
        0.2,
        _EFFICIENT,
        5000,
        2000,
        "Cover letter review",
    ),
    StageKey.KB: ("kb", 0.3, _STRONG, 30000, 8000, "KB generation"),
    StageKey.VALIDATE: ("validate", 0.3, _EFFICIENT, 8000, 3000, "Validate"),
}


class TestCoverage:
    def test_every_stage_key_has_a_requirement(self) -> None:
        assert set(STAGE_REQUIREMENTS) == set(StageKey)

    def test_requirements_are_ordered_like_the_stage_keys(self) -> None:
        assert tuple(STAGE_REQUIREMENTS) == tuple(StageKey)

    def test_each_requirement_names_its_own_stage(self) -> None:
        for stage, requirement in STAGE_REQUIREMENTS.items():
            assert requirement.stage is stage


@pytest.mark.parametrize("stage", list(StageKey))
class TestTable:
    def test_config_path(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].config_path == _TABLE[stage][0]

    def test_default_temperature(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].default_temperature == _TABLE[stage][1]

    def test_minimum_tier(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].min_tier is _TABLE[stage][2]

    def test_estimated_input_tokens(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].est_input_tokens == _TABLE[stage][3]

    def test_estimated_output_tokens(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].est_output_tokens == _TABLE[stage][4]

    def test_label(self, stage: StageKey) -> None:
        assert STAGE_REQUIREMENTS[stage].label == _TABLE[stage][5]


class TestInvariants:
    def test_default_temperatures_are_valid_sampling_values(self) -> None:
        for requirement in STAGE_REQUIREMENTS.values():
            assert 0.0 <= requirement.default_temperature <= 2.0

    def test_token_estimates_are_positive(self) -> None:
        for requirement in STAGE_REQUIREMENTS.values():
            assert requirement.est_input_tokens > 0
            assert requirement.est_output_tokens > 0

    def test_config_paths_are_unique(self) -> None:
        paths = [requirement.config_path for requirement in STAGE_REQUIREMENTS.values()]
        assert len(paths) == len(set(paths))

    def test_labels_are_unique(self) -> None:
        labels = [requirement.label for requirement in STAGE_REQUIREMENTS.values()]
        assert len(labels) == len(set(labels))

    def test_no_stage_needs_the_frontier_tier(self) -> None:
        tiers = {requirement.min_tier for requirement in STAGE_REQUIREMENTS.values()}
        assert tiers == {_EFFICIENT, _STRONG}


class TestStageRequirementModel:
    def test_requirements_are_frozen(self) -> None:
        requirement = STAGE_REQUIREMENTS[StageKey.TAILOR]
        with pytest.raises(ValidationError):
            requirement.label = "other"  # type: ignore[misc]

    def test_fields_match_the_design(self) -> None:
        assert list(StageRequirement.model_fields) == [
            "stage",
            "config_path",
            "default_temperature",
            "min_tier",
            "est_input_tokens",
            "est_output_tokens",
            "label",
        ]
