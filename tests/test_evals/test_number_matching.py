"""Tests for matching numbers in an output to the knowledge base's numbers."""

import pytest

from evals.graders.cover_letter_faithfulness_grader import (
    CoverLetterFaithfulnessGrader,
)
from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.text_normalization import is_supported_number, supported_numbers
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import COVER_LETTER
from tests.test_evals.grading_support import CASE_BY_ID, make_context


@pytest.mark.parametrize(
    ("claimed", "source"),
    [
        ("9,800", "followers went from 1,200 to 9.8k"),
        ("9.8k", "grew to 9,800 followers"),
        ("410,000", "one video got 410k views"),
        ("410K", "one video got 410,000 views"),
        ("$1.2M", "a $1,200,000 budget"),
        ("$1,200,000", "a $1.2M budget"),
        ("$1.2 million", "a $1.2M budget"),
        ("$6.8M", "a book of $6.8 million"),
        ("2.5B", "2.5 billion events"),
        ("12000", "12,000 users"),
        ("40 percent", "cut latency by 40%"),
        ("12.5%", "a 12.5 percent rise"),
        ("40", "cut latency by 40%"),
        ("8x", "made queries 8x faster"),
        ("$310K", "saving an estimated $310K per year"),
    ],
)
def test_the_same_quantity_written_differently_is_supported(
    claimed: str, source: str
) -> None:
    assert is_supported_number(claimed, supported_numbers(source))


@pytest.mark.parametrize(
    ("claimed", "source"),
    [
        ("9,900", "grew to 9.8k followers"),
        ("$2.4M", "saved $310K"),
        ("41", "cut latency by 40%"),
        ("98", "grew to 9.8k followers"),
        ("4,100", "one video got 410k views"),
    ],
)
def test_a_different_quantity_is_not_supported(claimed: str, source: str) -> None:
    assert not is_supported_number(claimed, supported_numbers(source))


def test_a_number_without_digits_is_not_supported() -> None:
    assert not is_supported_number("k", supported_numbers("9.8k"))


class TestGraders:
    """The dataset's own false positive: 9,800 followers against a KB of 9.8k."""

    CASE = CASE_BY_ID["marketing-coordinator-match"]
    KB = "- TikTok followers went from 1,200 to 9.8k over the summer\n- 410k views\n"

    async def test_the_resume_grader_accepts_a_reformatted_number(self) -> None:
        output = {
            "roles": [
                {
                    "company": "Juniper & Vale",
                    "position": "Intern",
                    "bullets": [
                        {"rewritten": "Grew TikTok from 1,200 to 9,800 followers"},
                        {"rewritten": "Made a video with 410,000 views"},
                    ],
                }
            ]
        }
        ctx = make_context(
            StageKey.TAILOR,
            output,
            case=self.CASE,
            kb_text=self.KB + "Juniper & Vale -- Intern\n",
        )
        grade = await FaithfulnessExtractionGrader().grade(ctx)
        numbers = [v for v in grade.details["violations"] if v["type"] == "number"]
        assert numbers == []

    async def test_the_cover_letter_grader_accepts_a_reformatted_number(
        self,
    ) -> None:
        letter = {
            **COVER_LETTER.model_dump(),
            "opening_paragraph": "I grew the TikTok account to 9,800 followers.",
            "body_paragraphs": ["One video reached 410,000 views."],
            "closing_paragraph": "I would like to talk.",
        }
        ctx = make_context(
            StageKey.COVER_LETTER_GENERATE, letter, case=self.CASE, kb_text=self.KB
        )
        grade = await CoverLetterFaithfulnessGrader().grade(ctx)
        numbers = [v for v in grade.details["violations"] if v["type"] == "number"]
        assert numbers == []
