"""Tests for the cover letter cases wired from evals/fixtures/cover_letter_cases.md."""

import re

import pytest

from evals.graders.text_normalization import claims_term
from evals.models.eval_case import EvalCase
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import CASE_BY_ID, FIXTURES

SPEC = (FIXTURES / "cover_letter_cases.md").read_text(encoding="utf-8")
SPEC_IDS = re.findall(r"(?m)^## ([a-z0-9-]+)$", SPEC)
LETTER_CASES = [case for case in CASE_BY_ID.values() if case.cover_letter is not None]


def test_the_spec_lists_thirteen_cases() -> None:
    assert len(SPEC_IDS) == 13


def test_exactly_the_spec_cases_write_cover_letters() -> None:
    assert sorted(case.id for case in LETTER_CASES) == sorted(SPEC_IDS)


@pytest.mark.parametrize("case", LETTER_CASES, ids=lambda case: case.id)
def test_each_case_has_must_should_connect_and_must_not_rules(case: EvalCase) -> None:
    letter = case.letter
    assert letter.must
    assert letter.should_connect
    assert letter.must_not


@pytest.mark.parametrize("case", LETTER_CASES, ids=lambda case: case.id)
def test_no_term_the_letter_must_not_claim_is_in_the_knowledge_base(
    case: EvalCase,
) -> None:
    present = [
        term for term in case.cover_letter_forbidden if claims_term(case.kb_text, term)
    ]
    assert present == []


@pytest.mark.parametrize("case", LETTER_CASES, ids=lambda case: case.id)
def test_each_case_runs_both_cover_letter_stages(case: EvalCase) -> None:
    assert case.applies_to(StageKey.COVER_LETTER_GENERATE)
    assert case.applies_to(StageKey.COVER_LETTER_REVIEW)


def test_cases_without_a_table_write_no_letter() -> None:
    others = [case for case in CASE_BY_ID.values() if case.cover_letter is None]
    assert others
    assert not any(case.applies_to(StageKey.COVER_LETTER_GENERATE) for case in others)
