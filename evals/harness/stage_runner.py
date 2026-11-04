"""Run one pipeline stage in isolation against reference inputs (design 9.5)."""

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from evals.harness.stage_run import StageRun
from evals.harness.stop_after_stage import StopAfterStage
from evals.models.eval_case import (
    COVER_LETTER_FILE,
    REFERENCE_FILES,
    UPSTREAM_STAGES,
    EvalCase,
)
from evals.models.matrix_model import MatrixModel
from mkcv.adapters.factory import (
    create_cover_letter_service_for_stage_configs,
    create_pipeline_service_for_stage_configs,
)
from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.config.configuration import Configuration
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import (
    COVER_LETTER_STAGES,
    PIPELINE_STAGE_NUMBERS,
    PIPELINE_STAGES,
    StageKey,
)

logger = logging.getLogger(__name__)

ARTIFACT_DIR = ".mkcv"
RESUME_FILE = "resume.yaml"
BOOTSTRAP_HINT = "run: uv run python -m evals bootstrap-reference"

OUTPUT_ARTIFACTS: dict[StageKey, str] = {
    StageKey.ANALYZE: "stage1_analysis",
    StageKey.SELECT: "stage2_selection",
    StageKey.TAILOR: "stage3_content",
    StageKey.REVIEW: "stage5_review",
}
"""JSON artifact each stage writes (stage 4 writes ``resume.yaml`` instead)."""


def work_dir_for(
    results_dir: Path,
    case_id: str,
    stage: StageKey,
    model: MatrixModel,
    repeat: int,
) -> Path:
    """Return the directory one stage run works in, under ``results_dir/raw``."""
    slug = f"{_slug(model.provider)}__{_slug(model.model)}"
    return results_dir / "raw" / case_id / stage.value / slug / f"r{repeat}"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", text)


class StageRunner:
    """Runs a single resume or cover letter stage for one case and one model.

    The stage's upstream inputs come from the case's reference artifacts, so
    every model is graded on the same input regardless of what earlier stages
    would have produced for it. ``cover_letter.generate`` writes from the
    knowledge base, the job description, the reference resume, and the
    company and role of the reference analysis; ``cover_letter.review``
    reviews the reference letter.
    """

    def __init__(self, config: Configuration, *, preset: str = "standard") -> None:
        self._config = config
        self._preset = preset
        self._store = FileSystemArtifactStore()

    async def run(
        self,
        case: EvalCase,
        stage: StageKey,
        model: MatrixModel,
        repeat: int,
        work_dir: Path,
    ) -> StageRun:
        """Run ``stage`` once and return what it produced.

        Failures are returned as an ``error`` run, never raised, so one bad
        call cannot abort a matrix run.
        """
        missing = _missing_reference_stages(case, stage)
        if missing:
            return StageRun(status="skipped", error=_no_reference_message(missing))

        logger.info(
            "Running %s %s on %s (repeat %d)", case.id, stage, model.label, repeat
        )
        if stage in COVER_LETTER_STAGES:
            return await self._run_cover_letter(case, stage, model, work_dir)
        number = PIPELINE_STAGE_NUMBERS[stage]
        stop = StopAfterStage(number)
        try:
            self._prepare(case, number, work_dir)
            service = create_pipeline_service_for_stage_configs(
                self._config,
                _stage_configs(model, stage),
                preset_name=self._preset,
            )
            await service.generate(
                case.jd_path,
                case.persona_path,
                output_dir=work_dir,
                from_stage=number,
                stage_callback=stop,
            )
            return self._collect(stage, work_dir, stop)
        except (MkcvError, OSError, ValueError) as error:
            return StageRun(status="error", error=str(error))

    async def _run_cover_letter(
        self, case: EvalCase, stage: StageKey, model: MatrixModel, work_dir: Path
    ) -> StageRun:
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True)
            service = create_cover_letter_service_for_stage_configs(
                self._config, _cover_letter_configs(model, stage)
            )
            if stage is StageKey.COVER_LETTER_GENERATE:
                analysis = JDAnalysis.model_validate_json(
                    _reference_text(case, REFERENCE_FILES[StageKey.ANALYZE][0])
                )
                letter, metadata = await service.generate_letter(
                    case.jd_text,
                    kb_text=case.kb_text,
                    resume_text=_reference_text(case, RESUME_FILE),
                    company=analysis.company,
                    role_title=analysis.role_title,
                    output_dir=work_dir,
                )
                return StageRun(
                    status="ok", payload=letter.model_dump(), metadata=metadata
                )
            reference = CoverLetter.model_validate_json(
                _reference_text(case, COVER_LETTER_FILE)
            )
            review, metadata = await service.review_letter(
                reference, case.jd_text, output_dir=work_dir
            )
            return StageRun(status="ok", payload=review.model_dump(), metadata=metadata)
        except (MkcvError, OSError, ValueError) as error:
            return StageRun(status="error", error=str(error))

    def _prepare(self, case: EvalCase, number: int, work_dir: Path) -> None:
        """Start from an empty work directory holding the upstream references."""
        if work_dir.exists():
            shutil.rmtree(work_dir)
        (work_dir / ARTIFACT_DIR).mkdir(parents=True)
        for stage in PIPELINE_STAGES:
            if PIPELINE_STAGE_NUMBERS[stage] >= number:
                break
            for name in REFERENCE_FILES[stage]:
                target = work_dir if name == RESUME_FILE else work_dir / ARTIFACT_DIR
                shutil.copy(case.reference_dir / name, target / name)

    def _collect(
        self, stage: StageKey, work_dir: Path, stop: StopAfterStage
    ) -> StageRun:
        metadata = stop.metadata
        if metadata is None:
            return StageRun(status="error", error="the stage did not complete")
        if stage is StageKey.STRUCTURE:
            payload: dict[str, Any] | str = (work_dir / RESUME_FILE).read_text(
                encoding="utf-8"
            )
        else:
            payload = self._store.load(
                OUTPUT_ARTIFACTS[stage], run_dir=work_dir / ARTIFACT_DIR
            )
        return StageRun(status="ok", payload=payload, metadata=metadata)


def _stage_configs(model: MatrixModel, stage: StageKey) -> dict[int, StageConfig]:
    temperature = (
        model.temperature
        if model.temperature is not None
        else STAGE_REQUIREMENTS[stage].default_temperature
    )
    config = StageConfig(
        provider=model.provider, model=model.model, temperature=temperature
    )
    return {number: config for number in PIPELINE_STAGE_NUMBERS.values()}


def _cover_letter_configs(
    model: MatrixModel, stage: StageKey
) -> dict[int, StageConfig]:
    """Both cover letter stages on ``model``, at ``stage``'s temperature."""
    temperature = (
        model.temperature
        if model.temperature is not None
        else STAGE_REQUIREMENTS[stage].default_temperature
    )
    config = StageConfig(
        provider=model.provider, model=model.model, temperature=temperature
    )
    return {number: config for number in (1, 2)}


def _reference_text(case: EvalCase, name: str) -> str:
    return (case.reference_dir / name).read_text(encoding="utf-8")


def _missing_reference_stages(case: EvalCase, stage: StageKey) -> list[StageKey]:
    available = case.reference_stages()
    return [s for s in UPSTREAM_STAGES[stage] if s not in available]


def _no_reference_message(missing: list[StageKey]) -> str:
    stages = ", ".join(stage.value for stage in missing)
    return f"no reference artifacts for {stages}; {BOOTSTRAP_HINT}"
