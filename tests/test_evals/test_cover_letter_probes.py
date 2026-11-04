"""Tests for the hand-written cover letter review probes and their planted defects."""

import json
import re

import pytest

from evals.graders.cover_letter_rules_grader import PLACEHOLDER
from evals.graders.cover_letter_text import load_letter, sentences, word_count
from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import (
    claims_term,
    extract_numbers,
    is_supported_number,
    supported_numbers,
)
from evals.harness.reference_bootstrapper import needs_cover_letter
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import CASE_BY_ID

CUSTOMER_SUCCESS = "cover-letter-probe-customer-success"
SECURITY = "cover-letter-probe-security"
PROBES = (CUSTOMER_SUCCESS, SECURITY)
DESIGN = {
    CUSTOMER_SUCCESS: {
        "jd": "jds/customer-success-match.md",
        "invented_number": "130%",
        "lacking_skill": "SQL",
        "wrong_company": "Vantorra",
        "filler": "results-driven team player",
    },
    SECURITY: {
        "jd": "jds/security-cloud-match.md",
        "invented_number": "400",
        "lacking_skill": "Kubernetes",
        "wrong_company": "Fernhill Payments",
        "filler": "can-do spirit",
    },
}


def _letter(case_id: str) -> CoverLetter:
    path = CASE_BY_ID[case_id].reference_dir / "cover_letter_content.json"
    return load_letter(json.loads(path.read_text(encoding="utf-8")))


def _text(letter: CoverLetter) -> str:
    return " ".join(sentences(letter))


@pytest.mark.parametrize("case_id", PROBES)
class TestEveryProbe:
    def test_it_reviews_cover_letters_only(self, case_id: str) -> None:
        case = CASE_BY_ID[case_id]
        assert case.stages == [StageKey.COVER_LETTER_REVIEW]
        assert case.is_cover_letter_probe

    def test_it_pairs_an_existing_persona_with_its_job(self, case_id: str) -> None:
        assert CASE_BY_ID[case_id].jd == DESIGN[case_id]["jd"]

    def test_it_documents_six_planted_defects(self, case_id: str) -> None:
        defects = CASE_BY_ID[case_id].letter.review_defects
        assert len(defects) == 6
        for kind in (
            "invented metric",
            "skill she lacks",
            "wrong company",
            "generic filler",
            "over-length",
        ):
            assert any(kind in defect for defect in defects)

    def test_the_letter_is_a_valid_cover_letter_for_the_persona(
        self, case_id: str
    ) -> None:
        letter = _letter(case_id)
        assert letter.candidate_name in CASE_BY_ID[case_id].kb_text

    def test_the_only_number_missing_from_the_kb_and_jd_is_the_invented_one(
        self, case_id: str
    ) -> None:
        case = CASE_BY_ID[case_id]
        supported = supported_numbers(f"{case.kb_text}\n{case.jd_text}")
        letter = _letter(case_id)
        invented = [
            number
            for sentence in sentences(letter)
            for number in extract_numbers(sentence)
            if not is_supported_number(number, supported)
        ]
        assert invented == [DESIGN[case_id]["invented_number"]]

    def test_it_claims_a_skill_the_kb_lacks(self, case_id: str) -> None:
        case = CASE_BY_ID[case_id]
        skill = DESIGN[case_id]["lacking_skill"]
        assert claims_term(_text(_letter(case_id)), skill)
        assert not claims_term(case.kb_text, skill)

    def test_it_names_a_company_other_than_the_jds(self, case_id: str) -> None:
        case = CASE_BY_ID[case_id]
        wrong = DESIGN[case_id]["wrong_company"]
        assert wrong in _text(_letter(case_id))
        assert wrong not in case.jd_text

    def test_it_has_a_paragraph_of_generic_filler(self, case_id: str) -> None:
        assert DESIGN[case_id]["filler"] in _text(_letter(case_id))

    def test_it_runs_past_the_word_limit(self, case_id: str) -> None:
        limit = CASE_BY_ID[case_id].letter.max_words
        assert word_count(_letter(case_id)) > limit + 40

    def test_bootstrapping_never_writes_its_letter(self, case_id: str) -> None:
        assert not needs_cover_letter(CASE_BY_ID[case_id])

    async def test_the_rules_grader_catches_its_length(self, case_id: str) -> None:
        from evals.graders.cover_letter_rules_grader import CoverLetterRulesGrader

        case = CASE_BY_ID[case_id]
        grade = await CoverLetterRulesGrader().grade(
            GradingContext(
                case=case,
                stage=StageKey.COVER_LETTER_GENERATE,
                kb_text=case.kb_text,
                jd_text=case.jd_text,
                output=_letter(case_id).model_dump(),
            )
        )
        assert "C1" in [failure["rule"] for failure in grade.details["failures"]]


def test_the_customer_success_letter_leaves_a_placeholder() -> None:
    letter = _letter(CUSTOMER_SUCCESS)
    assert PLACEHOLDER.search(letter.opening_paragraph).group() == "[Company]"  # type: ignore[union-attr]


def test_the_security_letter_overloads_the_first_person() -> None:
    found = sentences(_letter(SECURITY))
    starting_with_i = [s for s in found if re.match(r"I\b", s)]
    assert len(starting_with_i) / len(found) >= 0.9


def test_the_other_letter_has_no_placeholder() -> None:
    letter = _letter(SECURITY)
    assert PLACEHOLDER.search(" ".join([letter.salutation, _text(letter)])) is None


def test_the_review_stage_now_has_probes_to_score() -> None:
    probes = [c for c in CASE_BY_ID.values() if c.is_cover_letter_probe]
    assert sorted(c.id for c in probes) == sorted(PROBES)
