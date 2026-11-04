"""Tests for the faithfulness extraction grader (REQ-EV-10) and its helpers."""

from decimal import Decimal
from typing import Any

import pytest

from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.text_normalization import (
    contains_term,
    extract_numbers,
    normalize_company,
    number_values,
)
from evals.models.grade import Grade
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import (
    CLEAN_YAML,
    FIXTURES,
    RECORDED_ROOT,
    make_case,
    make_context,
    recorded_json,
)

grader = FaithfulnessExtractionGrader()
FABRICATED = RECORDED_ROOT / "fabricated-claims"


def _tailored(*bullets: str, company: str = "Initech", **role: Any) -> dict[str, Any]:
    return {
        "mission": {"text": "m", "rationale": "r"},
        "skills": [],
        "roles": [
            {
                "company": company,
                "position": role.pop("position", "Engineer"),
                "bullets": [{"original": b, "rewritten": b} for b in bullets],
                **role,
            }
        ],
    }


KB_BASICS = "Initech\nEngineer\n"
"""A company and a title every synthetic knowledge base in these tests holds."""


async def _grade_tailored(
    output: dict[str, Any], kb_text: str, **case_fields: Any
) -> Grade:
    context = make_context(
        StageKey.TAILOR,
        output,
        case=make_case(**case_fields),
        kb_text=KB_BASICS + kb_text,
    )
    return await grader.grade(context)


def _violations(grade: Grade, kind: str) -> list[str]:
    return [v["text"] for v in grade.details["violations"] if v["type"] == kind]


def test_the_grader_is_named_faithfulness_extraction() -> None:
    assert grader.name == "faithfulness_extraction"


class TestNumbers:
    async def test_a_percent_spelled_out_matches_the_percent_sign(self) -> None:
        output = _tailored("Cut p99 latency by 40 percent")
        grade = await _grade_tailored(output, "Initech\nreduced p99 latency by 40%\n")
        assert _violations(grade, "number") == []

    async def test_a_number_absent_from_the_knowledge_base_is_a_violation(
        self,
    ) -> None:
        grade = await _grade_tailored(
            _tailored("Saved $2.4M annually"), "Initech\nsaved money\n"
        )
        assert _violations(grade, "number") == ["$2.4M"]

    async def test_the_violation_carries_its_type_and_text(self) -> None:
        grade = await _grade_tailored(
            _tailored("Saved $2.4M annually"), "Initech\nsaved money\n"
        )
        assert grade.details["violations"] == [{"type": "number", "text": "$2.4M"}]

    async def test_a_dollar_amount_in_the_knowledge_base_supports_the_same_amount(
        self,
    ) -> None:
        grade = await _grade_tailored(
            _tailored("Saved $2.4M annually"), "Initech\nsaved $2.4M a year\n"
        )
        assert _violations(grade, "number") == []

    async def test_thousands_separators_do_not_matter(self) -> None:
        grade = await _grade_tailored(
            _tailored("Handled 85,000 events"), "Initech\n85000 events\n"
        )
        assert _violations(grade, "number") == []

    async def test_a_unit_the_knowledge_base_lacks_is_tolerated(self) -> None:
        grade = await _grade_tailored(
            _tailored("Made queries 8x faster"), "Initech\nqueries got 8 times faster\n"
        )
        assert _violations(grade, "number") == []

    async def test_digits_inside_a_word_are_not_numbers(self) -> None:
        grade = await _grade_tailored(
            _tailored("Improved p99 latency on S3 and EC2 for Q3"), "Initech\n"
        )
        assert _violations(grade, "number") == []

    async def test_each_occurrence_is_a_violation(self) -> None:
        grade = await _grade_tailored(
            _tailored("Saved 73% here", "Saved 73% there"), "Initech\n"
        )
        assert _violations(grade, "number") == ["73%", "73%"]

    async def test_a_date_field_is_not_checked_as_a_number(self) -> None:
        output = _tailored("Led platform work", start_date="2019-03", end_date="2021")
        grade = await _grade_tailored(output, "Initech\nplatform work\n")
        assert _violations(grade, "number") == []

    async def test_an_iso_date_inside_a_bullet_is_not_checked_either(self) -> None:
        grade = await _grade_tailored(
            _tailored("Shipped on 2019-03 as planned"), "Initech\n"
        )
        assert _violations(grade, "number") == []

    async def test_a_year_in_a_knowledge_base_date_supports_the_same_year(
        self,
    ) -> None:
        grade = await _grade_tailored(
            _tailored("Joined in 2021"), "Initech: 2021-03 to present\n"
        )
        assert _violations(grade, "number") == []

    async def test_a_year_in_a_bullet_must_be_in_the_knowledge_base(self) -> None:
        grade = await _grade_tailored(_tailored("Launched in 2019"), "Initech\n")
        assert _violations(grade, "number") == ["2019"]

    async def test_the_original_bullet_is_not_checked_only_the_rewrite(self) -> None:
        output = _tailored("Kept 5 teams")
        output["roles"][0]["bullets"][0]["original"] = "Invented 99 things"
        grade = await _grade_tailored(output, "Initech\n5 teams\n")
        assert _violations(grade, "number") == []


class TestEmployersAndTitles:
    async def test_a_company_suffix_is_ignored(self) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", company="Initech, Inc."), "Initech\nled work\n"
        )
        assert _violations(grade, "company") == []

    async def test_a_company_missing_from_the_knowledge_base_is_a_violation(
        self,
    ) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", company="Hooli"), "Initech\nled work\n"
        )
        assert _violations(grade, "company") == ["Hooli"]

    async def test_a_company_only_matches_whole_words(self) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", company="Tech"), "Initech\nled work\n"
        )
        assert _violations(grade, "company") == ["Tech"]

    async def test_a_title_missing_from_the_knowledge_base_is_a_violation(
        self,
    ) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", position="Principal Architect"),
            "Initech -- Staff Engineer\nled work\n",
        )
        assert _violations(grade, "title") == ["Principal Architect"]

    async def test_a_title_with_other_punctuation_still_matches(self) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", position="Senior Engineer, Platform"),
            "### Initech -- Senior Engineer (Platform)\nled work\n",
        )
        assert _violations(grade, "title") == []

    async def test_a_blank_company_is_not_checked(self) -> None:
        grade = await _grade_tailored(_tailored("x", company=" "), "Initech\n")
        assert _violations(grade, "company") == []

    async def test_a_company_that_is_only_a_suffix_is_not_counted(self) -> None:
        grade = await _grade_tailored(_tailored("x", company="Inc."), "Initech\n")
        assert grade.details["checked"] == 1  # only the title


class TestForbiddenClaims:
    async def test_a_forbidden_term_in_a_bullet_is_a_violation(self) -> None:
        grade = await _grade_tailored(
            _tailored("Trained models in PyTorch"),
            "Initech\ntrained models\n",
            forbidden_claims=["PyTorch"],
        )
        assert _violations(grade, "forbidden_claim") == ["PyTorch"]

    async def test_a_forbidden_term_in_a_skill_is_a_violation(self) -> None:
        output = _tailored("Led work")
        output["skills"] = [{"label": "ML", "skills": ["MLflow", "Python"]}]
        grade = await _grade_tailored(
            output, "Initech\nled work\n", forbidden_claims=["MLflow"]
        )
        assert _violations(grade, "forbidden_claim") == ["MLflow"]

    async def test_a_forbidden_term_in_a_tech_stack_is_a_violation(self) -> None:
        grade = await _grade_tailored(
            _tailored("Led work", tech_stack="Go, Airflow"),
            "Initech\nled work\n",
            forbidden_claims=["Airflow"],
        )
        assert _violations(grade, "forbidden_claim") == ["Airflow"]

    async def test_matching_ignores_case(self) -> None:
        grade = await _grade_tailored(
            _tailored("Used pytorch daily"),
            "Initech\n",
            forbidden_claims=["PyTorch"],
        )
        assert _violations(grade, "forbidden_claim") == ["PyTorch"]

    async def test_a_term_inside_a_longer_word_is_not_a_violation(self) -> None:
        grade = await _grade_tailored(
            _tailored("Ran a NoSQL store"),
            "Initech\nnosql\n",
            forbidden_claims=["SQL"],
        )
        assert _violations(grade, "forbidden_claim") == []

    async def test_a_term_found_twice_is_one_violation(self) -> None:
        grade = await _grade_tailored(
            _tailored("PyTorch here", "PyTorch there"),
            "Initech\n",
            forbidden_claims=["PyTorch"],
        )
        assert _violations(grade, "forbidden_claim") == ["PyTorch"]

    async def test_a_term_in_the_mission_is_not_scanned(self) -> None:
        grade = await _grade_tailored(
            _tailored("Led work") | {"mission": {"text": "PyTorch", "rationale": ""}},
            "Initech\nled work\n",
            forbidden_claims=["PyTorch"],
        )
        assert _violations(grade, "forbidden_claim") == []


class TestScore:
    async def test_a_faithful_output_scores_one_and_passes(self) -> None:
        grade = await _grade_tailored(
            _tailored("Kept 5 teams"), "Initech\nEngineer\n5 teams\n"
        )
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_the_score_is_one_minus_violations_over_checked_claims(self) -> None:
        # Checked: company, title, one number, one forbidden term = 4; one violation.
        grade = await _grade_tailored(
            _tailored("Saved 73% on spend"),
            "Initech\nEngineer\n",
            forbidden_claims=["PyTorch"],
        )
        assert grade.score == pytest.approx(0.75)
        assert grade.passed is False

    async def test_an_output_with_no_claims_scores_one(self) -> None:
        output: dict[str, Any] = {"mission": {"text": "", "rationale": ""}}
        output |= {"skills": [], "roles": []}
        grade = await _grade_tailored(output, "Initech\n")
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_the_score_never_drops_below_zero(self) -> None:
        grade = await _grade_tailored(
            _tailored("Saved 73%", company="Hooli", position="CEO"), "x"
        )
        assert grade.score is not None
        assert grade.score >= 0.0

    async def test_a_missing_output_scores_zero(self) -> None:
        grade = await grader.grade(make_context(StageKey.TAILOR, None))
        assert (grade.score, grade.passed) == (0.0, False)


class TestRecordedOutputs:
    """The grader on the recorded outputs and the seeded fabrications."""

    async def test_the_recorded_tailored_content_is_faithful(self) -> None:
        output = recorded_json("stage3_content.json")
        grade = await grader.grade(make_context(StageKey.TAILOR, output))
        assert grade.details["violations"] == []
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_the_recorded_selection_is_faithful(self) -> None:
        output = recorded_json("stage2_selection.json")
        grade = await grader.grade(make_context(StageKey.SELECT, output))
        assert grade.details["violations"] == []

    async def test_the_recorded_resume_is_faithful(self) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, CLEAN_YAML))
        assert grade.details["violations"] == []
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_the_fabricated_amount_and_forbidden_claim_are_both_caught(
        self,
    ) -> None:
        output = recorded_json("stage3_content.json", folder=FABRICATED)
        grade = await grader.grade(
            make_context(StageKey.TAILOR, output, case="backend-ml-stretch")
        )
        assert _violations(grade, "number") == ["$2.4M"]
        assert _violations(grade, "forbidden_claim") == ["PyTorch"]
        assert grade.passed is False

    async def test_the_probes_fabricated_73_percent_is_caught(self) -> None:
        probe = FIXTURES / "reference" / "review-probe" / "resume.yaml"
        grade = await grader.grade(
            make_context(StageKey.STRUCTURE, probe.read_text(encoding="utf-8"))
        )
        assert grade.details["violations"] == [{"type": "number", "text": "73%"}]
        assert grade.passed is False

    async def test_a_stage_4_company_the_knowledge_base_lacks_is_caught(self) -> None:
        text = CLEAN_YAML.replace("company: Globex", "company: Wonka Industries")
        grade = await grader.grade(make_context(StageKey.STRUCTURE, text))
        assert _violations(grade, "company") == ["Wonka Industries"]

    async def test_a_stage_4_forbidden_skill_is_caught(self) -> None:
        text = CLEAN_YAML.replace("details: Go, Python, SQL", "details: Go, PyTorch")
        grade = await grader.grade(
            make_context(StageKey.STRUCTURE, text, case="backend-ml-stretch")
        )
        assert _violations(grade, "forbidden_claim") == ["PyTorch"]

    async def test_stage_2_suggested_bullets_are_checked(self) -> None:
        output = recorded_json("stage2_selection.json")
        output["selected_experiences"][0]["suggested_bullets"].append("Saved $9.9M")
        grade = await grader.grade(make_context(StageKey.SELECT, output))
        assert _violations(grade, "number") == ["$9.9M"]

    async def test_stage_2_highlighted_skills_are_scanned_for_forbidden_terms(
        self,
    ) -> None:
        output = recorded_json("stage2_selection.json")
        output["skills_to_highlight"].append("MLflow")
        grade = await grader.grade(
            make_context(StageKey.SELECT, output, case="backend-ml-stretch")
        )
        assert _violations(grade, "forbidden_claim") == ["MLflow"]

    async def test_an_unparseable_resume_has_nothing_to_check(self) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, "cv: [oops"))
        assert (grade.score, grade.passed) == (0.0, False)


class TestNormalization:
    @pytest.mark.parametrize(
        ("text", "numbers"),
        [
            ("Cut p99 latency by 40%", ["40%"]),
            ("Saved $2.4M and 85,000 events", ["$2.4M", "85,000"]),
            ("a 3 TB database", ["3"]),
            ("8x faster in 6 minutes", ["8x", "6"]),
            ("lowered 40 percent", ["40 percent"]),
            ("S3, EC2 and Q3", []),
            ("1st and 2nd", []),
            ("version 1.5 shipped", ["1.5"]),
            ("in 2021, then 2022.", ["2021", "2022"]),
        ],
    )
    def test_numbers_are_extracted(self, text: str, numbers: list[str]) -> None:
        assert extract_numbers(text) == numbers

    @pytest.mark.parametrize(
        ("raw", "values"),
        [
            ("$2.4M", {"2.4", "2400000"}),
            ("85,000", {"85000"}),
            ("40 percent", {"40"}),
            ("40 %", {"40"}),
            ("8X", {"8"}),
            ("310k", {"310", "310000"}),
            ("1.5 billion", {"1.5", "1500000000"}),
        ],
    )
    def test_numbers_stand_for_their_scaled_and_bare_values(
        self, raw: str, values: set[str]
    ) -> None:
        assert number_values(raw) == {Decimal(value) for value in values}

    @pytest.mark.parametrize(
        ("name", "normalized"),
        [
            ("Initech, Inc.", "initech"),
            ("Pied Piper LLC", "pied piper"),
            ("Acme Corp.", "acme"),
            ("Dunder Mifflin Co", "dunder mifflin"),
            ("Acme Co Ltd", "acme"),
            ("Wonka Industries", "wonka industries"),
            ("Senior Engineer, Platform", "senior engineer platform"),
        ],
    )
    def test_companies_and_titles_are_normalized(
        self, name: str, normalized: str
    ) -> None:
        assert normalize_company(name) == normalized

    @pytest.mark.parametrize(
        ("text", "term", "found"),
        [
            ("Used PyTorch daily", "pytorch", True),
            ("NoSQL store", "SQL", False),
            ("SQL, Python", "SQL", True),
            ("An A/B testing platform", "A/B testing platform", True),
            ("Wrote C++ and C#", "C++", True),
            ("Wrote Cobol", "C", False),
        ],
    )
    def test_terms_match_whole_words_without_regard_to_case(
        self, text: str, term: str, found: bool
    ) -> None:
        assert contains_term(text, term) is found
