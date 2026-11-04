"""Tests for matching forbidden claims in resumes and cover letters."""

import pytest

from evals.graders.cover_letter_faithfulness_grader import (
    CoverLetterFaithfulnessGrader,
)
from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.text_normalization import claims_term
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import COVER_LETTER
from tests.test_evals.grading_support import make_case, make_context


@pytest.mark.parametrize(
    ("text", "term", "claimed"),
    [
        ("Built Spark jobs on the data lake", "Spark", True),
        ("I want to spark interest in the product", "Spark", False),
        ("Moved the warehouse to Snowflake", "Snowflake", True),
        ("Every customer is a snowflake", "Snowflake", False),
        ("Ran the SAP migration", "SAP", True),
        ("Tapped the sap of the maple", "SAP", False),
        ("Operated kubernetes clusters", "Kubernetes", True),
        ("Ran apache spark jobs", "Apache Spark", True),
        ("Sparked a redesign", "Apache Spark", False),
        ("Quota attainment of 120%", "quota", True),
        ("Designed NoSQL schemas", "SQL", False),
        ("Wrote SQL reports", "SQL", True),
        ("Migrated to PostgreSQL", "SQL", False),
    ],
)
def test_claims_match_whole_words_and_common_words_by_case(
    text: str, term: str, claimed: bool
) -> None:
    assert claims_term(text, term) is claimed


async def test_the_resume_grader_does_not_flag_the_verb() -> None:
    output = {
        "roles": [
            {
                "company": "Initech",
                "position": "Engineer",
                "bullets": [{"rewritten": "Helped spark adoption of the new tooling"}],
            }
        ]
    }
    ctx = make_context(
        StageKey.TAILOR,
        output,
        case=make_case(forbidden_claims=["Spark"]),
        kb_text="Initech -- Engineer",
    )
    grade = await FaithfulnessExtractionGrader().grade(ctx)
    assert grade.details["violations"] == []


async def test_the_resume_grader_still_flags_the_tool() -> None:
    output = {
        "roles": [
            {
                "company": "Initech",
                "position": "Engineer",
                "bullets": [{"rewritten": "Ran Apache Spark pipelines"}],
            }
        ]
    }
    ctx = make_context(
        StageKey.TAILOR,
        output,
        case=make_case(forbidden_claims=["Apache Spark"]),
        kb_text="Initech -- Engineer",
    )
    grade = await FaithfulnessExtractionGrader().grade(ctx)
    assert {"type": "forbidden_claim", "text": "Apache Spark"} in grade.details[
        "violations"
    ]


async def test_the_unit_of_a_scaled_number_is_not_a_name() -> None:
    letter = {
        **COVER_LETTER.model_dump(),
        "closing_paragraph": "Initech grew a book from $1.1M to $6.8M, closing $640K.",
    }
    ctx = make_context(
        StageKey.COVER_LETTER_GENERATE,
        letter,
        case=make_case(),
        kb_text="Initech: $1.1M sourced, $6.8M book, $640K closed.",
    )
    grade = await CoverLetterFaithfulnessGrader().grade(ctx)
    names = [v for v in grade.details["violations"] if v["type"] == "name"]
    assert "M" not in {v["text"] for v in names}
    assert "K" not in {v["text"] for v in names}


async def test_the_cover_letter_grader_does_not_flag_the_verb() -> None:
    letter = {
        **COVER_LETTER.model_dump(),
        "closing_paragraph": "I hope this letter will spark a conversation.",
    }
    ctx = make_context(
        StageKey.COVER_LETTER_GENERATE,
        letter,
        case=make_case(forbidden_claims=["Spark"]),
    )
    grade = await CoverLetterFaithfulnessGrader().grade(ctx)
    forbidden = [
        v for v in grade.details["violations"] if v["type"] == "forbidden_claim"
    ]
    assert forbidden == []
