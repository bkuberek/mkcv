"""Produce the reference artifacts that stage-isolated runs start from."""

import json
import logging
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from evals.harness.stage_runner import ARTIFACT_DIR, RESUME_FILE, StageRunner
from evals.harness.stop_after_stage import StopAfterStage
from evals.models.eval_case import (
    COVER_LETTER_FILE,
    PIPELINE_REFERENCE_STAGES,
    REFERENCE_FILES,
    EvalCase,
)
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.reference_outcome import ReferenceOutcome
from mkcv.adapters.factory import create_pipeline_service_for_stage_configs
from mkcv.config.configuration import Configuration
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import PIPELINE_STAGE_NUMBERS, PIPELINE_STAGES, StageKey

logger = logging.getLogger(__name__)

LAST_REFERENCE_STAGE = PIPELINE_STAGE_NUMBERS[StageKey.STRUCTURE]
UPSTREAM_OF_STRUCTURE = (StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR)
PIPELINE_FILES = tuple(
    name for stage in PIPELINE_REFERENCE_STAGES for name in REFERENCE_FILES[stage]
)


def needs_cover_letter(case: EvalCase) -> bool:
    """True if bootstrapping ``case`` would write its reference cover letter.

    A case that reviews cover letters needs one; a cover letter probe's is
    written by hand, and an existing letter is never replaced.
    """
    return (
        case.applies_to(StageKey.COVER_LETTER_REVIEW)
        and not case.is_cover_letter_probe
        and not case.review_probe_defects
        and not (case.reference_dir / COVER_LETTER_FILE).exists()
    )


def needs_pipeline(case: EvalCase) -> bool:
    """True if bootstrapping ``case`` would run stages 1-4 for it."""
    return (
        not case.review_probe_defects
        and not case.is_cover_letter_probe
        and not _existing(case, PIPELINE_FILES)
    )


class ReferenceBootstrapper:
    """Runs stages 1-4, then the cover letter, with the reference model.

    A person must review every produced file for fabricated facts before it
    is committed, so existing reference files are never overwritten: a case
    with every stage 1-4 file only gets the cover letter it lacks, and one
    with some but not all of them is left alone.
    """

    def __init__(
        self,
        config: Configuration,
        *,
        reference: JudgeConfig,
        preset: str = "standard",
    ) -> None:
        self._config = config
        self._reference = reference
        self._preset = preset

    async def bootstrap(
        self, cases: Sequence[EvalCase], known: Sequence[EvalCase]
    ) -> list[ReferenceOutcome]:
        """Produce references for ``cases`` and return one outcome per case.

        Review-probe cases come last: they copy stages 1-3 from the known case
        that shares their persona and job description, so that case must
        already have its references. A cover letter probe's letter is
        written by hand, so it is only checked.

        Args:
            cases: The cases to bootstrap.
            known: Every case in the fixtures, used to find a probe's donor.
        """
        ordered = sorted(cases, key=lambda case: bool(case.review_probe_defects))
        outcomes: list[ReferenceOutcome] = []
        for case in ordered:
            if case.review_probe_defects:
                outcomes.append(self._copy_for_probe(case, known))
            elif case.is_cover_letter_probe:
                outcomes.append(_check_letter_probe(case))
            else:
                outcomes.append(await self._generate(case))
        return outcomes

    async def _generate(self, case: EvalCase) -> ReferenceOutcome:
        existing = _existing(case, PIPELINE_FILES)
        if existing and len(existing) < len(PIPELINE_FILES):
            return _skipped(case)
        written: list[str] = []
        try:
            if not existing:
                with tempfile.TemporaryDirectory() as scratch:
                    work_dir = Path(scratch)
                    await self._run_stages(case, work_dir)
                    self._store(case, work_dir)
                written.append("stages 1-4")
            if needs_cover_letter(case):
                await self._write_cover_letter(case)
                written.append("cover letter")
        except (MkcvError, OSError, ValueError) as error:
            return ReferenceOutcome(case_id=case.id, status="error", detail=str(error))
        if not written:
            return _skipped(case)
        return ReferenceOutcome(
            case_id=case.id, status="written", detail=" and ".join(written)
        )

    async def _run_stages(self, case: EvalCase, work_dir: Path) -> None:
        service = create_pipeline_service_for_stage_configs(
            self._config, self._stage_configs(), preset_name=self._preset
        )
        await service.generate(
            case.jd_path,
            case.persona_path,
            output_dir=work_dir,
            from_stage=1,
            stage_callback=StopAfterStage(LAST_REFERENCE_STAGE),
        )

    async def _write_cover_letter(self, case: EvalCase) -> None:
        """Write the letter with the reference model, from the stored references."""
        model = MatrixModel(
            provider=self._reference.provider, model=self._reference.model
        )
        with tempfile.TemporaryDirectory() as scratch:
            result = await StageRunner(self._config, preset=self._preset).run(
                case, StageKey.COVER_LETTER_GENERATE, model, 0, Path(scratch)
            )
        if result.status != "ok" or not isinstance(result.payload, dict):
            raise ValueError(f"the cover letter failed: {result.error}")
        (case.reference_dir / COVER_LETTER_FILE).write_text(
            json.dumps(result.payload, indent=2) + "\n", encoding="utf-8"
        )

    def _stage_configs(self) -> dict[int, StageConfig]:
        return {
            PIPELINE_STAGE_NUMBERS[stage]: StageConfig(
                provider=self._reference.provider,
                model=self._reference.model,
                temperature=STAGE_REQUIREMENTS[stage].default_temperature,
            )
            for stage in PIPELINE_STAGES
        }

    def _store(self, case: EvalCase, work_dir: Path) -> None:
        case.reference_dir.mkdir(parents=True, exist_ok=True)
        for name in PIPELINE_FILES:
            source = work_dir if name == RESUME_FILE else work_dir / ARTIFACT_DIR
            shutil.copy(source / name, case.reference_dir / name)

    def _copy_for_probe(
        self, case: EvalCase, known: Sequence[EvalCase]
    ) -> ReferenceOutcome:
        donor = next(
            (
                other
                for other in known
                if other.persona == case.persona
                and other.jd == case.jd
                and not other.review_probe_defects
            ),
            None,
        )
        if donor is None:
            return ReferenceOutcome(
                case_id=case.id,
                status="error",
                detail="no case with the same persona and job description to copy from",
            )

        wanted = [
            name
            for stage in UPSTREAM_OF_STRUCTURE
            for name in REFERENCE_FILES[stage]
            if not (case.reference_dir / name).exists()
        ]
        if not wanted:
            return ReferenceOutcome(
                case_id=case.id,
                status="skipped",
                detail="stages 1-3 are already present; stage 4 is never written",
            )
        absent = [name for name in wanted if not (donor.reference_dir / name).is_file()]
        if absent:
            return ReferenceOutcome(
                case_id=case.id,
                status="error",
                detail=(
                    f"'{donor.id}' has no reference yet (missing {', '.join(absent)})"
                ),
            )

        case.reference_dir.mkdir(parents=True, exist_ok=True)
        for name in wanted:
            shutil.copy(donor.reference_dir / name, case.reference_dir / name)
        return ReferenceOutcome(
            case_id=case.id,
            status="written",
            detail=f"stages 1-3 copied from '{donor.id}'",
        )


def _existing(case: EvalCase, names: Sequence[str]) -> list[str]:
    return [name for name in names if (case.reference_dir / name).exists()]


def _skipped(case: EvalCase) -> ReferenceOutcome:
    return ReferenceOutcome(
        case_id=case.id,
        status="skipped",
        detail=(
            f"reference already exists in {case.reference_dir}; delete it to regenerate"
        ),
    )


def _check_letter_probe(case: EvalCase) -> ReferenceOutcome:
    if (case.reference_dir / COVER_LETTER_FILE).is_file():
        return ReferenceOutcome(
            case_id=case.id,
            status="skipped",
            detail="hand-written cover letter probe; nothing to bootstrap",
        )
    return ReferenceOutcome(
        case_id=case.id,
        status="error",
        detail=(
            f"a cover letter probe needs a hand-written {COVER_LETTER_FILE} "
            f"with its seeded defects in {case.reference_dir}"
        ),
    )
