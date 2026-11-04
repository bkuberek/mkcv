"""Produce the reference artifacts that stage-isolated runs start from."""

import logging
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from evals.harness.stage_runner import ARTIFACT_DIR, RESUME_FILE
from evals.harness.stop_after_stage import StopAfterStage
from evals.models.eval_case import REFERENCE_FILES, EvalCase
from evals.models.judge_config import JudgeConfig
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


class ReferenceBootstrapper:
    """Runs stages 1-4 with the reference model and stores what they produce.

    A person must review every produced file for fabricated facts before it
    is committed, so existing reference files are never overwritten.
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
        already have its references.

        Args:
            cases: The cases to bootstrap.
            known: Every case in the fixtures, used to find a probe's donor.
        """
        ordered = sorted(cases, key=lambda case: bool(case.review_probe_defects))
        outcomes: list[ReferenceOutcome] = []
        for case in ordered:
            if case.review_probe_defects:
                outcomes.append(self._copy_for_probe(case, known))
            else:
                outcomes.append(await self._generate(case))
        return outcomes

    async def _generate(self, case: EvalCase) -> ReferenceOutcome:
        existing = case.existing_reference_files()
        if existing:
            return ReferenceOutcome(
                case_id=case.id,
                status="skipped",
                detail=(
                    f"reference already exists in {case.reference_dir}; "
                    "delete it to regenerate"
                ),
            )
        try:
            with tempfile.TemporaryDirectory() as scratch:
                work_dir = Path(scratch)
                await self._run_stages(case, work_dir)
                self._store(case, work_dir)
        except (MkcvError, OSError, ValueError) as error:
            return ReferenceOutcome(case_id=case.id, status="error", detail=str(error))
        return ReferenceOutcome(
            case_id=case.id, status="written", detail=str(case.reference_dir)
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
        for names in REFERENCE_FILES.values():
            for name in names:
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
