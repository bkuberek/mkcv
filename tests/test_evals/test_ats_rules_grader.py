"""Tests for the ATS rules grader (REQ-EV-9)."""

import pytest

from evals.graders.ats_rules_grader import AtsRulesGrader
from evals.models.grade import Grade
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import (
    CLEAN_YAML,
    FIXTURES,
    RECORDED_ROOT,
    make_context,
)

grader = AtsRulesGrader()
FAILURES = RECORDED_ROOT / "ats-failures"

RULE_FIXTURES = [
    ("R1", "r1-nonstandard-heading.yaml"),
    ("R2", "r2-malformed-email.yaml"),
    ("R3", "r3-first-person-bullet.yaml"),
    ("R4", "r4-overlong-bullet.yaml"),
    ("R5", "r5-too-many-highlights.yaml"),
    ("R6", "r6-spelled-out-date.yaml"),
    ("R7", "r7-html-tag.yaml"),
    ("R7", "r7-table-row.yaml"),
]


async def _grade(text: str) -> Grade:
    return await grader.grade(make_context(StageKey.STRUCTURE, text))


def _rules(grade: Grade) -> set[str]:
    return {failure["rule"] for failure in grade.details["failures"]}


def _with(old: str, new: str) -> str:
    assert CLEAN_YAML.count(old) == 1
    return CLEAN_YAML.replace(old, new)


def test_the_grader_is_named_ats_rules() -> None:
    assert grader.name == "ats_rules"


class TestCleanResume:
    async def test_the_recorded_resume_passes_every_rule(self) -> None:
        grade = await _grade(CLEAN_YAML)
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_a_passing_resume_lists_no_failures(self) -> None:
        assert (await _grade(CLEAN_YAML)).details["failures"] == []


class TestOneFailingFixturePerRule:
    @pytest.mark.parametrize(("rule", "name"), RULE_FIXTURES)
    async def test_the_fixture_fails_exactly_its_rule(
        self, rule: str, name: str
    ) -> None:
        grade = await _grade((FAILURES / name).read_text(encoding="utf-8"))
        assert _rules(grade) == {rule}

    @pytest.mark.parametrize(("rule", "name"), RULE_FIXTURES)
    async def test_one_failed_rule_costs_one_seventh(
        self, rule: str, name: str
    ) -> None:
        grade = await _grade((FAILURES / name).read_text(encoding="utf-8"))
        assert grade.score == pytest.approx(6 / 7)
        assert grade.passed is False


class TestFailureDetails:
    async def test_a_first_person_bullet_fails_r3_and_quotes_the_bullet(self) -> None:
        grade = await _grade(
            (FAILURES / "r3-first-person-bullet.yaml").read_text(encoding="utf-8")
        )
        [failure] = grade.details["failures"]
        assert failure["rule"] == "R3"
        assert failure["text"].startswith("I migrated 42 services")

    async def test_the_review_probe_fails_only_r3(self) -> None:
        probe = FIXTURES / "reference" / "review-probe" / "resume.yaml"
        grade = await _grade(probe.read_text(encoding="utf-8"))
        assert _rules(grade) == {"R3"}

    async def test_a_heading_failure_quotes_the_heading(self) -> None:
        grade = await _grade(
            (FAILURES / "r1-nonstandard-heading.yaml").read_text(encoding="utf-8")
        )
        assert grade.details["failures"][0]["text"] == "core_competencies"

    async def test_two_failing_rules_cost_two_sevenths(self) -> None:
        text = _with("start_date: 2021-03", "start_date: March 2021").replace(
            "alex.rivera@example.com", "nobody"
        )
        grade = await _grade(text)
        assert _rules(grade) == {"R2", "R6"}
        assert grade.score == pytest.approx(5 / 7)

    async def test_every_offending_bullet_is_listed(self) -> None:
        text = CLEAN_YAML.replace("- Built a Go", "- I built a Go").replace(
            "- Cut cloud spend", "- My cloud spend cut"
        )
        failures = (await _grade(text)).details["failures"]
        assert [f["rule"] for f in failures] == ["R3", "R3"]

    async def test_many_offending_bullets_of_one_rule_still_cost_one_seventh(
        self,
    ) -> None:
        text = CLEAN_YAML.replace("- Built a Go", "- I built a Go").replace(
            "- Cut cloud spend", "- My cloud spend cut"
        )
        assert (await _grade(text)).score == pytest.approx(6 / 7)


class TestRuleEdges:
    @pytest.mark.parametrize(
        "heading",
        ["Experience", "work_experience", "Professional Experience", "volunteering"],
    )
    async def test_standard_headings_pass_r1_in_any_case_or_spacing(
        self, heading: str
    ) -> None:
        grade = await _grade(_with("    skills:\n", f"    {heading}:\n"))
        assert "R1" not in _rules(grade)

    async def test_a_missing_email_fails_r2(self) -> None:
        grade = await _grade(_with("  email: alex.rivera@example.com\n", ""))
        assert "R2" in _rules(grade)

    @pytest.mark.parametrize("word", ["me", "my", "mine", "myself"])
    async def test_every_first_person_pronoun_fails_r3(self, word: str) -> None:
        grade = await _grade(
            _with("- Built a Go ingestion", f"- Built {word} Go ingestion")
        )
        assert "R3" in _rules(grade)

    async def test_a_word_that_merely_contains_i_does_not_fail_r3(self) -> None:
        grade = await _grade(
            _with("- Built a Go ingestion", "- Built a Mighty ingestion")
        )
        assert "R3" not in _rules(grade)

    async def test_a_bullet_of_exactly_300_characters_passes_r4(self) -> None:
        bullet = "x" * 300
        grade = await _grade(
            _with(
                "- Built a Go ingestion service",
                f"- {bullet}\n          - Built a Go ingestion service",
            )
        )
        assert "R4" not in _rules(grade)

    async def test_a_bullet_of_301_characters_fails_r4(self) -> None:
        bullet = "x" * 301
        grade = await _grade(
            _with(
                "- Built a Go ingestion service",
                f"- {bullet}\n          - Built a Go ingestion service",
            )
        )
        assert "R4" in _rules(grade)

    async def test_an_entry_with_an_empty_highlight_list_fails_r5(self) -> None:
        text = CLEAN_YAML.split("        highlights:\n          - Built a Go")[0]
        grade = await _grade(text + "        highlights: []\n")
        assert "R5" in _rules(grade)

    @pytest.mark.parametrize("date", ["2021", "2021-03", "present", "Present"])
    async def test_accepted_dates_pass_r6(self, date: str) -> None:
        grade = await _grade(_with("end_date: present", f"end_date: {date}"))
        assert "R6" not in _rules(grade)

    @pytest.mark.parametrize("date", ["2021-03-15", "Mar 2021", "03/2021", "ongoing"])
    async def test_other_dates_fail_r6(self, date: str) -> None:
        grade = await _grade(_with("end_date: present", f"end_date: '{date}'"))
        assert "R6" in _rules(grade)

    async def test_an_unquoted_full_date_fails_r6(self) -> None:
        grade = await _grade(_with("end_date: present", "end_date: 2021-03-15"))
        assert "R6" in _rules(grade)

    async def test_html_in_the_headline_fails_r7(self) -> None:
        grade = await _grade(_with("  headline: Platform", "  headline: <i>Platform"))
        assert "R7" in _rules(grade)

    async def test_a_less_than_sign_before_a_digit_is_not_html(self) -> None:
        grade = await _grade(_with("by 40% with", "by <40% with"))
        assert "R7" not in _rules(grade)


class TestUnreadableResumes:
    @pytest.mark.parametrize("text", ["", "cv: [unclosed", "just text", "cv: 3"])
    async def test_a_resume_that_cannot_be_read_scores_zero(self, text: str) -> None:
        grade = await _grade(text)
        assert (grade.score, grade.passed) == (0.0, False)

    async def test_the_reason_is_reported(self) -> None:
        failure = (await _grade("just text")).details["failures"][0]
        assert failure["rule"] == "parse"

    async def test_a_missing_output_scores_zero(self) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, None))
        assert grade.score == 0.0
