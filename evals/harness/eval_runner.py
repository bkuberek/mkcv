"""Run a model matrix over eval cases and write the run's result files."""

import asyncio
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

import mkcv
from evals.graders.grader import Grader
from evals.graders.grading_context import GradingContext
from evals.graders.stage_graders import STAGE_GRADERS
from evals.harness.judge_factory import create_judge, judge_unavailable_reason
from evals.harness.stage_run import StageRun
from evals.harness.stage_runner import StageRunner, work_dir_for
from evals.models.eval_case import REFERENCE_FILES, EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.grade import Grade
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_manifest import RunManifest
from mkcv.adapters.factory import create_provider_registry
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.config.configuration import Configuration
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import PIPELINE_STAGE_NUMBERS, PIPELINE_STAGES, StageKey
from mkcv.core.ports.llm import LLMPort

if TYPE_CHECKING:
    from evals.models.judge_config import JudgeConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = "results.jsonl"
MANIFEST_FILE = "run.json"


def new_run_id(now: datetime, git_sha: str | None) -> str:
    """Return a run ID: the UTC time and the short commit, or ``nogit``."""
    return f"{now.astimezone(UTC):%Y%m%d-%H%M%S}-{git_sha or 'nogit'}"


def current_git_sha(directory: Path) -> str | None:
    """Return the short commit hash at ``directory``, or None outside a repository."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


@dataclass(frozen=True)
class _Judge:
    """The judge adapter a run created once, with who it is."""

    adapter: LLMPort
    provider: str
    model: str


@dataclass(frozen=True)
class _RunTools:
    """What every job of one run shares."""

    runner: StageRunner
    gate: asyncio.Semaphore
    sink: TextIO
    judge: _Judge | None


class EvalRunner:
    """Runs every (model, case, stage, repeat) of a matrix, one record each.

    ``results.jsonl`` grows by one flushed line per finished record and
    ``run.json`` exists from the start, so an interrupted run still leaves
    its results and manifest on disk.

    The judge is created once per run. Without credentials for its provider
    the run goes on without judge grades and the manifest says why.
    """

    def __init__(
        self,
        config: Configuration,
        *,
        out_dir: Path,
        run_id: str,
        on_record: Callable[[EvalRecord], None] | None = None,
        graders: Mapping[StageKey, Sequence[Grader]] | None = None,
    ) -> None:
        self._config = config
        self._out_dir = out_dir
        self._run_id = run_id
        self._on_record = on_record
        self._graders = STAGE_GRADERS if graders is None else graders

    async def run(
        self,
        matrix: MatrixConfig,
        cases: Sequence[EvalCase],
        *,
        skipped_models: Sequence[str] = (),
    ) -> list[EvalRecord]:
        """Run the matrix and return its records in plan order.

        Args:
            matrix: What to run; models without credentials are already out.
            cases: The cases to evaluate.
            skipped_models: ``provider/model: reason`` for models left out,
                recorded in the manifest.
        """
        registry = create_provider_registry(self._config)
        judge_skipped = judge_unavailable_reason(registry, matrix.judge)
        judge = None if judge_skipped else _create_judge(registry, matrix.judge)

        self._out_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest(
            matrix, cases, skipped_models, registry.catalog, judge_skipped
        )
        self._write_manifest(manifest)

        runner = StageRunner(self._config, preset=matrix.run.preset)
        gate = asyncio.Semaphore(matrix.run.concurrency)
        with (self._out_dir / RESULTS_FILE).open("w", encoding="utf-8") as sink:
            tools = _RunTools(runner, gate, sink, judge)
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(self._run_job(tools, case, stage, model, repeat))
                    for model in matrix.models
                    for case in cases
                    for stage in matrix.run.stages
                    if case.applies_to(stage)
                    for repeat in range(matrix.run.repeats)
                ]
        records = [task.result() for task in tasks]

        finished = manifest.model_copy(update={"finished_at": datetime.now(UTC)})
        self._write_manifest(finished)
        return records

    async def _run_job(
        self,
        tools: _RunTools,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        repeat: int,
    ) -> EvalRecord:
        async with tools.gate:
            work_dir = work_dir_for(self._out_dir, case.id, stage, model, repeat)
            result = await tools.runner.run(case, stage, model, repeat, work_dir)
            grades = await self._grade(case, stage, model, result, tools.judge)
            record = self._record(case, stage, model, repeat, result, grades)
            tools.sink.write(record.model_dump_json() + "\n")
            tools.sink.flush()
        if self._on_record is not None:
            self._on_record(record)
        return record

    async def _grade(
        self,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        result: StageRun,
        judge: _Judge | None,
    ) -> list[Grade]:
        """Run the stage's graders on an ``ok`` output; other results have none.

        A grader that fails with an mkcv, OS, or value error (a judge call, say)
        leaves a grade without a score that names the error, so the run goes
        on. A grader that does not apply (no judge, no seeded defects) adds
        nothing.
        """
        if result.status != "ok":
            return []
        context = GradingContext(
            case=case,
            stage=stage,
            kb_text=case.kb_text,
            jd_text=case.jd_text,
            output=result.payload,
            reference=_upstream_reference(case, stage),
            judge=judge.adapter if judge else None,
            judge_model=judge.model if judge else None,
            judge_provider=judge.provider if judge else None,
            evaluated_provider=model.provider,
        )
        grades: list[Grade] = []
        for grader in self._graders.get(stage, ()):
            try:
                grade = await grader.grade(context)
            except (MkcvError, OSError, ValueError) as error:
                grade = Grade(name=grader.name, details={"error": str(error)})
            if grade is not None:
                grades.append(grade)
        return grades

    def _record(
        self,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        repeat: int,
        result: StageRun,
        grades: list[Grade],
    ) -> EvalRecord:
        metadata = result.metadata
        return EvalRecord(
            run_id=self._run_id,
            case_id=case.id,
            stage=stage,
            provider=model.provider,
            model=model.model,
            repeat=repeat,
            status=result.status,
            error=result.error,
            input_tokens=metadata.input_tokens if metadata else 0,
            output_tokens=metadata.output_tokens if metadata else 0,
            cost_usd=metadata.cost_usd if metadata else 0.0,
            latency_s=metadata.duration_seconds if metadata else 0.0,
            grades=grades,
            judge=next(
                (g.details["judge"] for g in grades if "judge" in g.details), None
            ),
        )

    def _manifest(
        self,
        matrix: MatrixConfig,
        cases: Sequence[EvalCase],
        skipped_models: Sequence[str],
        catalog: ModelCatalog,
        judge_skipped: str | None,
    ) -> RunManifest:
        return RunManifest(
            run_id=self._run_id,
            started_at=datetime.now(UTC),
            mkcv_version=mkcv.__version__,
            git_sha=current_git_sha(REPO_ROOT),
            matrix=matrix,
            judge=matrix.judge,
            catalog_prices=_catalog_prices(matrix, catalog),
            cases=[case.id for case in cases],
            skipped_models=list(skipped_models),
            judge_skipped=judge_skipped,
        )

    def _write_manifest(self, manifest: RunManifest) -> None:
        (self._out_dir / MANIFEST_FILE).write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


def _create_judge(registry: ProviderRegistry, config: "JudgeConfig") -> _Judge:
    adapter, model = create_judge(registry, config)
    return _Judge(adapter=adapter, provider=config.provider, model=model)


def _upstream_reference(case: EvalCase, stage: StageKey) -> dict[str, Any]:
    """Load the case's JSON reference artifacts of the stages before ``stage``.

    Keys are the artifact names (``stage1_analysis``, ...). The stage 4 resume
    is YAML, not an artifact, so it is not included.
    """
    number = PIPELINE_STAGE_NUMBERS[stage]
    reference: dict[str, Any] = {}
    for earlier in PIPELINE_STAGES:
        if PIPELINE_STAGE_NUMBERS[earlier] >= number:
            break
        for name in REFERENCE_FILES[earlier]:
            path = case.reference_dir / name
            if path.suffix == ".json" and path.is_file():
                reference[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return reference


def _catalog_prices(
    matrix: MatrixConfig, catalog: ModelCatalog
) -> dict[str, tuple[float, float]]:
    """Return the catalog price of every model that has one, plus the judge."""
    prices: dict[str, tuple[float, float]] = {}
    priced: list[MatrixModel | JudgeConfig] = [*matrix.models, matrix.judge]
    for model in priced:
        price = catalog.price_for(model.model, provider=model.provider)
        if price is not None:
            prices[model.label] = price
    return prices
