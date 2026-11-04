"""Tests for the cover letter graders: rules, faithfulness, and judges."""

from pathlib import Path
from typing import Any

import pytest

import evals.graders
from evals.graders.cover_letter_defect_grader import CoverLetterDefectGrader
from evals.graders.cover_letter_faithfulness_grader import (
    CoverLetterFaithfulnessGrader,
)
from evals.graders.cover_letter_faithfulness_judge_grader import (
    CoverLetterFaithfulnessJudgeGrader,
)
from evals.graders.cover_letter_judge_grader import CoverLetterJudgeGrader
from evals.graders.cover_letter_rules_grader import CoverLetterRulesGrader
from evals.graders.schema_grader import SchemaGrader
from evals.models.criterion_score import CriterionScore
from evals.models.defect_finding import DefectFinding
from evals.models.defect_judgement import DefectJudgement
from evals.models.eval_case import EvalCase
from evals.models.faithfulness_judgement import FaithfulnessJudgement
from evals.models.faithfulness_verdict import FaithfulnessVerdict
from evals.models.grade import Grade
from evals.models.rubric_judgement import RubricJudgement
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import COVER_LETTER, COVER_LETTER_REVIEW
from tests.test_evals.grading_support import (
    CASE_BY_ID,
    FIXTURES,
    make_context,
    recorded_json,
)
from tests.test_evals.test_judge_graders import RecordingJudge

GENERATE = StageKey.COVER_LETTER_GENERATE
REVIEW = StageKey.COVER_LETTER_REVIEW
RUBRICS = Path(evals.graders.__file__).parent / "rubrics"
JD = (FIXTURES / "jds" / "backend-platform-match.md").read_text(encoding="utf-8")
ANALYSIS = {"stage1_analysis": recorded_json("stage1_analysis.json")}
CASE = CASE_BY_ID["backend-platform-match"]


def _letter(**changes: Any) -> dict[str, Any]:
    return {**COVER_LETTER.model_dump(), **changes}


def _case(**cover_letter: Any) -> EvalCase:
    return CASE.model_copy(
        update={"cover_letter": CASE.letter.model_copy(update=cover_letter)}
    )


async def _grade(grader: Any, output: object, **options: Any) -> Grade:
    ctx = make_context(
        options.pop("stage", GENERATE),
        output,  # type: ignore[arg-type]
        case=options.pop("case", CASE),
        jd_text=options.pop("jd_text", JD),
        reference=options.pop("reference", ANALYSIS),
        **options,
    )
    grade = await grader.grade(ctx)
    assert grade is not None
    return grade


def _failed_rules(grade: Grade) -> list[str]:
    return [failure["rule"] for failure in grade.details["failures"]]


class TestSchema:
    async def test_a_valid_letter_scores_one(self) -> None:
        grade = await _grade(SchemaGrader(), _letter())
        assert grade.score == 1.0

    async def test_a_letter_without_paragraphs_scores_zero(self) -> None:
        output = _letter()
        del output["body_paragraphs"]
        assert (await _grade(SchemaGrader(), output)).score == 0.0

    async def test_a_valid_review_scores_one(self) -> None:
        grade = await _grade(
            SchemaGrader(), COVER_LETTER_REVIEW.model_dump(), stage=REVIEW
        )
        assert grade.score == 1.0


class TestRules:
    grader = CoverLetterRulesGrader()

    def test_the_grader_is_named_cover_letter_rules(self) -> None:
        assert self.grader.name == "cover_letter_rules"

    async def test_the_recorded_letter_passes_every_rule(self) -> None:
        grade = await _grade(self.grader, _letter())
        assert (grade.score, grade.passed, grade.details["failures"]) == (
            1.0,
            True,
            [],
        )

    async def test_a_short_letter_fails_the_word_bounds(self) -> None:
        grade = await _grade(self.grader, _letter(body_paragraphs=["Short."]))
        assert _failed_rules(grade) == ["C1"]
        assert grade.score == pytest.approx(6 / 7)

    async def test_the_case_sets_the_word_bounds(self) -> None:
        grade = await _grade(self.grader, _letter(), case=_case(max_words=200))
        assert _failed_rules(grade) == ["C1"]

    async def test_too_many_body_paragraphs_fail(self) -> None:
        body = COVER_LETTER.body_paragraphs
        grade = await _grade(
            self.grader,
            _letter(body_paragraphs=[body[0][:60], body[1][:60], "a.", "b."]),
            case=_case(min_words=1),
        )
        assert _failed_rules(grade) == ["C2"]

    async def test_first_person_plural_fails(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(
                closing_paragraph=COVER_LETTER.closing_paragraph + " We shipped it."
            ),
        )
        assert _failed_rules(grade) == ["C3"]

    async def test_the_abbreviation_us_is_not_first_person(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(
                closing_paragraph=COVER_LETTER.closing_paragraph + " I am in the US."
            ),
        )
        assert grade.passed is True

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("salutation", "Dear [Name],"),
            ("opening_paragraph", COVER_LETTER.opening_paragraph + " [Company]"),
            ("closing_paragraph", COVER_LETTER.closing_paragraph + " {company}"),
            (
                "closing_paragraph",
                COVER_LETTER.closing_paragraph + " Insert team here.",
            ),
        ],
    )
    async def test_placeholder_text_fails(self, field: str, value: str) -> None:
        grade = await _grade(self.grader, _letter(**{field: value}))
        assert "C4" in _failed_rules(grade)

    async def test_a_wrong_company_fails(self) -> None:
        grade = await _grade(self.grader, _letter(company="Globex"))
        assert _failed_rules(grade) == ["C5"]

    async def test_a_letter_that_never_names_the_company_fails(self) -> None:
        letter = _letter(
            opening_paragraph=COVER_LETTER.opening_paragraph.replace(
                "Acme Corp", "the"
            ),
            closing_paragraph=COVER_LETTER.closing_paragraph.replace(
                "Acme Corp", "your team"
            ),
        )
        assert "C5" in _failed_rules(await _grade(self.grader, letter))

    async def test_the_case_can_name_the_expected_company(self) -> None:
        grade = await _grade(self.grader, _letter(), case=_case(company="Initech"))
        assert "C5" in _failed_rules(grade)

    async def test_without_an_expected_company_the_rule_is_not_checked(self) -> None:
        grade = await _grade(self.grader, _letter(company="Globex"), reference={})
        assert "C5" not in grade.details["checked"]
        assert "C5" not in _failed_rules(grade)

    async def test_a_wrong_role_fails(self) -> None:
        grade = await _grade(self.grader, _letter(role_title="Data Scientist"))
        assert _failed_rules(grade) == ["C6"]

    async def test_a_candidate_name_not_in_the_knowledge_base_fails(self) -> None:
        grade = await _grade(self.grader, _letter(candidate_name="Jordan Smith"))
        assert _failed_rules(grade) == ["C7"]

    async def test_an_output_that_is_not_a_letter_scores_zero(self) -> None:
        grade = await _grade(self.grader, {"letter": "hi"})
        assert (grade.score, grade.passed) == (0.0, False)
        assert "error" in grade.details


class TestFaithfulness:
    grader = CoverLetterFaithfulnessGrader()

    def test_it_is_gated_as_deterministic_faithfulness(self) -> None:
        assert self.grader.name == "faithfulness_extraction"

    async def test_the_recorded_letter_is_faithful(self) -> None:
        grade = await _grade(self.grader, _letter())
        assert (grade.passed, grade.details["violations"]) == (True, [])
        assert grade.details["checked"] > 10

    async def test_a_number_absent_from_the_kb_and_jd_is_a_violation(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(closing_paragraph="I saved Initech $2.4M in one year."),
        )
        assert {"type": "number", "text": "$2.4M"} in grade.details["violations"]
        assert grade.passed is False

    async def test_a_number_from_the_job_description_is_fine(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(
                closing_paragraph="I would like to help run more than 60 services."
            ),
        )
        assert grade.passed is True

    async def test_a_name_absent_from_the_kb_and_jd_is_a_violation(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(closing_paragraph="I also led the platform team at Google."),
        )
        assert {"type": "name", "text": "Google"} in grade.details["violations"]

    async def test_the_first_word_of_a_sentence_is_not_a_name(self) -> None:
        grade = await _grade(
            self.grader, _letter(closing_paragraph="Thanks for reading this letter.")
        )
        assert grade.passed is True

    async def test_a_forbidden_claim_is_a_violation(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(closing_paragraph="I trained models in PyTorch."),
            case=CASE_BY_ID["backend-ml-stretch"],
        )
        assert {"type": "forbidden_claim", "text": "PyTorch"} in grade.details[
            "violations"
        ]

    async def test_an_honest_gap_is_not_a_claim(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(closing_paragraph="I have not used PyTorch in production yet."),
            case=CASE_BY_ID["backend-ml-stretch"],
        )
        types = [v["type"] for v in grade.details["violations"]]
        assert "forbidden_claim" not in types

    async def test_must_not_claim_applies_too(self) -> None:
        grade = await _grade(
            self.grader,
            _letter(closing_paragraph="I led a team of twenty engineers."),
            case=_case(must_not_claim=["team of twenty"]),
        )
        assert {"type": "forbidden_claim", "text": "team of twenty"} in grade.details[
            "violations"
        ]


class TestFaithfulnessJudge:
    grader = CoverLetterFaithfulnessJudgeGrader()

    def _judge(self, *verdicts: str) -> RecordingJudge:
        return RecordingJudge(
            FaithfulnessJudgement(
                items=[
                    FaithfulnessVerdict(index=i, verdict=v, evidence="KB")  # type: ignore[arg-type]
                    for i, v in enumerate(verdicts, start=1)
                ]
            )
        )

    def test_it_is_gated_as_judged_faithfulness(self) -> None:
        assert self.grader.name == "faithfulness_judge"

    async def test_every_sentence_is_judged(self) -> None:
        judge = self._judge(*["supported"] * 10)
        grade = await _grade(
            self.grader,
            _letter(),
            judge=judge,
            judge_model="m",
            judge_provider="anthropic",
        )
        assert (grade.score, grade.passed) == (1.0, True)
        user = judge.requests[0]["messages"][1]["content"]
        assert "10. " in user
        assert "11. " not in user

    async def test_the_judge_sees_the_rubric_the_jd_and_what_not_to_claim(
        self,
    ) -> None:
        judge = self._judge(*["supported"] * 10)
        await _grade(
            self.grader,
            _letter(),
            case=_case(must_not_claim=["MLflow"]),
            judge=judge,
            judge_model="m",
            judge_provider="anthropic",
        )
        system, user = (m["content"] for m in judge.requests[0]["messages"])
        assert system == (RUBRICS / "cover_letter_faithfulness.md").read_text()
        assert "Acme Corp" in user
        assert "MLflow" in user

    async def test_the_faithfulness_judge_sees_the_must_not_rules(self) -> None:
        judge = self._judge(*["supported"] * 10)
        await _grade(
            self.grader,
            _letter(),
            case=_case(must_not=["invent a reason for leaving"]),
            judge=judge,
            judge_model="m",
            judge_provider="anthropic",
        )
        assert (
            "invent a reason for leaving" in judge.requests[0]["messages"][1]["content"]
        )

    async def test_one_unsupported_sentence_fails(self) -> None:
        judge = self._judge(*["supported"] * 9, "unsupported")
        grade = await _grade(
            self.grader, _letter(), judge=judge, judge_model="m", judge_provider="x"
        )
        assert grade.passed is False


class TestCoverLetterJudge:
    grader = CoverLetterJudgeGrader()
    CRITERIA = (
        "evidence_connection",
        "specificity",
        "persuasiveness",
        "professional_tone",
    )

    def _judge(self, score: int = 4) -> RecordingJudge:
        return RecordingJudge(
            RubricJudgement(
                criteria=[
                    CriterionScore(name=name, score=score, rationale="r")
                    for name in self.CRITERIA
                ],
                summary="s",
            )
        )

    def test_it_scores_the_documented_criteria(self) -> None:
        assert self.grader.name == "cover_letter_judge"
        assert self.grader.criteria == self.CRITERIA

    def test_the_rubric_names_every_criterion(self) -> None:
        rubric = (RUBRICS / "cover_letter.md").read_text()
        assert rubric.startswith("Return only the JSON object")
        for name in self.CRITERIA:
            assert f"`{name}`" in rubric

    async def test_the_score_is_the_mean_criterion_over_five(self) -> None:
        grade = await _grade(
            self.grader, _letter(), judge=self._judge(4), judge_model="m"
        )
        assert grade.score == pytest.approx(0.8)

    async def test_the_judge_sees_the_connections_a_strong_letter_makes(
        self,
    ) -> None:
        judge = self._judge()
        await _grade(
            self.grader,
            _letter(),
            case=_case(should_connect=["Kubernetes migration -> cluster upgrades"]),
            judge=judge,
            judge_model="m",
        )
        user = judge.requests[0]["messages"][1]["content"]
        assert "Kubernetes migration -> cluster upgrades" in user

    async def test_the_judge_sees_what_the_letter_must_and_must_not_do(
        self,
    ) -> None:
        judge = self._judge()
        await _grade(
            self.grader,
            _letter(),
            case=_case(must=["lead with OTIF"], must_not=["claim SAP"]),
            judge=judge,
            judge_model="m",
        )
        user = judge.requests[0]["messages"][1]["content"]
        assert "lead with OTIF" in user
        assert "claim SAP" in user

    async def test_without_connections_none_are_listed(self) -> None:
        judge = self._judge()
        await _grade(self.grader, _letter(), judge=judge, judge_model="m")
        assert "connect" not in judge.requests[0]["messages"][1]["content"].lower()


class TestCoverLetterDefectRecall:
    grader = CoverLetterDefectGrader()
    DEFECTS = ("the placeholder [Company] is left in", "a metric not in the KB")

    def test_it_is_named_cover_letter_defect_recall(self) -> None:
        assert self.grader.name == "cover_letter_defect_recall"

    def test_it_applies_only_to_cases_with_seeded_defects(self) -> None:
        assert self.grader.applies_to(_case(review_defects=list(self.DEFECTS)))
        assert not self.grader.applies_to(CASE)

    async def test_the_score_is_the_share_of_defects_found(self) -> None:
        judge = RecordingJudge(
            DefectJudgement(
                findings=[
                    DefectFinding(defect=self.DEFECTS[0], detected=True, quote="q"),
                    DefectFinding(defect=self.DEFECTS[1], detected=False, quote=""),
                ]
            )
        )
        grade = await _grade(
            self.grader,
            COVER_LETTER_REVIEW.model_dump(),
            stage=REVIEW,
            case=_case(review_defects=list(self.DEFECTS)),
            judge=judge,
            judge_model="m",
        )
        assert grade.score == 0.5
        system = judge.requests[0]["messages"][0]["content"]
        assert system == (RUBRICS / "cover_letter_review_defects.md").read_text()

    async def test_a_case_without_defects_is_not_graded(self) -> None:
        ctx = make_context(
            REVIEW,
            COVER_LETTER_REVIEW.model_dump(),
            case=CASE,
            judge=RecordingJudge(),
            judge_model="m",
        )
        assert await self.grader.grade(ctx) is None
