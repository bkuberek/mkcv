"""Tests for the matrix runner and its output files (REQ-EV-19 part, design 9.9)."""

import asyncio
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dynaconf import Dynaconf
from pydantic import BaseModel

from evals.graders.grading_context import GradingContext
from evals.harness.case_loader import load_cases
from evals.harness.eval_runner import EvalRunner, current_git_sha, new_run_id
from evals.models.eval_case import EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.grade import Grade
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_manifest import RunManifest
from evals.models.run_settings import RunSettings
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.conftest import FailingStub, UsageStub, recorded

STUB = MatrixModel(provider="stub", model="stub-model")
HAIKU = MatrixModel(provider="anthropic", model="claude-haiku-5-5")
JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
RUN_ID = "20261104-010203-abc1234"


def _matrix(
    models: list[MatrixModel],
    stages: list[StageKey],
    *,
    repeats: int = 1,
    concurrency: int = 2,
) -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(stages=stages, repeats=repeats, concurrency=concurrency),
        judge=JUDGE,
        reference=JUDGE,
        models=models,
    )


@pytest.fixture
def cases(tmp_fixtures: Path) -> list[EvalCase]:
    return load_cases(tmp_fixtures)


@pytest.fixture
def make_runner(
    make_settings: Callable[..., Dynaconf], tmp_path: Path
) -> Callable[..., EvalRunner]:
    def _make(**options: Any) -> EvalRunner:
        return EvalRunner(
            make_settings(), out_dir=tmp_path / "out", run_id=RUN_ID, **options
        )

    return _make


class TestRecords:
    async def test_one_record_per_model_case_stage_and_repeat(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        matrix = _matrix([STUB], [StageKey.ANALYZE, StageKey.REVIEW], repeats=2)
        records = await make_runner().run(matrix, cases)
        # alpha-match: analyze and review; alpha-probe only reviews; two repeats.
        assert len(records) == (2 + 1) * 2

    async def test_a_case_restricted_to_review_is_not_run_on_other_stages(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        records = await make_runner().run(_matrix([STUB], [StageKey.ANALYZE]), cases)
        assert {r.case_id for r in records} == {"alpha-match"}

    async def test_every_model_is_run(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        records = await make_runner().run(
            _matrix([STUB, HAIKU], [StageKey.ANALYZE]), cases[:1]
        )
        assert {(r.provider, r.model) for r in records} == {
            ("stub", "stub-model"),
            ("anthropic", "claude-haiku-5-5"),
        }

    async def test_records_in_the_return_value_follow_the_plan_order(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        records = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE], repeats=3), cases[:1]
        )
        assert [r.repeat for r in records] == [0, 1, 2]

    async def test_an_ok_record_carries_the_run_identity_and_stage_metadata(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(UsageStub(responses={JDAnalysis: recorded(JDAnalysis)}))
        [record] = await make_runner().run(
            _matrix([HAIKU], [StageKey.ANALYZE]), cases[:1]
        )
        assert record.run_id == RUN_ID
        assert (record.case_id, record.stage, record.status) == (
            "alpha-match",
            StageKey.ANALYZE,
            "ok",
        )
        assert (record.input_tokens, record.output_tokens) == (1000, 500)
        assert record.cost_usd == pytest.approx(0.00035)
        assert record.latency_s >= 0.0
        assert record.error is None

    async def test_latency_is_the_stage_duration(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        class Slow(StubLLMAdapter):
            async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
                await asyncio.sleep(0.05)
                return recorded(JDAnalysis)

        install_adapter(Slow())
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE]), cases[:1]
        )
        assert record.latency_s >= 0.04

    async def test_a_stage_without_a_reference_is_recorded_as_skipped(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.TAILOR]), cases[:1]
        )
        assert record.status == "skipped"
        assert record.error is not None
        assert "bootstrap-reference" in record.error
        assert (record.input_tokens, record.cost_usd) == (0, 0.0)

    async def test_a_failed_stage_is_recorded_and_the_run_continues(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(FailingStub())
        records = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE], repeats=2), cases[:1]
        )
        assert [(r.status, r.repeat) for r in records] == [("error", 0), ("error", 1)]
        assert records[0].error is not None
        assert "boom" in records[0].error


class RecordingGrader:
    """A grader that keeps the contexts it was given."""

    name = "recording"

    def __init__(self) -> None:
        self.contexts: list[GradingContext] = []

    async def grade(self, ctx: GradingContext) -> Grade:
        self.contexts.append(ctx)
        return Grade(name=self.name, score=0.5, passed=False)


class ExplodingGrader:
    name = "exploding"

    async def grade(self, ctx: GradingContext) -> Grade:
        raise ProviderError("judge is down")


class TestGrading:
    """T15: ok records are graded by the stage's graders."""

    async def test_an_ok_analysis_carries_the_deterministic_grades(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE]), cases[:1]
        )
        assert [g.name for g in record.grades] == ["schema", "jd_keyword_recall"]

    async def test_an_ok_tailor_record_carries_schema_and_faithfulness_grades(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        install_adapter(canned_stub)
        add_reference(cases[0], [StageKey.ANALYZE, StageKey.SELECT])
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.TAILOR]), cases[:1]
        )
        assert record.status == "ok"
        assert {g.name for g in record.grades} >= {"schema", "faithfulness_extraction"}

    async def test_the_schema_grade_of_a_valid_artifact_is_one(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE]), cases[:1]
        )
        assert record.grades[0].score == 1.0

    async def test_a_structure_record_is_graded_on_its_yaml(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        install_adapter(canned_stub)
        add_reference(cases[0], [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR])
        [record] = await make_runner().run(
            _matrix([STUB], [StageKey.STRUCTURE]), cases[:1]
        )
        grades = {g.name: g for g in record.grades}
        assert set(grades) == {
            "schema",
            "ats_rules",
            "structure",
            "faithfulness_extraction",
        }
        assert grades["schema"].score == 1.0
        assert grades["structure"].score == 1.0

    async def test_failed_and_skipped_records_are_not_graded(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(FailingStub())
        records = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE, StageKey.TAILOR]), cases[:1]
        )
        assert {r.status for r in records} == {"error", "skipped"}
        assert [r.grades for r in records] == [[], []]

    async def test_graders_see_the_case_the_output_and_the_upstream_references(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        install_adapter(canned_stub)
        add_reference(cases[0], [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR])
        recorder = RecordingGrader()
        runner = make_runner(graders={StageKey.TAILOR: [recorder]})
        await runner.run(_matrix([HAIKU], [StageKey.TAILOR]), cases[:1])
        [ctx] = recorder.contexts
        assert ctx.case.id == "alpha-match"
        assert (ctx.kb_text, ctx.jd_text) == (cases[0].kb_text, cases[0].jd_text)
        assert ctx.output == recorded(TailoredContent).model_dump()
        assert sorted(ctx.reference) == ["stage1_analysis", "stage2_selection"]
        assert ctx.evaluated_provider == "anthropic"

    async def test_the_reference_artifacts_of_the_stage_itself_are_withheld(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        add_reference: Callable[..., None],
    ) -> None:
        install_adapter(canned_stub)
        add_reference(cases[0], [StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR])
        recorder = RecordingGrader()
        runner = make_runner(graders={StageKey.ANALYZE: [recorder]})
        await runner.run(_matrix([STUB], [StageKey.ANALYZE]), cases[:1])
        assert recorder.contexts[0].reference == {}

    async def test_a_grader_that_fails_is_recorded_and_the_run_continues(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        runner = make_runner(
            graders={StageKey.ANALYZE: [ExplodingGrader(), RecordingGrader()]}
        )
        [record] = await runner.run(
            _matrix([STUB], [StageKey.ANALYZE], repeats=1), cases[:1]
        )
        failed, recorded_grade = record.grades
        assert (failed.name, failed.score, failed.passed) == ("exploding", None, None)
        assert "judge is down" in failed.details["error"]
        assert recorded_grade.name == "recording"
        assert record.status == "ok"

    async def test_grades_are_written_to_results_jsonl(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await make_runner().run(_matrix([STUB], [StageKey.ANALYZE]), cases[:1])
        line = (tmp_path / "out" / "results.jsonl").read_text().splitlines()[0]
        written = EvalRecord.model_validate_json(line)
        assert [g.name for g in written.grades] == ["schema", "jd_keyword_recall"]


class TestFiles:
    """REQ-EV-19: the files the runner writes."""

    async def test_results_jsonl_has_one_valid_record_per_line(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        records = await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE, StageKey.REVIEW]), cases
        )
        lines = (tmp_path / "out" / "results.jsonl").read_text().splitlines()
        written = [EvalRecord.model_validate_json(line) for line in lines]
        assert sorted(r.model_dump_json() for r in written) == sorted(
            r.model_dump_json() for r in records
        )

    async def test_run_json_is_a_valid_manifest(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        matrix = _matrix([STUB, HAIKU], [StageKey.ANALYZE])
        await make_runner().run(matrix, cases)
        manifest = RunManifest.model_validate_json(
            (tmp_path / "out" / "run.json").read_text()
        )
        assert manifest.run_id == RUN_ID
        assert manifest.matrix == matrix
        assert manifest.judge == JUDGE
        assert manifest.cases == ["alpha-match", "alpha-probe"]

    async def test_run_json_records_when_the_run_finished(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await make_runner().run(_matrix([STUB], [StageKey.ANALYZE]), cases)
        manifest = RunManifest.model_validate_json(
            (tmp_path / "out" / "run.json").read_text()
        )
        assert manifest.finished_at is not None
        assert manifest.finished_at >= manifest.started_at

    async def test_run_json_carries_the_catalog_prices_used(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await make_runner().run(_matrix([STUB, HAIKU], [StageKey.ANALYZE]), cases)
        manifest = RunManifest.model_validate_json(
            (tmp_path / "out" / "run.json").read_text()
        )
        assert manifest.catalog_prices == {
            "anthropic/claude-haiku-5-5": (0.10, 0.50),
            "anthropic/claude-opus-5-5": (4.0, 20.0),
        }

    async def test_run_json_lists_the_skipped_models(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await make_runner().run(
            _matrix([STUB], [StageKey.ANALYZE]),
            cases,
            skipped_models=["openai/gpt-6.1-sol: no API key"],
        )
        manifest = RunManifest.model_validate_json(
            (tmp_path / "out" / "run.json").read_text()
        )
        assert manifest.skipped_models == ["openai/gpt-6.1-sol: no API key"]

    async def test_raw_outputs_go_under_the_output_directory(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(canned_stub)
        await make_runner().run(_matrix([STUB], [StageKey.ANALYZE]), cases[:1])
        produced = (
            tmp_path
            / "out"
            / "raw"
            / "alpha-match"
            / "analyze"
            / "stub__stub-model"
            / "r0"
            / ".mkcv"
            / "stage1_analysis.json"
        )
        assert produced.is_file()

    async def test_run_json_exists_before_the_first_model_call(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        seen: list[bool] = []

        class Probe(StubLLMAdapter):
            async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
                seen.append((tmp_path / "out" / "run.json").is_file())
                return recorded(JDAnalysis)

        install_adapter(Probe())
        await make_runner().run(_matrix([STUB], [StageKey.ANALYZE]), cases[:1])
        assert seen == [True]

    async def test_each_record_is_on_disk_before_the_next_stage_starts(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        lines_seen: list[int] = []

        class Probe(StubLLMAdapter):
            async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
                results = tmp_path / "out" / "results.jsonl"
                lines_seen.append(len(results.read_text().splitlines()))
                return recorded(JDAnalysis)

        install_adapter(Probe())
        matrix = _matrix([STUB], [StageKey.ANALYZE], repeats=3, concurrency=1)
        await make_runner().run(matrix, cases[:1])
        assert lines_seen == [0, 1, 2]

    async def test_no_models_still_writes_both_files(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        tmp_path: Path,
    ) -> None:
        matrix = MatrixConfig(
            run=RunSettings(stages=[StageKey.ANALYZE]),
            judge=JUDGE,
            reference=JUDGE,
            models=[],
        )
        records = await make_runner().run(matrix, cases)
        assert records == []
        assert (tmp_path / "out" / "results.jsonl").read_text() == ""
        assert (tmp_path / "out" / "run.json").is_file()


class TestConcurrency:
    async def _peak_in_flight(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
        concurrency: int,
    ) -> int:
        active = 0
        peak = 0

        class Slow(StubLLMAdapter):
            async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.02)
                active -= 1
                return recorded(JDAnalysis)

        install_adapter(Slow())
        matrix = _matrix([STUB], [StageKey.ANALYZE], repeats=6, concurrency=concurrency)
        await make_runner().run(matrix, cases[:1])
        return peak

    async def test_runs_overlap_up_to_the_concurrency_limit(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        assert await self._peak_in_flight(make_runner, cases, install_adapter, 3) == 3

    async def test_a_limit_of_one_runs_stages_one_at_a_time(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        assert await self._peak_in_flight(make_runner, cases, install_adapter, 1) == 1


class TestProgress:
    async def test_the_callback_sees_every_record(
        self,
        make_runner: Callable[..., EvalRunner],
        cases: list[EvalCase],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        install_adapter(canned_stub)
        seen: list[EvalRecord] = []
        runner = make_runner(on_record=seen.append)
        records = await runner.run(
            _matrix([STUB], [StageKey.ANALYZE], repeats=2), cases[:1]
        )
        assert sorted(r.repeat for r in seen) == [r.repeat for r in records]


class TestRunIdentity:
    def test_the_run_id_is_a_utc_stamp_and_the_short_sha(self) -> None:
        stamp = datetime(2026, 11, 4, 1, 2, 3, tzinfo=UTC)
        assert new_run_id(stamp, "abc1234") == "20261104-010203-abc1234"

    def test_the_run_id_says_nogit_without_a_sha(self) -> None:
        stamp = datetime(2026, 11, 4, 1, 2, 3, tzinfo=UTC)
        assert new_run_id(stamp, None) == "20261104-010203-nogit"

    def test_the_short_sha_comes_from_the_repository(self, tmp_path: Path) -> None:
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(
            [*git, "commit", "-q", "--allow-empty", "-m", "x"], cwd=tmp_path, check=True
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert current_git_sha(tmp_path) == head

    def test_outside_a_repository_there_is_no_sha(self, tmp_path: Path) -> None:
        assert current_git_sha(tmp_path) is None


def test_the_manifest_round_trips_through_json() -> None:
    manifest = RunManifest(
        run_id=RUN_ID,
        started_at=datetime(2026, 11, 4, tzinfo=UTC),
        mkcv_version="1.3.0",
        matrix=_matrix([STUB], [StageKey.ANALYZE]),
        judge=JUDGE,
        catalog_prices={"a/b": (1.0, 2.0)},
    )
    assert (
        RunManifest.model_validate(json.loads(manifest.model_dump_json())) == manifest
    )
