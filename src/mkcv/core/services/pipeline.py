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
from mkcv.core.models.pricing import calculate_cost
from mkcv.core.models.profile_preset import Preset
from mkcv.core.models.resume_design import ResumeDesign
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.artifacts import ArtifactStorePort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort
from mkcv.core.ports.stage_callback import StageCallbackPort

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096
STAGE_MAX_TOKENS_YAML = 8192

_T = TypeVar("_T", bound=BaseModel)

STAGE_NAMES: dict[int, str] = {
    1: "analyze_jd",
    2: "select_experience",
    3: "tailor_content",
    4: "structure_yaml",
    5: "review",
}

DEFAULT_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.2),
    2: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.3),
    3: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.5),
    4: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.1),
    5: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.3),
}


class PipelineService:
    """Orchestrates the 5-stage resume generation pipeline.

    Each stage can use a different LLM provider and model, configured
    via stage_configs. Providers are resolved by name from the
    providers dict.

    Stages:
        1. Analyze JD -> JDAnalysis
        2. Select experience -> ExperienceSelection
        3. Tailor content -> TailoredContent
        4. Structure YAML -> resume.yaml
        5. Review -> ReviewReport
    """

    def __init__(
        self,
        providers: dict[str, LLMPort],
        prompts: PromptLoaderPort,
        artifacts: ArtifactStorePort,
        stage_configs: dict[int, StageConfig] | None = None,
        preset: Preset | None = None,
        resume_design: ResumeDesign | None = None,
    ) -> None:
        self._providers = providers
        self._prompts = prompts
        self._artifacts = artifacts
        self._stage_configs = stage_configs or DEFAULT_STAGE_CONFIGS
        self._preset = preset
        self._resume_design = resume_design

    @property
    def _max_tokens(self) -> int:
        """Max output tokens for structured calls, from preset or default."""
        if self._preset is not None:
            return self._preset.max_tokens
        return DEFAULT_MAX_TOKENS

    @property
    def _max_tokens_yaml(self) -> int:
        """Max output tokens for YAML/large structured calls."""
        if self._preset is not None:
            return self._preset.max_tokens
        return STAGE_MAX_TOKENS_YAML

    def _density_context(self) -> dict[str, object]:
        """Build density template variables from the preset.

        Returns an empty dict when no preset is set, so templates
        can safely use ``{{ variable | default(...) }}`` fallbacks.
        """
        if self._preset is None:
            return {}
        return {
            "max_roles": self._preset.max_roles,
            "max_bullets_primary": self._preset.max_bullets_primary,
            "max_bullets_secondary": self._preset.max_bullets_secondary,
            "page_budget": self._preset.page_budget,
            "density": self._preset.density.value,
            "include_earlier_experience": self._preset.include_earlier_experience,
        }

    def _resolve_llm(self, stage_number: int) -> LLMPort:
        """Resolve the LLM adapter for a given stage.

        Args:
            stage_number: The pipeline stage number (1-5).

        Returns:
            The LLMPort for this stage.

        Raises:
            PipelineStageError: If the provider is not configured.
        """
        config = self._stage_configs[stage_number]
        provider = config.provider

        if provider in self._providers:
            return self._providers[provider]

        # Fall back to "default" if a named provider isn't found
        if "default" in self._providers:
            return self._providers["default"]

        raise PipelineStageError(
            f"No LLM provider '{provider}' configured for "
            f"stage {stage_number} ({STAGE_NAMES[stage_number]}). "
            f"Available: {list(self._providers.keys())}",
            stage=STAGE_NAMES[stage_number],
            stage_number=stage_number,
        )

    async def generate(
        self,
        jd_path: Path,
        kb_path: Path,
        *,
        output_dir: Path,
        from_stage: int = 1,
        stage_callback: StageCallbackPort | None = None,
        theme: str | None = None,
    ) -> PipelineResult:
        """Run the full pipeline from JD + KB to structured resume.

        Args:
            jd_path: Path to job description file.
            kb_path: Path to knowledge base file.
            output_dir: Directory for pipeline artifacts.
            from_stage: Resume from this stage number (1-5).
            stage_callback: Optional callback invoked after each stage.
                Return False from the callback to stop the pipeline early.

        Returns:
            PipelineResult with metadata about the run.
        """
        run_id = uuid.uuid4().hex[:12]
        start_time = time.monotonic()
        stages: list[StageMetadata] = []
        output_paths: dict[str, str] = {}

        jd_text = jd_path.read_text(encoding="utf-8")
        kb_text = kb_path.read_text(encoding="utf-8")

        # Intermediate stage artifacts go into a .mkcv/ subdirectory
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Pipeline run %s started (from_stage=%d)",
            run_id,
            from_stage,
        )

        stopped_early = False
        review_score = 0

        # Stage 1: Analyze JD
        if from_stage <= 1:
            self._notify_stage_start(stage_callback, 1)
            jd_analysis, meta = await self._analyze_jd(jd_text, run_dir=artifact_dir)
            stages.append(meta)
            if not self._should_continue(stage_callback, meta):
                stopped_early = True
        else:
            jd_analysis = self._load_stage_artifact(
                "stage1_analysis",
                JDAnalysis,
                artifact_dir=artifact_dir,
                output_dir=output_dir,
            )

        # Stage 2: Select experience
        if not stopped_early and from_stage <= 2:
            self._notify_stage_start(stage_callback, 2)
            selection, meta = await self._select_experience(
                jd_analysis, kb_text, run_dir=artifact_dir
            )
            stages.append(meta)
            if not self._should_continue(stage_callback, meta):
                stopped_early = True
        elif not stopped_early:
            selection = self._load_stage_artifact(
                "stage2_selection",
                ExperienceSelection,
                artifact_dir=artifact_dir,
                output_dir=output_dir,
            )

        # Stage 3: Tailor content
        if not stopped_early and from_stage <= 3:
            self._notify_stage_start(stage_callback, 3)
            content, meta = await self._tailor_content(
                jd_analysis, selection, kb_text, run_dir=artifact_dir
            )
            stages.append(meta)
            if not self._should_continue(stage_callback, meta):
                stopped_early = True
        elif not stopped_early:
            content = self._load_stage_artifact(
                "stage3_content",
                TailoredContent,
                artifact_dir=artifact_dir,
                output_dir=output_dir,
            )

        # Stage 4: Structure YAML
        effective_theme = theme or "sb2nov"
        if not stopped_early and from_stage <= 4:
            self._notify_stage_start(stage_callback, 4)
            resume_yaml, meta = await self._structure_yaml(
                content, kb_text, run_dir=artifact_dir, theme=effective_theme
            )
            stages.append(meta)
            yaml_path = self._artifacts.save_final_output(
                "resume.yaml", resume_yaml, output_dir=output_dir
            )
            output_paths["resume_yaml"] = str(yaml_path)
            if not self._should_continue(stage_callback, meta):
                stopped_early = True
        elif not stopped_early:
            yaml_path = output_dir / "resume.yaml"
            resume_yaml = yaml_path.read_text(encoding="utf-8")

        # Stage 5: Review (skipped if stopped early)
        if not stopped_early:
            self._notify_stage_start(stage_callback, 5)
            review, meta = await self._review(
                resume_yaml, jd_analysis, kb_text, run_dir=artifact_dir
            )
            stages.append(meta)
            # Notify callback (return value ignored — no next stage)
            self._should_continue(stage_callback, meta)

        total_duration = time.monotonic() - start_time
        total_cost = sum(s.cost_usd for s in stages)
        if not stopped_early:
            review_score = review.overall_score

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
            review_score=review_score,
            output_paths=output_paths,
        )

        if stopped_early:
            logger.info(
                "Pipeline run %s stopped early after %d stages",
                run_id,
                len(stages),
            )
        else:
            logger.info(
                "Pipeline run %s completed in %.1fs (score=%d)",
                run_id,
                total_duration,
                review_score,
            )

        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _analyze_jd(
        self,
        jd_text: str,
        *,
        run_dir: Path,
    ) -> tuple[JDAnalysis, StageMetadata]:
        """Stage 1: Analyze the job description."""
        stage_number = 1
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("Stage %d: Analyzing job description", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "analyze_jd.j2",
            {"jd_text": jd_text},
        )

        result = await self._call_structured(
            prompt,
            llm=llm,
            response_model=JDAnalysis,
            model=config.model,
            temperature=config.temperature,
            stage_number=stage_number,
        )

        usage = llm.get_last_usage()
        self._artifacts.save("stage1_analysis", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            duration=time.monotonic() - start,
            usage=usage,
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
        run_dir: Path,
    ) -> tuple[ExperienceSelection, StageMetadata]:
        """Stage 2: Select relevant experience from the knowledge base."""
        stage_number = 2
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("Stage %d: Selecting experience", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "select_experience.j2",
            {
                "jd_analysis": jd_analysis.model_dump(),
                "kb_text": kb_text,
                **self._density_context(),
            },
        )

        result = await self._call_structured(
            prompt,
            llm=llm,
            response_model=ExperienceSelection,
            model=config.model,
            temperature=config.temperature,
            stage_number=stage_number,
        )

        usage = llm.get_last_usage()
        self._artifacts.save("stage2_selection", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            duration=time.monotonic() - start,
            usage=usage,
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
        run_dir: Path,
    ) -> tuple[TailoredContent, StageMetadata]:
        """Stage 3: Tailor content for the target role."""
        stage_number = 3
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("Stage %d: Tailoring content", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "tailor_bullets.j2",
            {
                "jd_analysis": jd_analysis.model_dump(),
                "selection": selection.model_dump(),
                "ats_keywords": jd_analysis.ats_keywords,
                "kb_text": kb_text,
                **self._density_context(),
            },
        )

        result = await self._call_structured(
            prompt,
            llm=llm,
            response_model=TailoredContent,
            model=config.model,
            temperature=config.temperature,
            stage_number=stage_number,
            max_tokens=self._max_tokens_yaml,
        )

        usage = llm.get_last_usage()
        self._artifacts.save("stage3_content", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            duration=time.monotonic() - start,
            usage=usage,
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
        run_dir: Path,
        theme: str = "sb2nov",
    ) -> tuple[str, StageMetadata]:
        """Stage 4: Structure tailored content into RenderCV YAML.

        Uses plain text completion since the output is YAML, not JSON.
        """
        stage_number = 4
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("Stage %d: Structuring YAML", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "structure_yaml.j2",
            {
                "tailored_content": content.model_dump(),
                "kb_text": kb_text,
                "theme": theme,
                **self._density_context(),
            },
        )

        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]

        try:
            resume_yaml = await llm.complete(
                messages,
                model=config.model,
                temperature=config.temperature,
                max_tokens=self._max_tokens_yaml,
            )
        except Exception as exc:
            raise PipelineStageError(
                f"Stage {stage_number} (structure_yaml) failed: {exc}",
                stage=STAGE_NAMES[stage_number],
                stage_number=stage_number,
            ) from exc

        # Strip markdown code fences if the LLM wraps output
        resume_yaml = _strip_code_fences(resume_yaml)

        # Post-process to ensure correct design section
        from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

        postprocessor = YamlPostProcessor()
        try:
            if self._resume_design is not None:
                resume_yaml = postprocessor.inject_design(
                    resume_yaml, self._resume_design
                )
            else:
                resume_yaml = postprocessor.inject_theme(resume_yaml, theme)
        except ValueError:
            logger.warning(
                "YAML post-processing failed; using raw LLM output",
                exc_info=True,
            )

        usage = llm.get_last_usage()

        # Save metadata about the stage
        self._artifacts.save(
            "stage4_structure",
            {"yaml_length": len(resume_yaml)},
            run_dir=run_dir,
        )

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            duration=time.monotonic() - start,
            usage=usage,
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
        run_dir: Path,
    ) -> tuple[ReviewReport, StageMetadata]:
        """Stage 5: Review the generated resume."""
        stage_number = 5
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("Stage %d: Reviewing resume", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "review.j2",
            {
                "resume_yaml": resume_yaml,
                "jd_analysis": jd_analysis.model_dump(),
                "kb_text": kb_text,
                **self._density_context(),
            },
        )

        result = await self._call_structured(
            prompt,
            llm=llm,
            response_model=ReviewReport,
            model=config.model,
            temperature=config.temperature,
            stage_number=stage_number,
            max_tokens=self._max_tokens_yaml,
        )

        usage = llm.get_last_usage()
        self._artifacts.save("stage5_review", result.model_dump(), run_dir=run_dir)

        meta = self._build_stage_metadata(
            stage_number=stage_number,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            duration=time.monotonic() - start,
            usage=usage,
        )

        logger.info(
            "Stage %d complete: score=%d",
            stage_number,
            result.overall_score,
        )
        return result, meta

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _notify_stage_start(
        callback: StageCallbackPort | None,
        stage_number: int,
    ) -> None:
        """Notify the callback that a stage is about to begin.

        Args:
            callback: Optional stage callback.
            stage_number: The stage number (1-5).
        """
        if callback is not None:
            callback.on_stage_start(stage_number)

    @staticmethod
    def _should_continue(
        callback: StageCallbackPort | None,
        meta: StageMetadata,
    ) -> bool:
        """Check if the pipeline should continue after a stage.

        Args:
            callback: Optional stage callback (interactive mode).
            meta: Metadata for the just-completed stage.

        Returns:
            True to continue, False to stop.
        """
        if callback is None:
            return True
        return callback.on_stage_complete(meta.stage_number, meta.stage_name, meta)

    async def _call_structured(
        self,
        prompt: str,
        *,
        llm: LLMPort,
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
            result = await llm.complete_structured(
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
        artifact_dir: Path,
        output_dir: Path,
    ) -> _T:
        """Load a previously saved stage artifact and parse into model.

        Tries the .mkcv/ artifact directory first, then falls back to
        the output directory root for backward compatibility with runs
        created before artifacts were moved to .mkcv/.
        """
        try:
            data = self._artifacts.load(artifact_name, run_dir=artifact_dir)
        except FileNotFoundError:
            data = self._artifacts.load(artifact_name, run_dir=output_dir)
        return model_class.model_validate(data)

    @staticmethod
    def _build_stage_metadata(
        *,
        stage_number: int,
        provider: str,
        model: str,
        temperature: float,
        duration: float,
        usage: TokenUsage | None = None,
    ) -> StageMetadata:
        """Build metadata for a completed stage."""
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0

        resolved_usage = usage or TokenUsage()
        cost = calculate_cost(model, resolved_usage)

        return StageMetadata(
            stage_number=stage_number,
            stage_name=STAGE_NAMES[stage_number],
            provider=provider,
            model=model,
            temperature=temperature,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
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
