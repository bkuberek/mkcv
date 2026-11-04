"""Tests for stage-isolated runs (REQ-EV-3 to REQ-EV-6, design 9.5)."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from dynaconf import Dynaconf
from pydantic import BaseModel

from evals.harness.case_loader import load_cases
from evals.harness.stage_runner import StageRunner, work_dir_for
from evals.harness.stop_after_stage import StopAfterStage
from evals.models.eval_case import EvalCase
from evals.models.matrix_model import MatrixModel
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_key import PIPELINE_STAGE_NUMBERS, PIPELINE_STAGES, StageKey
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.stage_callback import StageCallbackPort
from tests.test_evals.conftest import RESUME_YAML, FailingStub, UsageStub, recorded

MODEL = MatrixModel(provider="stub", model="stub-model")
RESPONSE_MODEL_FOR_STAGE: dict[StageKey, type[BaseModel] | None] = {
    StageKey.ANALYZE: JDAnalysis,
    StageKey.SELECT: ExperienceSelection,
    StageKey.TAILOR: TailoredContent,
    StageKey.STRUCTURE: None,
    StageKey.REVIEW: ReviewReport,
}


def _metadata(stage_number: int = 3) -> StageMetadata:
    return StageMetadata(
        stage_number=stage_number,
        stage_name="tailor_content",
        provider="stub",
        model="stub-model",
        temperature=0.5,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0,
        duration_seconds=0.1,
    )


@pytest.fixture
def case(tmp_fixtures: Path) -> EvalCase:
    return load_cases(tmp_fixtures)[0]


@pytest.fixture
def runner(make_settings: Callable[..., Dynaconf]) -> StageRunner:
    return StageRunner(make_settings(), preset="standard")


class TestStopAfterStage:
    def test_it_is_a_stage_callback(self) -> None:
        assert isinstance(StopAfterStage(3), StageCallbackPort)

    def test_completing_the_target_stage_stops_the_pipeline(self) -> None:
        assert (
            StopAfterStage(3).on_stage_complete(3, "tailor_content", _metadata())
            is False
        )

    def test_completing_the_target_stage_stores_its_metadata(self) -> None:
        callback = StopAfterStage(3)
        meta = _metadata()
        callback.on_stage_complete(3, "tailor_content", meta)
        assert callback.metadata == meta

    def test_other_stages_let_the_pipeline_continue(self) -> None:
        assert StopAfterStage(3).on_stage_complete(2, "select", _metadata(2)) is True

    def test_other_stages_store_nothing(self) -> None:
        callback = StopAfterStage(3)
        callback.on_stage_complete(2, "select", _metadata(2))
        assert callback.metadata is None

    def test_starting_a_stage_does_nothing(self) -> None:
        assert StopAfterStage(3).on_stage_start(3) is None


class TestRunsExactlyOneStage:
    """REQ-EV-3."""

    async def test_the_stub_receives_one_structured_call_for_the_stage(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        await runner.run(case, StageKey.TAILOR, MODEL, 0, tmp_path / "work")
        calls = canned_stub.call_log
        assert [(c["method"], c["response_model"]) for c in calls] == [
            ("complete_structured", "TailoredContent")
        ]

    async def test_the_run_is_ok_with_the_canned_payload(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.TAILOR, MODEL, 0, tmp_path / "work")
        assert result.status == "ok"
        assert result.payload == recorded(TailoredContent).model_dump()

    @pytest.mark.parametrize("stage", PIPELINE_STAGES)
    async def test_every_stage_makes_exactly_one_call(
        self,
        stage: StageKey,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        await runner.run(case, stage, MODEL, 0, tmp_path / "work")
        expected = RESPONSE_MODEL_FOR_STAGE[stage]
        assert [c.get("response_model") for c in canned_stub.call_log] == [
            expected.__name__ if expected else None
        ]

    @pytest.mark.parametrize("stage", PIPELINE_STAGES)
    async def test_the_metadata_belongs_to_the_stage_that_ran(
        self,
        stage: StageKey,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        result = await runner.run(case, stage, MODEL, 0, tmp_path / "work")
        assert result.metadata is not None
        assert result.metadata.stage_number == PIPELINE_STAGE_NUMBERS[stage]

    async def test_the_structure_stage_returns_the_yaml_text(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.STRUCTURE, MODEL, 0, tmp_path / "work")
        assert isinstance(result.payload, str)
        assert result.payload.startswith("cv:")

    async def test_the_review_stage_reads_the_reference_resume(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        await runner.run(case, StageKey.REVIEW, MODEL, 0, tmp_path / "work")
        prompt = canned_stub.call_log[0]["messages"][0]["content"]
        assert "Alex Rivera" in prompt
        assert RESUME_YAML.splitlines()[1].strip() in prompt

    async def test_the_analyze_stage_needs_no_reference(
        self,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "work")
        assert result.status == "ok"

    async def test_the_stage_uses_the_models_and_default_temperature(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.TAILOR, MODEL, 0, tmp_path / "work")
        assert result.metadata is not None
        assert (result.metadata.provider, result.metadata.model) == (
            "stub",
            "stub-model",
        )
        assert (
            result.metadata.temperature
            == STAGE_REQUIREMENTS[StageKey.TAILOR].default_temperature
        )

    async def test_a_matrix_temperature_overrides_the_stage_default(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        hot = MatrixModel(provider="stub", model="stub-model", temperature=1.0)
        result = await runner.run(case, StageKey.TAILOR, hot, 0, tmp_path / "work")
        assert result.metadata is not None
        assert result.metadata.temperature == 1.0

    async def test_the_reference_artifacts_are_copied_into_the_work_directory(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        install_adapter(canned_stub)
        work = tmp_path / "work"
        await runner.run(case, StageKey.TAILOR, MODEL, 0, work)
        copied = json.loads((work / ".mkcv" / "stage1_analysis.json").read_text())
        assert copied == recorded(JDAnalysis).model_dump()

    async def test_the_reference_is_never_modified(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        before = (case.reference_dir / "stage3_content.json").read_text()
        install_adapter(canned_stub)
        await runner.run(case, StageKey.TAILOR, MODEL, 0, tmp_path / "work")
        assert (case.reference_dir / "stage3_content.json").read_text() == before

    async def test_tokens_and_cost_come_from_the_stage_metadata(
        self,
        runner: StageRunner,
        case: EvalCase,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(UsageStub(responses={JDAnalysis: recorded(JDAnalysis)}))
        haiku = MatrixModel(provider="anthropic", model="claude-haiku-5-5")
        result = await runner.run(case, StageKey.ANALYZE, haiku, 0, tmp_path / "work")
        assert result.metadata is not None
        assert (
            result.metadata.input_tokens,
            result.metadata.output_tokens,
            result.metadata.cost_usd,
        ) == (1000, 500, pytest.approx(0.00035))


class TestMissingReference:
    """REQ-EV-4."""

    @pytest.mark.parametrize("stage", PIPELINE_STAGES[1:])
    async def test_a_stage_without_references_is_skipped(
        self,
        stage: StageKey,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        result = await runner.run(case, stage, MODEL, 0, tmp_path / "work")
        assert result.status == "skipped"
        assert result.error is not None
        assert "bootstrap-reference" in result.error

    async def test_no_model_is_called_for_a_skipped_stage(
        self,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await runner.run(case, StageKey.SELECT, MODEL, 0, tmp_path / "work")
        assert canned_stub.call_log == []

    async def test_the_message_names_the_missing_stages(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case, [StageKey.ANALYZE])
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.REVIEW, MODEL, 0, tmp_path / "work")
        assert result.error is not None
        assert "select, tailor, structure" in result.error

    async def test_a_skipped_run_has_no_payload_or_metadata(
        self,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.SELECT, MODEL, 0, tmp_path / "work")
        assert (result.payload, result.metadata) == (None, None)


class TestErrorsAreRecorded:
    """REQ-EV-5."""

    async def test_a_provider_error_becomes_an_error_run(
        self,
        runner: StageRunner,
        case: EvalCase,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(FailingStub())
        result = await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "work")
        assert result.status == "error"
        assert result.error is not None
        assert "boom" in result.error

    async def test_an_error_run_has_no_payload(
        self,
        runner: StageRunner,
        case: EvalCase,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(FailingStub())
        result = await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "work")
        assert result.payload is None

    async def test_a_stub_without_a_canned_response_is_an_error_run(
        self,
        runner: StageRunner,
        case: EvalCase,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(StubLLMAdapter())
        result = await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "work")
        assert result.status == "error"
        assert result.error is not None
        assert "No canned response" in result.error

    async def test_the_runner_keeps_going_after_an_error(
        self,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(FailingStub())
        await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "first")
        install_adapter(canned_stub)
        second = await runner.run(case, StageKey.ANALYZE, MODEL, 0, tmp_path / "second")
        assert second.status == "ok"

    async def test_an_unknown_provider_is_an_error_run(
        self,
        runner: StageRunner,
        case: EvalCase,
        tmp_path: Path,
    ) -> None:
        nowhere = MatrixModel(provider="nowhere", model="m")
        result = await runner.run(case, StageKey.ANALYZE, nowhere, 0, tmp_path / "work")
        assert result.status == "error"
        assert result.error is not None
        assert "Unknown LLM provider 'nowhere'" in result.error

    async def test_a_malformed_reference_artifact_is_an_error_run(
        self,
        runner: StageRunner,
        case: EvalCase,
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        add_reference(case)
        (case.reference_dir / "stage1_analysis.json").write_text('{"company": 1}')
        install_adapter(canned_stub)
        result = await runner.run(case, StageKey.SELECT, MODEL, 0, tmp_path / "work")
        assert result.status == "error"

    async def test_artifacts_from_an_earlier_run_do_not_survive_a_failed_rerun(
        self,
        runner: StageRunner,
        case: EvalCase,
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        work = tmp_path / "work"
        install_adapter(canned_stub)
        await runner.run(case, StageKey.ANALYZE, MODEL, 0, work)
        install_adapter(FailingStub())
        result = await runner.run(case, StageKey.ANALYZE, MODEL, 0, work)
        assert result.status == "error"
        assert not (work / ".mkcv" / "stage1_analysis.json").exists()


class TestPreset:
    async def _structure_prompt(
        self,
        preset: str,
        case: EvalCase,
        settings: Dynaconf,
        add_reference: Callable[..., None],
        stub: StubLLMAdapter,
        work: Path,
    ) -> str:
        add_reference(case)
        await StageRunner(settings, preset=preset).run(
            case, StageKey.STRUCTURE, MODEL, 0, work
        )
        return str(stub.call_log[0]["messages"][0]["content"])

    async def test_the_preset_sets_the_content_density(
        self,
        case: EvalCase,
        make_settings: Callable[..., Dynaconf],
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        prompt = await self._structure_prompt(
            "concise", case, make_settings(), add_reference, canned_stub, tmp_path / "w"
        )
        assert "Be selective" in prompt

    async def test_the_standard_preset_does_not_ask_for_a_selective_resume(
        self,
        case: EvalCase,
        make_settings: Callable[..., Dynaconf],
        add_reference: Callable[..., None],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        prompt = await self._structure_prompt(
            "standard",
            case,
            make_settings(),
            add_reference,
            canned_stub,
            tmp_path / "w",
        )
        assert "Be selective" not in prompt


class TestWorkDirectory:
    """REQ-EV-6."""

    def test_the_directory_ends_with_the_slugged_model_and_repeat(self) -> None:
        model = MatrixModel(provider="openrouter", model="openai/gpt-4o")
        path = work_dir_for(Path("results"), "case", StageKey.TAILOR, model, 0)
        assert path.as_posix().endswith("openrouter__openai_gpt-4o/r0")

    def test_the_directory_nests_case_and_stage_under_raw(self) -> None:
        model = MatrixModel(provider="stub", model="m")
        path = work_dir_for(Path("results"), "alpha", StageKey.SELECT, model, 2)
        assert path == Path("results/raw/alpha/select/stub__m/r2")

    def test_unusual_characters_become_underscores(self) -> None:
        model = MatrixModel(provider="a b", model="llama3.1:8b")
        path = work_dir_for(Path("r"), "c", StageKey.REVIEW, model, 1)
        assert path.parent.name == "a_b__llama3.1_8b"
