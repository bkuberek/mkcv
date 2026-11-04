"""Run a model matrix over eval cases and write the run's result files."""

import asyncio
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import mkcv
from evals.harness.stage_run import StageRun
from evals.harness.stage_runner import StageRunner, work_dir_for
from evals.models.eval_case import EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_manifest import RunManifest
from mkcv.adapters.factory import create_provider_registry
from mkcv.config.configuration import Configuration
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import StageKey

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


class EvalRunner:
    """Runs every (model, case, stage, repeat) of a matrix, one record each.

    ``results.jsonl`` grows by one flushed line per finished record and
    ``run.json`` exists from the start, so an interrupted run still leaves
    its results and manifest on disk.
    """

    def __init__(
        self,
        config: Configuration,
        *,
        out_dir: Path,
        run_id: str,
        on_record: Callable[[EvalRecord], None] | None = None,
    ) -> None:
        self._config = config
        self._out_dir = out_dir
        self._run_id = run_id
        self._on_record = on_record

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
        self._out_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest(matrix, cases, skipped_models)
        self._write_manifest(manifest)

        runner = StageRunner(self._config, preset=matrix.run.preset)
        gate = asyncio.Semaphore(matrix.run.concurrency)
        with (self._out_dir / RESULTS_FILE).open("w", encoding="utf-8") as sink:
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(
                        self._run_job(runner, gate, sink, case, stage, model, repeat)
                    )
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
        runner: StageRunner,
        gate: asyncio.Semaphore,
        sink: TextIO,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        repeat: int,
    ) -> EvalRecord:
        async with gate:
            work_dir = work_dir_for(self._out_dir, case.id, stage, model, repeat)
            result = await runner.run(case, stage, model, repeat, work_dir)
            record = self._record(case, stage, model, repeat, result)
            sink.write(record.model_dump_json() + "\n")
            sink.flush()
        if self._on_record is not None:
            self._on_record(record)
        return record

    def _record(
        self,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        repeat: int,
        result: StageRun,
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
        )

    def _manifest(
        self,
        matrix: MatrixConfig,
        cases: Sequence[EvalCase],
        skipped_models: Sequence[str],
    ) -> RunManifest:
        catalog = create_provider_registry(self._config).catalog
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
        )

    def _write_manifest(self, manifest: RunManifest) -> None:
        (self._out_dir / MANIFEST_FILE).write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


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
