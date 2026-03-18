"""Pipeline orchestration service."""

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast

from pydantic import BaseModel

from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.ports.artifacts import ArtifactStorePort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096
STAGE_MAX_TOKENS_YAML = 8192

_T = TypeVar("_T", bound=BaseModel)

STAGE_TEMPERATURES: dict[int, float] = {
    1: 0.2,
    2: 0.3,
    3: 0.5,
    4: 0.1,
    5: 0.3,
}

STAGE_NAMES: dict[int, str] = {
    1: "analyze_jd",
    2: "select_experience",
    3: "tailor_content",
    4: "structure_yaml",
    5: "review",
}


class PipelineService:
    """Orchestrates the 5-stage resume generation pipeline.

    Stages:
        1. Analyze JD -> JDAnalysis
        2. Select experience -> ExperienceSelection
        3. Tailor content -> TailoredContent
        4. Structure YAML -> resume.yaml
        5. Review -> ReviewReport
    """

    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        artifacts: ArtifactStorePort,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._artifacts = artifacts

    async def generate(
        self,
        jd_path: Path,
        kb_path: Path,
        *,
        output_dir: Path,
        model: str = DEFAULT_MODEL,
        from_stage: int = 1,
    ) -> PipelineResult:
        """Run the full pipeline from JD + KB to structured resume.

        Args:
            jd_path: Path to job description file.
            kb_path: Path to knowledge base file.
            output_dir: Directory for pipeline artifacts.
            model: LLM model identifier to use for all stages.
            from_stage: Resume from this stage number (1-5).

        Returns:
            PipelineResult with metadata about the run.
        """
        run_id = uuid.uuid4().hex[:12]
        start_time = time.monotonic()
        stages: list[StageMetadata] = []
        output_paths: dict[str, str] = {}

        jd_text = jd_path.read_text(encoding="utf-8")
        kb_text = kb_path.read_text(encoding="utf-8")

        logger.info("Pipeline run %s started (from_stage=%d)", run_id, from_stage)

        # Stage 1: Analyze JD
        if from_stage <= 1:
            jd_analysis, meta = await self._analyze_jd(
                jd_text, model=model, run_dir=output_dir
            )
            stages.append(meta)
        else:
            jd_analysis = self._load_stage_artifact(
                "stage1_analysis", JDAnalysis, run_dir=output_dir
            )

        # Stage 2: Select experience
        if from_stage <= 2:
            selection, meta = await self._select_experience(
                jd_analysis, kb_text, model=model, run_dir=output_dir
            )
            stages.append(meta)
        else:
            selection = self._load_stage_artifact(
                "stage2_selection", ExperienceSelection, run_dir=output_dir
            )

        # Stage 3: Tailor content
        if from_stage <= 3:
            content, meta = await self._tailor_content(
                jd_analysis, selection, kb_text, model=model, run_dir=output_dir
            )
            stages.append(meta)
        else:
            content = self._load_stage_artifact(
                "stage3_content", TailoredContent, run_dir=output_dir
            )

        # Stage 4: Structure YAML
        if from_stage <= 4:
            resume_yaml, meta = await self._structure_yaml(
                content, kb_text, model=model, run_dir=output_dir
            )
            stages.append(meta)
            yaml_path = self._artifacts.save_final_output(
                "resume.yaml", resume_yaml, output_dir=output_dir
            )
            output_paths["resume_yaml"] = str(yaml_path)
        else:
            yaml_path = output_dir / "resume.yaml"
            resume_yaml = yaml_path.read_text(encoding="utf-8")

        # Stage 5: Review
        review, meta = await self._review(
            resume_yaml, jd_analysis, kb_text, model=model, run_dir=output_dir
        )
        stages.append(meta)

        total_duration = time.monotonic() - start_time
        total_cost = sum(s.cost_usd for s in stages)

        result = PipelineResult(
            run_id=run_id,
            timestamp=datetime.now(tz=UTC),
            jd_source=str(jd_path),
            kb_source=str(kb_path),
            company=jd_analysis.company,
            role_title=jd_analysis.role_title,
            stages=stages,
            total_cost_usd=total_cost,
            total_duration_seconds=round(total_duration, 2),
            review_score=review.overall_score,
            output_paths=output_paths,
        )

        logger.info(
            "Pipeline run %s completed in %.1fs (score=%d)",
            run_id,
            total_duration,
            review.overall_score,
        )

        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _analyze_jd(
        self,
        jd_text: str,
        *,
        model: str,
        run_dir: Path,
    ) -> tuple[JDAnalysis, StageMetadata]:
        """Stage 1: Analyze the job description."""
        stage_number = 1
        logger.info("Stage %d: Analyzing job description", stage_number)
        start = time.monotonic()
        temperature = STAGE_TEMPERATURES[stage_number]

        prompt = self._prompts.render(
            "analyze_jd.j2",
            {"jd_text": jd_text},
        )

        result = await self._call_structured(
            prompt,
            response_model=JDAnalysis,
            model=model,
            temperature=temperature,
            stage_number=stage_number,
        )

        self._artifacts.save("stage1_analysis", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            model=model,
            temperature=temperature,
            duration=time.monotonic() - start,
        )

        logger.info(
            "Stage %d complete: %s at %s",
            stage_number,
            result.role_title,
            result.company,
        )
        return result, meta

    async def _select_experience(
        self,
        jd_analysis: JDAnalysis,
        kb_text: str,
        *,
        model: str,
        run_dir: Path,
    ) -> tuple[ExperienceSelection, StageMetadata]:
        """Stage 2: Select relevant experience from the knowledge base."""
        stage_number = 2
        logger.info("Stage %d: Selecting experience", stage_number)
        start = time.monotonic()
        temperature = STAGE_TEMPERATURES[stage_number]

        prompt = self._prompts.render(
            "select_experience.j2",
            {
                "jd_analysis": jd_analysis.model_dump(),
                "kb_text": kb_text,
            },
        )

        result = await self._call_structured(
            prompt,
            response_model=ExperienceSelection,
            model=model,
            temperature=temperature,
            stage_number=stage_number,
        )

        self._artifacts.save("stage2_selection", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            model=model,
            temperature=temperature,
            duration=time.monotonic() - start,
        )

        logger.info(
            "Stage %d complete: %d experiences selected",
            stage_number,
            len(result.selected_experiences),
        )
        return result, meta

    async def _tailor_content(
        self,
        jd_analysis: JDAnalysis,
        selection: ExperienceSelection,
        kb_text: str,
        *,
        model: str,
        run_dir: Path,
    ) -> tuple[TailoredContent, StageMetadata]:
        """Stage 3: Tailor content for the target role.

        Makes a single LLM call for the full tailored content rather than
        per-role calls. This simplification can be refined later.
        """
        stage_number = 3
        logger.info("Stage %d: Tailoring content", stage_number)
        start = time.monotonic()
        temperature = STAGE_TEMPERATURES[stage_number]

        prompt = self._prompts.render(
            "tailor_bullets.j2",
            {
                "jd_analysis": jd_analysis.model_dump(),
                "selection": selection.model_dump(),
                "ats_keywords": jd_analysis.ats_keywords,
                "kb_text": kb_text,
            },
        )

        result = await self._call_structured(
            prompt,
            response_model=TailoredContent,
            model=model,
            temperature=temperature,
            stage_number=stage_number,
            max_tokens=STAGE_MAX_TOKENS_YAML,
        )

        self._artifacts.save("stage3_content", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            model=model,
            temperature=temperature,
            duration=time.monotonic() - start,
        )

        logger.info(
            "Stage %d complete: %d roles, %d skill groups",
            stage_number,
            len(result.roles),
            len(result.skills),
        )
        return result, meta

    async def _structure_yaml(
        self,
        content: TailoredContent,
        kb_text: str,
        *,
        model: str,
        run_dir: Path,
    ) -> tuple[str, StageMetadata]:
        """Stage 4: Structure tailored content into RenderCV YAML.

        Uses plain text completion since the output is YAML, not JSON.
        """
        stage_number = 4
        logger.info("Stage %d: Structuring YAML", stage_number)
        start = time.monotonic()
        temperature = STAGE_TEMPERATURES[stage_number]

        prompt = self._prompts.render(
            "structure_yaml.j2",
            {
                "tailored_content": content.model_dump(),
                "kb_text": kb_text,
            },
        )

        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]

        try:
            resume_yaml = await self._llm.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=STAGE_MAX_TOKENS_YAML,
            )
        except Exception as exc:
            raise PipelineStageError(
                f"Stage {stage_number} (structure_yaml) failed: {exc}",
                stage=STAGE_NAMES[stage_number],
                stage_number=stage_number,
            ) from exc

        # Strip markdown code fences if the LLM wraps output
        resume_yaml = _strip_code_fences(resume_yaml)

        # Save metadata about the stage
        self._artifacts.save(
            "stage4_structure",
            {"yaml_length": len(resume_yaml)},
            run_dir=run_dir,
        )

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            model=model,
            temperature=temperature,
            duration=time.monotonic() - start,
        )

        logger.info(
            "Stage %d complete: %d chars of YAML",
            stage_number,
            len(resume_yaml),
        )
        return resume_yaml, meta

    async def _review(
        self,
        resume_yaml: str,
        jd_analysis: JDAnalysis,
        kb_text: str,
        *,
        model: str,
        run_dir: Path,
    ) -> tuple[ReviewReport, StageMetadata]:
        """Stage 5: Review the generated resume."""
        stage_number = 5
        logger.info("Stage %d: Reviewing resume", stage_number)
        start = time.monotonic()
        temperature = STAGE_TEMPERATURES[stage_number]

        prompt = self._prompts.render(
            "review.j2",
            {
                "resume_yaml": resume_yaml,
                "jd_analysis": jd_analysis.model_dump(),
                "kb_text": kb_text,
            },
        )

        result = await self._call_structured(
            prompt,
            response_model=ReviewReport,
            model=model,
            temperature=temperature,
            stage_number=stage_number,
            max_tokens=STAGE_MAX_TOKENS_YAML,
        )

        self._artifacts.save("stage5_review", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            model=model,
            temperature=temperature,
            duration=time.monotonic() - start,
        )

        logger.info("Stage %d complete: score=%d", stage_number, result.overall_score)
        return result, meta

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _call_structured(
        self,
        prompt: str,
        *,
        response_model: type[_T],
        model: str,
        temperature: float,
        stage_number: int,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> _T:
        """Call the LLM with structured output and wrap errors."""
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self._llm.complete_structured(
                messages,
                model=model,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except PipelineStageError:
            raise
        except Exception as exc:
            raise PipelineStageError(
                f"Stage {stage_number} ({STAGE_NAMES[stage_number]}) failed: {exc}",
                stage=STAGE_NAMES[stage_number],
                stage_number=stage_number,
            ) from exc

        return cast("_T", result)

    def _load_stage_artifact(
        self,
        artifact_name: str,
        model_class: type[_T],
        *,
        run_dir: Path,
    ) -> _T:
        """Load a previously saved stage artifact and parse into a model."""
        data = self._artifacts.load(artifact_name, run_dir=run_dir)
        return model_class.model_validate(data)

    @staticmethod
    def _build_stage_metadata(
        *,
        stage_number: int,
        model: str,
        temperature: float,
        duration: float,
    ) -> StageMetadata:
        """Build metadata for a completed stage.

        Token counts and cost are placeholders until the LLM adapters
        report actual usage.
        """
        return StageMetadata(
            stage_number=stage_number,
            stage_name=STAGE_NAMES[stage_number],
            provider="unknown",
            model=model,
            temperature=temperature,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            duration_seconds=round(duration, 3),
        )


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences wrapping YAML content."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (```yaml or ```)
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1 :]
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped
