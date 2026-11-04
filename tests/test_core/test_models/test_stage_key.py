"""Tests for StageKey and its stage-group constants (design section 3.1)."""

import pytest

from mkcv.core.models.stage_key import (
    COVER_LETTER_STAGES,
    PIPELINE_STAGE_NUMBERS,
    PIPELINE_STAGES,
    StageKey,
)


class TestStageKey:
    def test_members_and_values_follow_the_design(self) -> None:
        assert {member.name: member.value for member in StageKey} == {
            "ANALYZE": "analyze",
            "SELECT": "select",
            "TAILOR": "tailor",
            "STRUCTURE": "structure",
            "REVIEW": "review",
            "COVER_LETTER_GENERATE": "cover_letter.generate",
            "COVER_LETTER_REVIEW": "cover_letter.review",
            "KB": "kb",
            "VALIDATE": "validate",
        }

    def test_members_are_declared_in_pipeline_order(self) -> None:
        assert [member.value for member in StageKey] == [
            "analyze",
            "select",
            "tailor",
            "structure",
            "review",
            "cover_letter.generate",
            "cover_letter.review",
            "kb",
            "validate",
        ]

    def test_members_compare_equal_to_their_string_values(self) -> None:
        assert StageKey.TAILOR == "tailor"

    def test_a_value_converts_back_to_its_member(self) -> None:
        assert StageKey("cover_letter.review") is StageKey.COVER_LETTER_REVIEW

    def test_unknown_values_are_rejected(self) -> None:
        with pytest.raises(ValueError):
            StageKey("translate")

    def test_str_gives_the_value_for_messages(self) -> None:
        assert f"{StageKey.COVER_LETTER_GENERATE}" == "cover_letter.generate"


class TestStageGroups:
    def test_pipeline_stages_are_the_five_resume_stages_in_order(self) -> None:
        assert PIPELINE_STAGES == (
            StageKey.ANALYZE,
            StageKey.SELECT,
            StageKey.TAILOR,
            StageKey.STRUCTURE,
            StageKey.REVIEW,
        )

    def test_cover_letter_stages_are_generate_then_review(self) -> None:
        assert COVER_LETTER_STAGES == (
            StageKey.COVER_LETTER_GENERATE,
            StageKey.COVER_LETTER_REVIEW,
        )

    def test_pipeline_stage_numbers_run_from_one_to_five(self) -> None:
        assert PIPELINE_STAGE_NUMBERS == {
            StageKey.ANALYZE: 1,
            StageKey.SELECT: 2,
            StageKey.TAILOR: 3,
            StageKey.STRUCTURE: 4,
            StageKey.REVIEW: 5,
        }

    def test_numbers_cover_exactly_the_pipeline_stages(self) -> None:
        assert tuple(PIPELINE_STAGE_NUMBERS) == PIPELINE_STAGES

    def test_groups_are_immutable_tuples(self) -> None:
        assert isinstance(PIPELINE_STAGES, tuple)
        assert isinstance(COVER_LETTER_STAGES, tuple)

    def test_groups_do_not_overlap(self) -> None:
        assert not set(PIPELINE_STAGES) & set(COVER_LETTER_STAGES)
