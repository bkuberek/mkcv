"""Cover letter generation service."""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast

from pydantic import BaseModel

from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.cover_letter import CoverLetterError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.cover_letter_design import CoverLetterDesign
from mkcv.core.models.cover_letter_result import CoverLetterResult
from mkcv.core.models.cover_letter_review import CoverLetterReview
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.pricing import calculate_cost
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.artifacts import ArtifactStorePort
from mkcv.core.ports.cover_letter_renderer import CoverLetterRendererPort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort
from mkcv.core.ports.stage_callback import StageCallbackPort

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096

_T = TypeVar("_T", bound=BaseModel)
_R = TypeVar("_R")

STAGE_NAMES: dict[int, str] = {
    1: "generate_cover_letter",
    2: "review_cover_letter",
}

DEFAULT_COVER_LETTER_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.6),
    2: StageConfig(provider="default", model=DEFAULT_MODEL, temperature=0.2),
}


class CoverLetterService:
    """Orchestrates the 2-stage cover letter generation pipeline.

    Stages:
        1. Generate cover letter -> CoverLetter
        2. Review cover letter -> CoverLetterReview
    """

    def __init__(
        self,
        providers: dict[str, LLMPort],
        prompts: PromptLoaderPort,
        artifacts: ArtifactStorePort,
        renderer: CoverLetterRendererPort,
        stage_configs: dict[int, StageConfig] | None = None,
        design: CoverLetterDesign | None = None,
    ) -> None:
        self._providers = providers
        self._prompts = prompts
        self._artifacts = artifacts
        self._renderer = renderer
        self._stage_configs = stage_configs or DEFAULT_COVER_LETTER_STAGE_CONFIGS
        self._design = design

    async def generate(
        self,
        jd_text: str,
        *,
        resume_text: str | None = None,
        kb_text: str | None = None,
        output_dir: Path,
        company: str | None = None,
        role_title: str | None = None,
        jd_analysis: JDAnalysis | None = None,
        render: bool = True,
        stage_callback: StageCallbackPort | None = None,
    ) -> CoverLetterResult:
        """Run the cover letter generation pipeline.

        When ``jd_analysis`` is provided, skips JD re-analysis and uses
        the pre-computed analysis (e.g. from a chained resume run).
        When ``resume_text`` is None, generates from KB + JD only.
        At least one of ``resume_text`` or ``kb_text`` must be provided.

        Args:
            jd_text: Job description text.
            resume_text: Optional resume YAML content for context.
            kb_text: Optional knowledge base text.
            output_dir: Directory for output files.
            company: Company name (for the cover letter header).
            role_title: Role title (for the cover letter header).
            jd_analysis: Pre-computed JD analysis to skip re-analysis.
            render: Whether to render the cover letter to PDF.
            stage_callback: Optional callback for progress reporting.

        Returns:
            CoverLetterResult with metadata about the run.

        Raises:
            CoverLetterError: If neither resume_text nor kb_text is provided,
                or if an LLM call fails.
        """
        if resume_text is None and kb_text is None:
            raise CoverLetterError(
                "At least one of resume_text or kb_text must be provided "
                "for cover letter generation."
            )

        run_id = uuid.uuid4().hex[:12]
        start_time = time.monotonic()
        stages: list[StageMetadata] = []
        output_paths: dict[str, str] = {}

        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Cover letter run %s started", run_id)

        # Resolve company/role from JD analysis if not explicitly provided
        resolved_company = company or (jd_analysis.company if jd_analysis else "")
        resolved_role = role_title or (jd_analysis.role_title if jd_analysis else "")

        # Stage 1: Generate cover letter
        self._notify_stage_start(stage_callback, 1)
        cover_letter, meta = await self._generate_cover_letter(
            jd_text=jd_text,
            resume_text=resume_text,
            kb_text=kb_text,
            jd_analysis=jd_analysis,
            company=resolved_company,
            role_title=resolved_role,
            run_dir=artifact_dir,
        )
        stages.append(meta)

        # Stage 2: Review cover letter (graceful failure)
        review_score = 0
        self._notify_stage_start(stage_callback, 2)
        try:
            review, review_meta = await self._review_cover_letter(
                cover_letter=cover_letter,
                jd_text=jd_text,
                run_dir=artifact_dir,
            )
            stages.append(review_meta)
            review_score = review.overall_score
        except Exception:
            logger.warning(
                "Cover letter review failed — skipping review",
                exc_info=True,
            )

        # Save text outputs (always)
        text_paths = self._save_text_outputs(cover_letter, output_dir)
        output_paths.update(text_paths)

        # Render PDF (optional)
        if render:
            try:
                rendered = self._renderer.render(
                    cover_letter, output_dir, design=self._design
                )
                output_paths["cover_letter_pdf"] = str(rendered.pdf_path)
            except Exception:
                logger.warning(
                    "Cover letter PDF rendering failed",
                    exc_info=True,
                )

        total_duration = time.monotonic() - start_time
        total_cost = sum(s.cost_usd for s in stages)

        result = CoverLetterResult(
            run_id=run_id,
            timestamp=datetime.now(tz=UTC),
            company=resolved_company,
            role_title=resolved_role,
            stages=stages,
            total_cost_usd=total_cost,
            total_duration_seconds=round(total_duration, 2),
            review_score=review_score,
            output_paths=output_paths,
        )

        logger.info(
            "Cover letter run %s completed in %.1fs (score=%d)",
            run_id,
            total_duration,
            review_score,
        )

        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _generate_cover_letter(
        self,
        jd_text: str,
        *,
        resume_text: str | None,
        kb_text: str | None,
        jd_analysis: JDAnalysis | None,
        company: str,
        role_title: str,
        run_dir: Path,
    ) -> tuple[CoverLetter, StageMetadata]:
        """Stage 1: Generate cover letter content."""
        stage_number = 1
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("CL Stage %d: Generating cover letter", stage_number)
        start = time.monotonic()

        context: dict[str, object] = {
            "jd_text": jd_text,
            "company": company,
            "role_title": role_title,
        }
        if resume_text is not None:
            context["resume_text"] = resume_text
        if kb_text is not None:
            context["kb_text"] = kb_text
        if jd_analysis is not None:
            context["jd_analysis"] = jd_analysis.model_dump()

        prompt = self._prompts.render("generate_cover_letter.j2", context)

        result = await self._call_with_retry(
            lambda: self._call_structured(
                prompt,
                llm=llm,
                response_model=CoverLetter,
                model=config.model,
                temperature=config.temperature,
                stage_number=stage_number,
            ),
            stage_name=STAGE_NAMES[stage_number],
            stage_number=stage_number,
        )

        usage = llm.get_last_usage()
        self._artifacts.save(
            "cover_letter_content", result.model_dump(), run_dir=run_dir
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
            "CL Stage %d complete: %s at %s",
            stage_number,
            result.role_title,
            result.company,
        )
        return result, meta

    async def _review_cover_letter(
        self,
        cover_letter: CoverLetter,
        jd_text: str,
        *,
        run_dir: Path,
    ) -> tuple[CoverLetterReview, StageMetadata]:
        """Stage 2: Review the generated cover letter."""
        stage_number = 2
        config = self._stage_configs[stage_number]
        llm = self._resolve_llm(stage_number)
        logger.info("CL Stage %d: Reviewing cover letter", stage_number)
        start = time.monotonic()

        prompt = self._prompts.render(
            "review_cover_letter.j2",
            {
                "cover_letter": cover_letter.model_dump(),
                "jd_text": jd_text,
            },
        )

        result = await self._call_with_retry(
            lambda: self._call_structured(
                prompt,
                llm=llm,
                response_model=CoverLetterReview,
                model=config.model,
                temperature=config.temperature,
                stage_number=stage_number,
            ),
            stage_name=STAGE_NAMES[stage_number],
            stage_number=stage_number,
        )

        usage = llm.get_last_usage()
        self._artifacts.save(
            "cover_letter_review", result.model_dump(), run_dir=run_dir
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
            "CL Stage %d complete: score=%d",
            stage_number,
            result.overall_score,
        )
        return result, meta

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _save_text_outputs(
        self,
        cover_letter: CoverLetter,
        output_dir: Path,
    ) -> dict[str, str]:
        """Save cover letter as plain text and Markdown files.

        Returns:
            Dict mapping output keys to file paths.
        """
        paths: dict[str, str] = {}

        # Build body text from structured fields
        paragraphs = "\n\n".join(cover_letter.body_paragraphs)
        full_text = (
            f"{cover_letter.salutation}\n\n"
            f"{cover_letter.opening_paragraph}\n\n"
            f"{paragraphs}\n\n"
            f"{cover_letter.closing_paragraph}\n\n"
            f"{cover_letter.sign_off}\n"
            f"{cover_letter.candidate_name}"
        )

        # Plain text
        txt_path = output_dir / "cover_letter.txt"
        txt_path.write_text(full_text, encoding="utf-8")
        paths["cover_letter_txt"] = str(txt_path)

        # Markdown
        md_body = (
            f"# Cover Letter — {cover_letter.company}\n\n"
            f"**{cover_letter.role_title}**\n\n"
            f"---\n\n"
            f"{cover_letter.salutation}\n\n"
            f"{cover_letter.opening_paragraph}\n\n"
            f"{paragraphs}\n\n"
            f"{cover_letter.closing_paragraph}\n\n"
            f"{cover_letter.sign_off}  \n"
            f"{cover_letter.candidate_name}\n"
        )
        md_path = output_dir / "cover_letter.md"
        md_path.write_text(md_body, encoding="utf-8")
        paths["cover_letter_md"] = str(md_path)

        return paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_llm(self, stage_number: int) -> LLMPort:
        """Resolve the LLM adapter for a given stage."""
        config = self._stage_configs[stage_number]
        provider = config.provider

        if provider in self._providers:
            return self._providers[provider]

        if "default" in self._providers:
            return self._providers["default"]

        raise CoverLetterError(
            f"No LLM provider '{provider}' configured for "
            f"CL stage {stage_number} ({STAGE_NAMES[stage_number]}). "
            f"Available: {list(self._providers.keys())}"
        )

    @staticmethod
    def _notify_stage_start(
        callback: StageCallbackPort | None,
        stage_number: int,
    ) -> None:
        """Notify the callback that a stage is about to begin."""
        if callback is not None:
            callback.on_stage_start(stage_number)

    async def _call_with_retry(
        self,
        coro_fn: Callable[[], Awaitable[_R]],
        *,
        stage_name: str,
        stage_number: int,
        max_retries: int = 3,
    ) -> _R:
        """Call an async function with retries on output quality errors.

        Retries on ``ValidationError`` and ``ValueError`` (transient LLM
        output quality issues).  Non-retryable provider errors
        (``RateLimitError``, ``AuthenticationError``, ``ContextLengthError``,
        ``ProviderError``) are raised immediately.

        Args:
            coro_fn: Zero-argument async callable that produces the result.
            stage_name: Human-readable stage name for log messages.
            stage_number: Numeric pipeline stage identifier.
            max_retries: Maximum number of attempts (default 3).

        Returns:
            The value produced by *coro_fn*.

        Raises:
            CoverLetterError: After all retries are exhausted.
            RateLimitError: Immediately on rate-limit errors.
            AuthenticationError: Immediately on auth errors.
            ContextLengthError: Immediately on context-length errors.
            ProviderError: Immediately on other provider errors.
        """
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                return await coro_fn()
            except (
                RateLimitError,
                AuthenticationError,
                ContextLengthError,
                ProviderError,
            ):
                raise
            except (ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < max_retries:
                    logger.warning(
                        "Stage %d (%s) attempt %d/%d failed: %s. Retrying...",
                        stage_number,
                        stage_name,
                        attempt,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(1.0 * attempt)

        raise CoverLetterError(
            f"CL stage {stage_number} ({stage_name}) failed after "
            f"{max_retries} attempts: {last_error}"
        ) from last_error

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
        except CoverLetterError:
            raise
        except Exception as exc:
            raise CoverLetterError(
                f"CL stage {stage_number} ({STAGE_NAMES[stage_number]}) failed: {exc}"
            ) from exc

        return cast("_T", result)

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
