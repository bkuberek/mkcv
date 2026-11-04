"""Run a model matrix over eval cases and write the run's result files."""

import asyncio
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TextIO

import mkcv
from evals.batch.batch_store import BatchStore
from evals.batch.call_scope import call_scope
from evals.batch.eval_adapters import EvalAdapters
from evals.batch.usage_ledger import UsageLedger
from evals.graders.grader import Grader
from evals.graders.grading_context import GradingContext
from evals.graders.judge_panel import PanelVerdict, combine_panel
from evals.graders.judged_grader import JudgedGrader
from evals.graders.stage_graders import STAGE_GRADERS
from evals.harness.judge_factory import split_judges
from evals.harness.run_files import BATCH_DIR, MANIFEST_FILE, RESULTS_FILE, USAGE_FILE
from evals.harness.stage_run import StageRun
from evals.harness.stage_runner import StageRunner, work_dir_for
from evals.harness.tournament import (
    decide_survivors,
    finals_models,
    screening_cases,
    screening_judges,
)
from evals.models.call_usage import CallUsage
from evals.models.eval_case import REFERENCE_FILES, UPSTREAM_STAGES, EvalCase
from evals.models.eval_record import EvalRecord
from evals.models.grade import Grade
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.round import ROUNDS, Round
from evals.models.run_manifest import RunManifest
from evals.report.aggregator import aggregate
from evals.report.report_writer import read_records, write_report_files
from mkcv.adapters.factory import create_provider_registry
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.config.configuration import Configuration
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    """A judge adapter a run created once, with who it is."""

    adapter: LLMPort
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}"


@dataclass(frozen=True)
class _Job:
    """One stage run to make and grade, with the judges that grade it."""

    round: Round | None
    case: EvalCase
    stage: StageKey
    model: MatrixModel
    repeat: int
    judges: tuple[_Judge, ...]

    @property
    def key(self) -> str:
        return job_key(
            self.round, self.case.id, self.stage, self.model.label, self.repeat
        )


@dataclass(frozen=True)
class _RunTools:
    """What every job of one run shares."""

    runner: StageRunner
    gate: asyncio.Semaphore
    sink: TextIO
    ledger: UsageLedger


def job_key(
    round_: "Round | None", case_id: str, stage: StageKey, label: str, repeat: int
) -> str:
    """Identify one stage run of a run: round, case, stage, model, and repeat."""
    return f"{round_ or 'single'}/{case_id}/{stage.value}/{label}/r{repeat}"


def record_key(record: EvalRecord) -> str:
    """The ``job_key`` of the run a record holds."""
    return job_key(
        record.round,
        record.case_id,
        record.stage,
        f"{record.provider}/{record.model}",
        record.repeat,
    )


class EvalRunner:
    """Runs every (model, case, stage, repeat) of a matrix, one record each.

    ``results.jsonl`` grows by one flushed line per finished record and
    ``run.json`` exists from the start, so an interrupted run still leaves
    its results and manifest on disk.

    Each judge of the panel is created once per run and scores every judged
    output. A judge without credentials for its provider is left out and the
    manifest says why; with no judge at all the run goes on without judge
    grades. When the records are in, ``summary.json`` and ``report.md`` are
    written beside them.

    With ``[tournament]`` enabled the run has two rounds (see
    ``evals.harness.tournament``): screening on a few cases, then the
    finals for the survivors on every case; both are graded by the panel
    without the judge of the evaluated model's own provider. With
    ``resume`` the records already in ``results.jsonl`` are kept and their
    runs are not made again.
    """

    def __init__(
        self,
        config: Configuration,
        *,
        out_dir: Path,
        run_id: str,
        on_record: Callable[[EvalRecord], None] | None = None,
        graders: Mapping[StageKey, Sequence[Grader]] | None = None,
        resume: bool = False,
    ) -> None:
        self._config = config
        self._out_dir = out_dir
        self._run_id = run_id
        self._on_record = on_record
        self._graders = STAGE_GRADERS if graders is None else graders
        self._resume = resume

    async def run(
        self,
        matrix: MatrixConfig,
        cases: Sequence[EvalCase],
        *,
        skipped_models: Sequence[str] = (),
        rounds: Sequence[Round] = ROUNDS,
    ) -> list[EvalRecord]:
        """Run the matrix and return its records: kept ones, then new ones.

        Args:
            matrix: What to run; models without credentials are already out.
            cases: The cases to evaluate.
            skipped_models: ``provider/model: reason`` for models left out,
                recorded in the manifest.
            rounds: Which tournament rounds to run (both by default); the
                finals read the screening records already in the run.

        Raises:
            ValueError: If the finals are asked for without screening records.
        """
        registry = create_provider_registry(self._config)
        runnable, skipped_judges = split_judges(registry, matrix.panel)
        self._out_dir.mkdir(parents=True, exist_ok=True)
        kept = self._kept_records()
        adapters = self._adapters(registry, matrix)
        judges = tuple(_create_judge(adapters, judge) for judge in runnable)
        manifest = self._manifest(
            matrix, cases, skipped_models, registry.catalog, skipped_judges
        )
        self._write_manifest(manifest)

        runner = StageRunner(self._config, preset=matrix.run.preset, adapters=adapters)
        gate = asyncio.Semaphore(
            matrix.batch.concurrency if matrix.batch.enabled else matrix.run.concurrency
        )
        records = list(kept)
        mode: Literal["a", "w"] = "a" if self._resume else "w"
        with (self._out_dir / RESULTS_FILE).open(mode, encoding="utf-8") as sink:
            tools = _RunTools(runner, gate, sink, adapters.ledger)
            if not matrix.tournament.enabled:
                plan = _single_round(matrix, cases, judges)
                records += await self._run_jobs(tools, plan, kept)
            else:
                if "screening" in rounds:
                    plan = _screening(matrix, cases, judges)
                    records += await self._run_jobs(tools, plan, kept)
                if "finals" in rounds:
                    plan = _finals(matrix, cases, judges, records)
                    records += await self._run_jobs(tools, plan, kept)

        finished = manifest.model_copy(update={"finished_at": datetime.now(UTC)})
        self._write_manifest(finished)
        write_report_files(self._out_dir)
        return records

    def _adapters(
        self, registry: ProviderRegistry, matrix: MatrixConfig
    ) -> EvalAdapters:
        """The run's transport-backed adapters, batch queues, and usage ledger.

        A fresh run starts a new ``usage.jsonl``; a resumed one appends to it
        and finds its submitted batches in ``batches/``.
        """
        usage = self._out_dir / USAGE_FILE
        if not self._resume:
            usage.unlink(missing_ok=True)
        return EvalAdapters(
            registry,
            settings=matrix.batch,
            store=BatchStore(self._out_dir / BATCH_DIR)
            if matrix.batch.enabled
            else None,
            ledger=UsageLedger(usage),
            run_id=self._run_id,
            cache_prefix=matrix.caching.enabled,
        )

    def _kept_records(self) -> list[EvalRecord]:
        if not self._resume or not (self._out_dir / RESULTS_FILE).is_file():
            return []
        return read_records(self._out_dir)

    async def _run_jobs(
        self, tools: _RunTools, plan: list[_Job], kept: Sequence[EvalRecord]
    ) -> list[EvalRecord]:
        done = {record_key(record) for record in kept}
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(self._run_job(tools, job))
                for job in plan
                if job.key not in done
            ]
        return [task.result() for task in tasks]

    async def _run_job(self, tools: _RunTools, job: _Job) -> EvalRecord:
        async with tools.gate:
            work_dir = work_dir_for(
                self._out_dir / (job.round or ""),
                job.case.id,
                job.stage,
                job.model,
                job.repeat,
            )
            with call_scope(job.key):
                result = await tools.runner.run(
                    job.case, job.stage, job.model, job.repeat, work_dir
                )
            grades = await self._grade(job, result)
            record = self._record(job, result, grades, tools.ledger.for_scope(job.key))
            tools.sink.write(record.model_dump_json() + "\n")
            tools.sink.flush()
        if self._on_record is not None:
            self._on_record(record)
        return record

    async def _grade(self, job: _Job, result: StageRun) -> list[Grade]:
        """Run the stage's graders on an ``ok`` output; other results have none.

        A judged grader is asked once per judge, concurrently, and the
        judges' grades are combined into one. A grader that fails with an
        mkcv, OS, or value error (a judge call, say) leaves a grade without a
        score that names the error, so the run goes on. A grader that does
        not apply (no judge, no seeded defects) adds nothing.
        """
        if result.status != "ok":
            return []
        case, stage, model = job.case, job.stage, job.model
        context = GradingContext(
            case=case,
            stage=stage,
            kb_text=case.kb_text,
            jd_text=case.jd_text,
            output=result.payload,
            reference=_upstream_reference(case, stage),
            evaluated_provider=model.provider,
        )
        grades: list[Grade] = []
        for grader in self._graders.get(stage, ()):
            if isinstance(grader, JudgedGrader):
                grade = await _panel_grade(grader, context, job.judges, job.key)
            else:
                grade = await _safe_grade(grader, context)
            if grade is not None:
                grades.append(grade)
        return grades

    def _record(
        self,
        job: _Job,
        result: StageRun,
        grades: list[Grade],
        usage: Sequence[CallUsage],
    ) -> EvalRecord:
        metadata = result.metadata
        judges = _judges_of(grades)
        return EvalRecord(
            run_id=self._run_id,
            round=job.round,
            case_id=job.case.id,
            stage=job.stage,
            provider=job.model.provider,
            model=job.model.model,
            repeat=job.repeat,
            status=result.status,
            error=result.error,
            input_tokens=metadata.input_tokens if metadata else 0,
            output_tokens=metadata.output_tokens if metadata else 0,
            cost_usd=metadata.cost_usd if metadata else 0.0,
            cache_read_tokens=sum(call.cache_read_tokens for call in usage),
            batched=any(call.batched for call in usage),
            latency_s=metadata.duration_seconds if metadata else 0.0,
            grades=grades,
            judge=", ".join(judges) or None,
            judges=judges,
        )

    def _manifest(
        self,
        matrix: MatrixConfig,
        cases: Sequence[EvalCase],
        skipped_models: Sequence[str],
        catalog: ModelCatalog,
        skipped_judges: dict[str, str],
    ) -> RunManifest:
        return RunManifest(
            run_id=self._run_id,
            started_at=datetime.now(UTC),
            mkcv_version=mkcv.__version__,
            git_sha=current_git_sha(REPO_ROOT),
            matrix=matrix,
            judges=matrix.panel,
            catalog_prices=_catalog_prices(matrix, catalog),
            cases=[case.id for case in cases],
            skipped_models=list(skipped_models),
            skipped_judges=skipped_judges,
        )

    def _write_manifest(self, manifest: RunManifest) -> None:
        (self._out_dir / MANIFEST_FILE).write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


def _single_round(
    matrix: MatrixConfig, cases: Sequence[EvalCase], judges: tuple[_Judge, ...]
) -> list[_Job]:
    return [
        _Job(None, case, stage, model, repeat, _judges_for(matrix, stage, judges))
        for model in matrix.models
        for case in cases
        for stage in matrix.run.stages
        if case.applies_to(stage)
        for repeat in range(matrix.run.repeats)
    ]


def _screening(
    matrix: MatrixConfig, cases: Sequence[EvalCase], judges: tuple[_Judge, ...]
) -> list[_Job]:
    """Every model on the screening cases, graded by the other providers' judges."""
    by_label = {judge.label: judge for judge in judges}
    configs = [JudgeConfig(provider=j.provider, model=j.model) for j in judges]
    plan: list[_Job] = []
    for model in matrix.models:
        own = tuple(by_label[j.label] for j in screening_judges(model, configs))
        for case in screening_cases(cases, matrix.tournament):
            for stage in matrix.run.stages:
                if not case.applies_to(stage):
                    continue
                stage_judges = own if stage in matrix.run.judged_stages else ()
                plan.extend(
                    _Job("screening", case, stage, model, repeat, stage_judges)
                    for repeat in range(matrix.tournament.screening_repeats)
                )
    return plan


def _finals(
    matrix: MatrixConfig,
    cases: Sequence[EvalCase],
    judges: tuple[_Judge, ...],
    records: Sequence[EvalRecord],
) -> list[_Job]:
    """The survivors of each stage on every case, graded by the whole panel."""
    screened = [record for record in records if record.round == "screening"]
    if not matrix.models:
        return []
    if not screened:
        raise ValueError(
            "The finals need the screening results; run the screening round first"
        )
    summaries = aggregate(screened, matrix.recommendation)
    survivors = finals_models(decide_survivors(summaries, matrix.tournament))
    return [
        _Job("finals", case, stage, model, repeat, _judges_for(matrix, stage, judges))
        for model in matrix.models
        for case in cases
        for stage in matrix.run.stages
        if case.applies_to(stage) and model.label in survivors.get(stage, set())
        for repeat in range(matrix.run.repeats)
    ]


def _judges_for(
    matrix: MatrixConfig, stage: StageKey, judges: tuple[_Judge, ...]
) -> tuple[_Judge, ...]:
    return judges if stage in matrix.run.judged_stages else ()


def _create_judge(adapters: EvalAdapters, config: JudgeConfig) -> _Judge:
    return _Judge(
        adapter=adapters.create(config.provider),
        provider=config.provider,
        model=config.model,
    )


async def _scoped_grade(
    scope: str, grader: Grader, context: GradingContext
) -> Grade | None:
    with call_scope(scope):
        return await _safe_grade(grader, context)


async def _safe_grade(grader: Grader, context: GradingContext) -> Grade | None:
    try:
        return await grader.grade(context)
    except (MkcvError, OSError, ValueError) as error:
        return Grade(name=grader.name, details={"error": str(error)})


async def _panel_grade(
    grader: JudgedGrader,
    context: GradingContext,
    judges: Sequence[_Judge],
    job_key: str,
) -> Grade | None:
    """Ask every judge, then combine their grades into the panel's grade.

    Each judge's calls run under ``<job>/judge/<grader>/<judge>`` so that a
    resumed run finds them in its batches.
    """
    contexts = [
        context.model_copy(
            update={
                "judge": judge.adapter,
                "judge_model": judge.model,
                "judge_provider": judge.provider,
            }
        )
        for judge in judges
    ]
    grades = await asyncio.gather(
        *(
            _scoped_grade(f"{job_key}/judge/{grader.name}/{judge.label}", grader, c)
            for judge, c in zip(judges, contexts, strict=True)
        )
    )
    verdicts = [
        PanelVerdict(judge=judge.label, provider=judge.provider, grade=grade)
        for judge, grade in zip(judges, grades, strict=True)
    ]
    assert context.evaluated_provider is not None
    return combine_panel(
        grader.name, verdicts, evaluated_provider=context.evaluated_provider
    )


def _judges_of(grades: Sequence[Grade]) -> list[str]:
    """Every judge that scored one of ``grades``, in the order first seen."""
    labels = [
        label
        for grade in grades
        for label in grade.details.get("judges", [])
        if isinstance(label, str)
    ]
    return list(dict.fromkeys(labels))


def _upstream_reference(case: EvalCase, stage: StageKey) -> dict[str, Any]:
    """Load the case's JSON reference artifacts that ``stage`` reads from.

    Keys are the artifact names (``stage1_analysis``, ``cover_letter_content``,
    ...). The stage 4 resume is YAML, not an artifact, so it is not included.
    """
    reference: dict[str, Any] = {}
    for earlier in UPSTREAM_STAGES[stage]:
        for name in REFERENCE_FILES[earlier]:
            path = case.reference_dir / name
            if path.suffix == ".json" and path.is_file():
                reference[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return reference


def _catalog_prices(
    matrix: MatrixConfig, catalog: ModelCatalog
) -> dict[str, tuple[float, float]]:
    """Return the catalog price of every model that has one, plus the judges."""
    prices: dict[str, tuple[float, float]] = {}
    priced: list[MatrixModel | JudgeConfig] = [*matrix.models, *matrix.panel]
    for model in priced:
        price = catalog.price_for(model.model, provider=model.provider)
        if price is not None:
            prices[model.label] = price
    return prices
