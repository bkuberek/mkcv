"""Tests for producing reference artifacts (design 9.4 and 9.8)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dynaconf import Dynaconf
from pydantic import BaseModel

from evals.harness.case_loader import load_cases
from evals.harness.reference_bootstrapper import ReferenceBootstrapper
from evals.models.cover_letter_expectations import CoverLetterExpectations
from evals.models.eval_case import REFERENCE_FILES, EvalCase
from evals.models.judge_config import JudgeConfig
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.conftest import COVER_LETTER, RECORDED_DIR, FailingStub

REFERENCE = JudgeConfig(provider="stub", model="stub-model")
ALL_FILES = [name for names in REFERENCE_FILES.values() for name in names]
UPSTREAM_FILES = [
    "stage1_analysis.json",
    "stage2_selection.json",
    "stage3_content.json",
]


@pytest.fixture
def cases(tmp_fixtures: Path) -> list[EvalCase]:
    """``alpha-match`` and ``alpha-probe`` (same persona and JD, review only)."""
    return load_cases(tmp_fixtures)


@pytest.fixture
def bootstrapper(make_settings: Callable[..., Dynaconf]) -> ReferenceBootstrapper:
    return ReferenceBootstrapper(
        make_settings(), reference=REFERENCE, preset="standard"
    )


def _written(case: EvalCase) -> list[str]:
    return (
        sorted(p.name for p in case.reference_dir.glob("*"))
        if case.reference_dir.is_dir()
        else []
    )


class TestBootstrapACase:
    async def test_it_writes_every_reference_file(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        assert _written(cases[0]) == sorted(ALL_FILES)

    async def test_the_written_case_has_a_complete_reference(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        assert cases[0].reference_stages() == [
            StageKey.ANALYZE,
            StageKey.SELECT,
            StageKey.TAILOR,
            StageKey.STRUCTURE,
            StageKey.COVER_LETTER_GENERATE,
        ]

    async def test_it_runs_stages_one_to_four_then_the_cover_letter(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        assert [c.get("response_model") for c in canned_stub.call_log] == [
            "JDAnalysis",
            "ExperienceSelection",
            "TailoredContent",
            None,
            "CoverLetter",
        ]

    async def test_the_cover_letter_is_the_models_letter(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        written = (cases[0].reference_dir / "cover_letter_content.json").read_text()
        assert CoverLetter.model_validate_json(written) == COVER_LETTER

    async def test_the_artifacts_are_the_models_output(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        written = json.loads(
            (cases[0].reference_dir / "stage3_content.json").read_text()
        )
        recorded = json.loads((RECORDED_DIR / "stage3_content.json").read_text())
        assert written == recorded

    async def test_the_outcome_reports_the_case_as_written(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap(cases[:1], cases)
        assert (outcome.case_id, outcome.status) == ("alpha-match", "written")

    async def test_nothing_is_left_behind_in_the_fixtures_besides_the_reference(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_fixtures: Path,
    ) -> None:
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        assert sorted(p.name for p in tmp_fixtures.iterdir()) == [
            "cases.toml",
            "jds",
            "personas",
            "reference",
        ]


class TestNeverOverwrites:
    async def test_a_case_with_any_reference_file_is_skipped(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        cases[0].reference_dir.mkdir(parents=True)
        (cases[0].reference_dir / "stage1_analysis.json").write_text("reviewed")
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap(cases[:1], cases)
        assert outcome.status == "skipped"
        assert "already exists" in outcome.detail

    async def test_a_skipped_case_is_left_untouched_and_costs_nothing(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        cases[0].reference_dir.mkdir(parents=True)
        (cases[0].reference_dir / "stage1_analysis.json").write_text("reviewed")
        install_adapter(canned_stub)
        await bootstrapper.bootstrap(cases[:1], cases)
        assert (
            cases[0].reference_dir / "stage1_analysis.json"
        ).read_text() == "reviewed"
        assert canned_stub.call_log == []


class TestFailures:
    async def test_a_failing_model_is_an_error_outcome_and_writes_nothing(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(FailingStub())
        [outcome] = await bootstrapper.bootstrap(cases[:1], cases)
        assert outcome.status == "error"
        assert "boom" in outcome.detail
        assert _written(cases[0]) == []

    async def test_the_next_case_is_still_bootstrapped_after_a_failure(
        self,
        bootstrapper: ReferenceBootstrapper,
        tmp_fixtures: Path,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        second = cases[0].model_copy(update={"id": "alpha-second"})

        class FailsOnce(StubLLMAdapter):
            failed = False

            async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
                if not self.failed:
                    self.failed = True
                    raise ProviderError("boom")
                return await canned_stub.complete_structured(*args, **kwargs)

            async def complete(self, *args: Any, **kwargs: Any) -> str:
                return await canned_stub.complete(*args, **kwargs)

        install_adapter(FailsOnce())
        outcomes = await bootstrapper.bootstrap([cases[0], second], [cases[0], second])
        assert [o.status for o in outcomes] == ["error", "written"]


class TestReviewProbe:
    """The probe copies stages 1-3 from the case with the same persona and JD."""

    def _bootstrapped_donor(
        self, add_reference: Callable[..., None], cases: list[EvalCase]
    ) -> None:
        add_reference(cases[0], [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR])

    async def test_stages_one_to_three_are_copied_from_the_donor(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        add_reference: Callable[..., None],
    ) -> None:
        self._bootstrapped_donor(add_reference, cases)
        [outcome] = await bootstrapper.bootstrap(cases[1:], cases)
        assert outcome.status == "written"
        assert _written(cases[1]) == sorted(UPSTREAM_FILES)

    async def test_stage_four_files_are_never_written(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(cases[0])
        await bootstrapper.bootstrap(cases[1:], cases)
        assert not (cases[1].reference_dir / "resume.yaml").exists()
        assert not (cases[1].reference_dir / "stage4_structure.json").exists()

    async def test_existing_stage_four_files_are_left_alone(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(cases[0])
        cases[1].reference_dir.mkdir(parents=True)
        (cases[1].reference_dir / "resume.yaml").write_text("hand-written")
        await bootstrapper.bootstrap(cases[1:], cases)
        assert (cases[1].reference_dir / "resume.yaml").read_text() == "hand-written"

    async def test_existing_upstream_files_are_not_replaced(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(cases[0])
        cases[1].reference_dir.mkdir(parents=True)
        (cases[1].reference_dir / "stage1_analysis.json").write_text("reviewed")
        await bootstrapper.bootstrap(cases[1:], cases)
        assert (
            cases[1].reference_dir / "stage1_analysis.json"
        ).read_text() == "reviewed"

    async def test_a_probe_with_everything_already_copied_is_skipped(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(cases[0])
        add_reference(cases[1], [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR])
        [outcome] = await bootstrapper.bootstrap(cases[1:], cases)
        assert outcome.status == "skipped"

    async def test_a_donor_without_a_reference_is_an_error(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
    ) -> None:
        [outcome] = await bootstrapper.bootstrap(cases[1:], cases)
        assert outcome.status == "error"
        assert "alpha-match" in outcome.detail

    async def test_a_probe_with_no_donor_is_an_error(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
    ) -> None:
        lonely = cases[1].model_copy(update={"jd": "jds/other.md"})
        [outcome] = await bootstrapper.bootstrap([lonely], [lonely])
        assert outcome.status == "error"
        assert "same persona and job description" in outcome.detail

    async def test_the_donor_is_bootstrapped_before_the_probe(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        outcomes = await bootstrapper.bootstrap([cases[1], cases[0]], cases)
        assert [(o.case_id, o.status) for o in outcomes] == [
            ("alpha-match", "written"),
            ("alpha-probe", "written"),
        ]
        assert _written(cases[1]) == sorted(UPSTREAM_FILES)


class TestCoverLetterReference:
    async def test_a_case_with_stages_one_to_four_gets_only_the_letter(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(
            cases[0],
            [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR, StageKey.STRUCTURE],
        )
        (cases[0].reference_dir / "stage1_analysis.json").write_text(
            (RECORDED_DIR / "stage1_analysis.json").read_text() + "\n"
        )
        before = (cases[0].reference_dir / "stage1_analysis.json").read_text()
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap(cases[:1], cases)
        assert (outcome.status, outcome.detail) == ("written", "cover letter")
        assert [c["response_model"] for c in canned_stub.call_log] == ["CoverLetter"]
        assert (cases[0].reference_dir / "stage1_analysis.json").read_text() == before

    async def test_an_existing_letter_is_never_replaced(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        add_reference(cases[0])
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap(cases[:1], cases)
        assert outcome.status == "skipped"
        assert canned_stub.call_log == []

    async def test_a_case_that_does_not_review_letters_gets_none(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        resume_only = cases[0].model_copy(update={"stages": [StageKey.TAILOR]})
        install_adapter(canned_stub)
        await bootstrapper.bootstrap([resume_only], [resume_only])
        assert "cover_letter_content.json" not in _written(resume_only)

    async def test_a_cover_letter_probe_needs_a_hand_written_letter(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        probe = _letter_probe(cases[0])
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap([probe], [probe])
        assert outcome.status == "error"
        assert "hand-written" in outcome.detail
        assert canned_stub.call_log == []

    async def test_a_cover_letter_probe_with_its_letter_is_skipped(
        self,
        bootstrapper: ReferenceBootstrapper,
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        probe = _letter_probe(cases[0])
        add_reference(probe, [StageKey.COVER_LETTER_GENERATE])
        install_adapter(canned_stub)
        [outcome] = await bootstrapper.bootstrap([probe], [probe])
        assert outcome.status == "skipped"
        assert canned_stub.call_log == []


def _letter_probe(case: EvalCase) -> EvalCase:
    return case.model_copy(
        update={
            "id": "letter-probe",
            "stages": [StageKey.COVER_LETTER_REVIEW],
            "cover_letter": CoverLetterExpectations(
                review_defects=["a placeholder [Company]"]
            ),
        }
    )
