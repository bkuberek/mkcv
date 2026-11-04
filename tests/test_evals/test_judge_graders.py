"""Tests for the LLM-judge graders and their rubrics (REQ-EV-12 to REQ-EV-15)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import evals.graders
from evals.graders.faithfulness_judge_grader import FaithfulnessJudgeGrader
from evals.graders.review_defect_grader import ReviewDefectGrader
from evals.graders.selection_judge_grader import SelectionJudgeGrader
from evals.graders.tailoring_judge_grader import TailoringJudgeGrader
from evals.models.criterion_score import CriterionScore
from evals.models.defect_finding import DefectFinding
from evals.models.defect_judgement import DefectJudgement
from evals.models.faithfulness_judgement import FaithfulnessJudgement
from evals.models.faithfulness_verdict import FaithfulnessVerdict
from evals.models.grade import Grade
from evals.models.rubric_judgement import RubricJudgement
from mkcv.adapters.llm.strict_schema import to_strict_json_schema
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import REVIEW_REPORT
from tests.test_evals.grading_support import (
    BACKEND_KB,
    CASE_BY_ID,
    make_context,
    recorded_json,
)

RUBRICS = Path(evals.graders.__file__).parent / "rubrics"
JUDGE_MODEL = "claude-opus-5-5"
LABEL = "anthropic/claude-opus-5-5"
INSTRUCTION = "Return only the JSON object for the requested schema."
JD_TEXT = "Platform Engineer at Acme Corp. Requires Kubernetes and Go."

TAILORING_CRITERIA = (
    "relevance",
    "keyword_integration",
    "impact",
    "clarity",
    "prioritization",
)
SELECTION_CRITERIA = (
    "role_relevance",
    "requirement_coverage",
    "omission_quality",
    "ordering",
)


class RecordingJudge(StubLLMAdapter):
    """A stub judge that keeps the arguments of every structured call."""

    def __init__(self, *responses: BaseModel) -> None:
        super().__init__(responses={type(r): r for r in responses})
        self.requests: list[dict[str, Any]] = []

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        self.requests.append(
            {
                "messages": messages,
                "model": model,
                "response_model": response_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return await super().complete_structured(
            messages,
            model=model,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class WrongJudge(StubLLMAdapter):
    """A judge that answers every request with a rubric judgement."""

    async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
        return RubricJudgement(criteria=[], summary="")


class ExplodingJudge(StubLLMAdapter):
    async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
        raise ProviderError("rate limited")


def _tailored(bullet_count: int = 4) -> dict[str, Any]:
    """The recorded stage 3 output with exactly ``bullet_count`` bullets."""
    output = recorded_json("stage3_content.json")
    bullets = [b for role in output["roles"] for b in role["bullets"]]
    output["roles"][0]["bullets"] = [
        bullets[i % len(bullets)] for i in range(bullet_count)
    ]
    output["roles"][1]["bullets"] = []
    return output


def _bullets(output: dict[str, Any]) -> list[str]:
    return [b["rewritten"] for role in output["roles"] for b in role["bullets"]]


def _verdicts(*verdicts: str) -> FaithfulnessJudgement:
    return FaithfulnessJudgement(
        items=[
            FaithfulnessVerdict(index=i, verdict=v, evidence="KB line")
            for i, v in enumerate(verdicts, start=1)
        ]
    )


def _rubric(
    *scores: int, names: tuple[str, ...] = TAILORING_CRITERIA
) -> RubricJudgement:
    return RubricJudgement(
        criteria=[
            CriterionScore(name=name, score=score, rationale="because")
            for name, score in zip(names, scores, strict=False)
        ],
        summary="Overall fine.",
    )


def _defects(*detected: bool) -> DefectJudgement:
    texts = CASE_BY_ID["review-probe"].review_probe_defects
    return DefectJudgement(
        findings=[
            DefectFinding(defect=text, detected=flag, quote="the review says so")
            for text, flag in zip(texts, detected, strict=True)
        ]
    )


def _judged(
    stage: StageKey,
    output: dict[str, Any] | str | None,
    judge: StubLLMAdapter,
    *,
    case: str = "backend-platform-match",
    judge_provider: str = "anthropic",
    evaluated_provider: str = "openai",
    kb_text: str | None = None,
) -> Any:
    return make_context(
        stage,
        output,
        case=case,
        kb_text=kb_text,
        jd_text=JD_TEXT,
        judge=judge,
        judge_model=JUDGE_MODEL,
        judge_provider=judge_provider,
        evaluated_provider=evaluated_provider,
    )


async def _grade(grader: Any, ctx: Any) -> Grade:
    grade = await grader.grade(ctx)
    assert grade is not None
    return grade  # type: ignore[no-any-return]


class TestJudgeResponseModels:
    @pytest.mark.parametrize("score", [1, 3, 5])
    def test_a_criterion_score_from_one_to_five_is_valid(self, score: int) -> None:
        assert CriterionScore(name="x", score=score, rationale="y").score == score

    @pytest.mark.parametrize("score", [0, 6, -1])
    def test_a_criterion_score_outside_one_to_five_is_rejected(
        self, score: int
    ) -> None:
        with pytest.raises(ValidationError):
            CriterionScore(name="x", score=score, rationale="y")

    def test_an_unknown_faithfulness_verdict_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FaithfulnessVerdict(index=1, verdict="mostly", evidence="")

    @pytest.mark.parametrize(
        "model", [FaithfulnessJudgement, RubricJudgement, DefectJudgement]
    )
    def test_each_response_model_has_a_strict_json_schema(
        self, model: type[BaseModel]
    ) -> None:
        schema = to_strict_json_schema(model)
        assert schema["type"] == "object"


class TestRubricFiles:
    @pytest.mark.parametrize(
        "name", ["faithfulness", "selection", "tailoring", "review_defects"]
    )
    def test_each_rubric_starts_with_the_json_only_instruction(self, name: str) -> None:
        text = (RUBRICS / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith(INSTRUCTION)

    def test_the_tailoring_rubric_lists_its_five_criteria(self) -> None:
        text = (RUBRICS / "tailoring.md").read_text(encoding="utf-8")
        assert all(f"`{name}`" in text for name in TAILORING_CRITERIA)

    def test_the_selection_rubric_lists_its_four_criteria(self) -> None:
        text = (RUBRICS / "selection.md").read_text(encoding="utf-8")
        assert all(f"`{name}`" in text for name in SELECTION_CRITERIA)

    def test_the_rubrics_anchor_the_scale_at_one_three_and_five(self) -> None:
        text = (RUBRICS / "tailoring.md").read_text(encoding="utf-8")
        assert "| 1 | 3 | 5 |" in text

    def test_the_faithfulness_rubric_defines_the_three_verdicts(self) -> None:
        text = (RUBRICS / "faithfulness.md").read_text(encoding="utf-8")
        assert all(f"`{v}`" in text for v in ("supported", "partial", "unsupported"))


class TestFaithfulnessJudge:
    """REQ-EV-12."""

    grader = FaithfulnessJudgeGrader()

    def test_the_grader_is_named_faithfulness_judge(self) -> None:
        assert self.grader.name == "faithfulness_judge"

    async def test_verdicts_score_supported_partial_unsupported_supported(
        self,
    ) -> None:
        judge = RecordingJudge(
            _verdicts("supported", "partial", "unsupported", "supported")
        )
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, _tailored(4), judge))
        assert grade.score == pytest.approx(0.625)
        assert grade.passed is False
        assert grade.details["judge"] == LABEL

    async def test_every_bullet_supported_scores_one_and_passes(self) -> None:
        judge = RecordingJudge(_verdicts(*["supported"] * 4))
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, _tailored(4), judge))
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_a_score_of_exactly_point_nine_passes(self) -> None:
        verdicts = _verdicts(*["supported"] * 9, "unsupported")
        grade = await _grade(
            self.grader,
            _judged(StageKey.TAILOR, _tailored(10), RecordingJudge(verdicts)),
        )
        assert (grade.score, grade.passed) == (0.9, True)

    async def test_a_score_below_point_nine_fails(self) -> None:
        verdicts = _verdicts(*["supported"] * 8, "unsupported", "unsupported")
        grade = await _grade(
            self.grader,
            _judged(StageKey.TAILOR, _tailored(10), RecordingJudge(verdicts)),
        )
        assert (grade.score, grade.passed) == (0.8, False)

    async def test_a_bullet_the_judge_skipped_counts_as_unsupported(self) -> None:
        judge = RecordingJudge(_verdicts("supported", "supported"))
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, _tailored(4), judge))
        assert grade.score == 0.5

    async def test_a_verdict_for_a_bullet_that_does_not_exist_is_ignored(self) -> None:
        judge = RecordingJudge(_verdicts(*["supported"] * 6))
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, _tailored(4), judge))
        assert grade.score == 1.0

    async def test_the_first_verdict_for_an_index_wins(self) -> None:
        verdicts = FaithfulnessJudgement(
            items=[
                FaithfulnessVerdict(index=1, verdict="unsupported", evidence=""),
                FaithfulnessVerdict(index=1, verdict="supported", evidence=""),
            ]
        )
        output = _tailored(1)
        grade = await _grade(
            self.grader, _judged(StageKey.TAILOR, output, RecordingJudge(verdicts))
        )
        assert grade.score == 0.0

    async def test_unsupported_bullets_are_listed_with_the_judges_evidence(
        self,
    ) -> None:
        output = _tailored(2)
        verdicts = FaithfulnessJudgement(
            items=[
                FaithfulnessVerdict(index=1, verdict="supported", evidence="ok"),
                FaithfulnessVerdict(index=2, verdict="unsupported", evidence="no such"),
            ]
        )
        grade = await _grade(
            self.grader, _judged(StageKey.TAILOR, output, RecordingJudge(verdicts))
        )
        [entry] = grade.details["unsupported"]
        assert entry == {
            "index": 2,
            "bullet": _bullets(output)[1],
            "evidence": "no such",
        }

    async def test_the_request_follows_the_design(self) -> None:
        output = _tailored(2)
        judge = RecordingJudge(_verdicts("supported", "supported"))
        await self.grader.grade(_judged(StageKey.TAILOR, output, judge))
        [request] = judge.requests
        assert request["model"] == JUDGE_MODEL
        assert request["response_model"] is FaithfulnessJudgement
        assert request["temperature"] == 0.0
        assert request["max_tokens"] == 8192

    async def test_the_system_message_is_the_rubric(self) -> None:
        judge = RecordingJudge(_verdicts("supported"))
        await self.grader.grade(_judged(StageKey.TAILOR, _tailored(1), judge))
        system, _ = judge.requests[0]["messages"]
        assert system["role"] == "system"
        assert system["content"] == (RUBRICS / "faithfulness.md").read_text(
            encoding="utf-8"
        )

    async def test_the_user_message_holds_the_knowledge_base_and_numbered_bullets(
        self,
    ) -> None:
        output = _tailored(2)
        judge = RecordingJudge(_verdicts("supported", "supported"))
        await self.grader.grade(_judged(StageKey.TAILOR, output, judge))
        _, user = judge.requests[0]["messages"]
        first, second = _bullets(output)
        assert user["role"] == "user"
        assert BACKEND_KB in user["content"]
        assert f"1. {first}" in user["content"]
        assert f"2. {second}" in user["content"]
        assert user["content"].index(BACKEND_KB) < user["content"].index(f"1. {first}")

    async def test_the_original_bullets_are_not_shown_to_the_judge(self) -> None:
        output = _tailored(1)
        output["roles"][0]["bullets"][0]["original"] = "SECRET ORIGINAL TEXT"
        judge = RecordingJudge(_verdicts("supported"))
        await self.grader.grade(_judged(StageKey.TAILOR, output, judge))
        assert "SECRET ORIGINAL TEXT" not in judge.requests[0]["messages"][1]["content"]

    async def test_without_bullets_there_is_nothing_to_judge_and_no_call(self) -> None:
        judge = RecordingJudge(_verdicts("supported"))
        output = _tailored(0)
        assert await self.grader.grade(_judged(StageKey.TAILOR, output, judge)) is None
        assert judge.requests == []

    async def test_without_a_judge_the_grader_does_not_apply(self) -> None:
        ctx = make_context(StageKey.TAILOR, _tailored(2))
        assert await self.grader.grade(ctx) is None

    async def test_a_bullet_without_a_verdict_is_listed_as_unsupported(self) -> None:
        judge = RecordingJudge(_verdicts("supported"))
        output = _tailored(2)
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, output, judge))
        [entry] = grade.details["unsupported"]
        assert entry == {"index": 2, "bullet": _bullets(output)[1], "evidence": ""}

    async def test_a_supported_or_partial_bullet_is_not_listed_as_unsupported(
        self,
    ) -> None:
        judge = RecordingJudge(_verdicts("supported", "partial"))
        grade = await _grade(self.grader, _judged(StageKey.TAILOR, _tailored(2), judge))
        assert grade.details["unsupported"] == []

    async def test_an_answer_of_the_wrong_kind_is_a_provider_error(self) -> None:
        ctx = _judged(StageKey.TAILOR, _tailored(2), WrongJudge())
        with pytest.raises(ProviderError, match="expected FaithfulnessJudgement"):
            await self.grader.grade(ctx)

    async def test_a_judge_failure_propagates_for_the_runner_to_record(self) -> None:
        ctx = _judged(StageKey.TAILOR, _tailored(2), ExplodingJudge())
        with pytest.raises(ProviderError, match="rate limited"):
            await self.grader.grade(ctx)


class TestRubricJudges:
    """REQ-EV-13."""

    def test_the_graders_are_named_after_their_stage_judges(self) -> None:
        assert TailoringJudgeGrader().name == "tailoring_judge"
        assert SelectionJudgeGrader().name == "selection_judge"

    async def test_tailoring_scores_the_mean_criterion_over_five(self) -> None:
        judge = RecordingJudge(_rubric(5, 4, 4, 3, 4))
        grade = await _grade(
            TailoringJudgeGrader(),
            _judged(StageKey.TAILOR, _tailored(), judge),
        )
        assert grade.score == pytest.approx(0.8)
        assert grade.details["judge"] == LABEL

    async def test_selection_uses_the_same_scoring(self) -> None:
        judge = RecordingJudge(_rubric(5, 5, 4, 2, names=SELECTION_CRITERIA))
        output = recorded_json("stage2_selection.json")
        grade = await _grade(
            SelectionJudgeGrader(), _judged(StageKey.SELECT, output, judge)
        )
        assert grade.score == pytest.approx(0.8)

    async def test_the_criteria_and_summary_are_kept_as_details(self) -> None:
        judge = RecordingJudge(_rubric(5, 4, 4, 3, 4))
        grade = await _grade(
            TailoringJudgeGrader(), _judged(StageKey.TAILOR, _tailored(), judge)
        )
        assert grade.details["criteria"][0] == {
            "name": "relevance",
            "score": 5,
            "rationale": "because",
        }
        assert grade.details["summary"] == "Overall fine."

    async def test_a_criterion_the_judge_left_out_is_named(self) -> None:
        judge = RecordingJudge(_rubric(4, 4, 4, 4))
        grade = await _grade(
            TailoringJudgeGrader(), _judged(StageKey.TAILOR, _tailored(), judge)
        )
        assert grade.details["missing_criteria"] == ["prioritization"]
        assert grade.score == pytest.approx(0.8)

    async def test_a_judgement_without_criteria_has_no_score(self) -> None:
        judge = RecordingJudge(RubricJudgement(criteria=[], summary=""))
        grade = await _grade(
            TailoringJudgeGrader(), _judged(StageKey.TAILOR, _tailored(), judge)
        )
        assert grade.score is None
        assert "no criteria" in grade.details["error"]

    async def test_rubric_grades_have_no_pass_threshold(self) -> None:
        judge = RecordingJudge(_rubric(5, 5, 5, 5, 5))
        grade = await _grade(
            TailoringJudgeGrader(), _judged(StageKey.TAILOR, _tailored(), judge)
        )
        assert grade.passed is None

    async def test_the_request_asks_for_a_rubric_judgement(self) -> None:
        judge = RecordingJudge(_rubric(3, 3, 3, 3, 3))
        await TailoringJudgeGrader().grade(_judged(StageKey.TAILOR, _tailored(), judge))
        [request] = judge.requests
        assert request["response_model"] is RubricJudgement
        assert request["model"] == JUDGE_MODEL
        assert request["temperature"] == 0.0
        assert request["messages"][0]["content"] == (
            RUBRICS / "tailoring.md"
        ).read_text(encoding="utf-8")

    async def test_the_user_message_holds_the_job_the_knowledge_base_and_the_output(
        self,
    ) -> None:
        output = _tailored()
        judge = RecordingJudge(_rubric(3, 3, 3, 3, 3))
        await TailoringJudgeGrader().grade(_judged(StageKey.TAILOR, output, judge))
        content = judge.requests[0]["messages"][1]["content"]
        assert JD_TEXT in content
        assert BACKEND_KB in content
        assert json.dumps(output, indent=2) in content

    async def test_the_selection_judge_reads_the_selection_rubric(self) -> None:
        judge = RecordingJudge(_rubric(3, 3, 3, 3, names=SELECTION_CRITERIA))
        output = recorded_json("stage2_selection.json")
        await SelectionJudgeGrader().grade(_judged(StageKey.SELECT, output, judge))
        assert judge.requests[0]["messages"][0]["content"] == (
            RUBRICS / "selection.md"
        ).read_text(encoding="utf-8")

    async def test_without_a_judge_the_grader_does_not_apply(self) -> None:
        ctx = make_context(StageKey.TAILOR, _tailored())
        assert await TailoringJudgeGrader().grade(ctx) is None

    async def test_a_judge_without_a_model_does_not_apply(self) -> None:
        ctx = make_context(StageKey.TAILOR, _tailored(), judge=RecordingJudge())
        assert await TailoringJudgeGrader().grade(ctx) is None

    async def test_a_missing_output_is_not_sent_to_the_judge(self) -> None:
        judge = RecordingJudge(_rubric(3, 3, 3, 3, 3))
        ctx = _judged(StageKey.TAILOR, None, judge)
        grade = await _grade(TailoringJudgeGrader(), ctx)
        assert grade.score is None
        assert judge.requests == []


class TestReviewDefectRecall:
    """REQ-EV-14."""

    grader = ReviewDefectGrader()

    def _context(self, judge: StubLLMAdapter, case: str = "review-probe") -> Any:
        return _judged(StageKey.REVIEW, REVIEW_REPORT.model_dump(), judge, case=case)

    def test_the_grader_is_named_review_defect_recall(self) -> None:
        assert self.grader.name == "review_defect_recall"

    async def test_two_of_three_detected_scores_two_thirds(self) -> None:
        judge = RecordingJudge(_defects(True, True, False))
        grade = await _grade(self.grader, self._context(judge))
        assert grade.score == pytest.approx(2 / 3)
        assert grade.details["judge"] == LABEL

    async def test_all_detected_scores_one(self) -> None:
        judge = RecordingJudge(_defects(True, True, True))
        assert (await _grade(self.grader, self._context(judge))).score == 1.0

    async def test_none_detected_scores_zero(self) -> None:
        judge = RecordingJudge(_defects(False, False, False))
        assert (await _grade(self.grader, self._context(judge))).score == 0.0

    async def test_a_non_probe_case_is_not_graded_and_the_judge_not_called(
        self,
    ) -> None:
        judge = RecordingJudge(_defects(True, True, True))
        ctx = self._context(judge, case="backend-platform-match")
        assert await self.grader.grade(ctx) is None
        assert judge.requests == []

    async def test_the_findings_are_kept_as_details(self) -> None:
        judge = RecordingJudge(_defects(True, False, True))
        grade = await _grade(self.grader, self._context(judge))
        assert [f["detected"] for f in grade.details["findings"]] == [True, False, True]
        assert grade.details["findings"][0]["quote"] == "the review says so"

    async def test_findings_match_the_seeded_defects_by_their_text(self) -> None:
        texts = CASE_BY_ID["review-probe"].review_probe_defects
        findings = DefectJudgement(
            findings=[
                DefectFinding(defect=texts[2].upper(), detected=True, quote="q"),
                DefectFinding(defect=texts[0], detected=False, quote=""),
            ]
        )
        grade = await _grade(self.grader, self._context(RecordingJudge(findings)))
        assert grade.score == pytest.approx(1 / 3)
        assert [f and f["detected"] for f in grade.details["findings"]] == [
            False,
            None,
            True,
        ]

    async def test_paraphrased_findings_are_matched_by_position(self) -> None:
        findings = DefectJudgement(
            findings=[
                DefectFinding(defect="pronoun", detected=True, quote="q"),
                DefectFinding(defect="made-up metric", detected=True, quote="q"),
                DefectFinding(defect="keyword", detected=False, quote=""),
            ]
        )
        grade = await _grade(self.grader, self._context(RecordingJudge(findings)))
        assert grade.score == pytest.approx(2 / 3)

    async def test_a_defect_the_judge_did_not_mention_is_not_detected(self) -> None:
        texts = CASE_BY_ID["review-probe"].review_probe_defects
        findings = DefectJudgement(
            findings=[DefectFinding(defect=texts[2], detected=True, quote="q")]
        )
        grade = await _grade(self.grader, self._context(RecordingJudge(findings)))
        assert grade.score == pytest.approx(1 / 3)
        assert [f and f["detected"] for f in grade.details["findings"]] == [
            None,
            None,
            True,
        ]

    async def test_the_request_asks_for_a_defect_judgement(self) -> None:
        judge = RecordingJudge(_defects(True, True, True))
        await self.grader.grade(self._context(judge))
        [request] = judge.requests
        assert request["response_model"] is DefectJudgement
        assert request["temperature"] == 0.0
        assert request["messages"][0]["content"] == (
            RUBRICS / "review_defects.md"
        ).read_text(encoding="utf-8")

    async def test_the_user_message_lists_the_defects_and_the_review(self) -> None:
        judge = RecordingJudge(_defects(True, True, True))
        await self.grader.grade(self._context(judge))
        content = judge.requests[0]["messages"][1]["content"]
        for position, text in enumerate(
            CASE_BY_ID["review-probe"].review_probe_defects, start=1
        ):
            assert f"{position}. {text}" in content
        assert json.dumps(REVIEW_REPORT.model_dump(), indent=2) in content

    async def test_without_a_judge_the_grader_does_not_apply(self) -> None:
        ctx = make_context(
            StageKey.REVIEW, REVIEW_REPORT.model_dump(), case="review-probe"
        )
        assert await self.grader.grade(ctx) is None


class TestSelfJudged:
    """REQ-EV-15."""

    @pytest.mark.parametrize(
        ("judge_provider", "evaluated_provider", "self_judged"),
        [("anthropic", "anthropic", True), ("anthropic", "openai", False)],
    )
    async def test_every_judge_grade_says_whether_the_model_judged_itself(
        self, judge_provider: str, evaluated_provider: str, self_judged: bool
    ) -> None:
        cases: list[tuple[Any, StageKey, Any, str]] = [
            (
                FaithfulnessJudgeGrader(),
                StageKey.TAILOR,
                _verdicts(*["supported"] * 4),
                "backend-platform-match",
            ),
            (
                TailoringJudgeGrader(),
                StageKey.TAILOR,
                _rubric(3, 3, 3, 3, 3),
                "backend-platform-match",
            ),
            (
                ReviewDefectGrader(),
                StageKey.REVIEW,
                _defects(True, True, True),
                "review-probe",
            ),
        ]
        for grader, stage, response, case in cases:
            output = (
                REVIEW_REPORT.model_dump() if stage is StageKey.REVIEW else _tailored()
            )
            ctx = _judged(
                stage,
                output,
                RecordingJudge(response),
                case=case,
                judge_provider=judge_provider,
                evaluated_provider=evaluated_provider,
            )
            grade = await _grade(grader, ctx)
            assert grade.details["self_judged"] is self_judged, grader.name
