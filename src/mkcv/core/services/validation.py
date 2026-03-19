"""Resume validation service."""

import logging
from pathlib import Path
from typing import cast

from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 8192
SUPPORTED_EXTENSIONS = {".yaml", ".yml"}


class ValidationService:
    """Validates resumes for ATS compliance and quality.

    Supports two modes:
        - With JD: Analyzes the JD first, then reviews the resume against it
          for keyword coverage and targeting.
        - Without JD: Reviews the resume for general quality and ATS readiness.
    """

    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
    ) -> None:
        self._llm = llm
        self._prompts = prompts

    async def validate(
        self,
        resume_path: Path,
        *,
        jd_path: Path | None = None,
        model: str = DEFAULT_MODEL,
    ) -> ReviewReport:
        """Validate a resume for ATS compliance and quality.

        Args:
            resume_path: Path to resume file (YAML).
            jd_path: Optional JD for keyword coverage analysis.
            model: LLM model identifier.

        Returns:
            ReviewReport with scores and suggestions.

        Raises:
            ValidationError: If the file type is unsupported.
        """
        resume_text = self._read_resume(resume_path)

        jd_analysis: JDAnalysis | None = None
        if jd_path is not None:
            jd_analysis = await self._analyze_jd(jd_path, model=model)

        return await self._review_resume(
            resume_text,
            jd_analysis=jd_analysis,
            model=model,
        )

    def _read_resume(self, resume_path: Path) -> str:
        """Read the resume file content.

        Args:
            resume_path: Path to the resume file.

        Returns:
            The resume file content as a string.

        Raises:
            ValidationError: If the file type is not supported.
            FileNotFoundError: If the file does not exist.
        """
        if not resume_path.is_file():
            raise FileNotFoundError(f"Resume file not found: {resume_path}")

        if resume_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type: '{resume_path.suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}. "
                f"PDF validation is not yet supported."
            )

        return resume_path.read_text(encoding="utf-8")

    async def _analyze_jd(
        self,
        jd_path: Path,
        *,
        model: str,
    ) -> JDAnalysis:
        """Run JD analysis to get structured requirements for keyword checking.

        Args:
            jd_path: Path to the job description file.
            model: LLM model identifier.

        Returns:
            JDAnalysis with structured JD data.
        """
        jd_text = jd_path.read_text(encoding="utf-8")
        logger.info("Analyzing JD for validation: %s", jd_path.name)

        prompt = self._prompts.render("analyze_jd.j2", {"jd_text": jd_text})
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        raw = await self._llm.complete_structured(
            messages,
            model=model,
            response_model=JDAnalysis,
            temperature=0.2,
        )
        analysis = cast("JDAnalysis", raw)

        logger.info(
            "JD analysis complete: %s at %s",
            analysis.role_title,
            analysis.company,
        )
        return analysis

    async def _review_resume(
        self,
        resume_text: str,
        *,
        jd_analysis: JDAnalysis | None,
        model: str,
    ) -> ReviewReport:
        """Run the validation review on a resume.

        Args:
            resume_text: The resume content (YAML).
            jd_analysis: Optional JD analysis for targeted review.
            model: LLM model identifier.

        Returns:
            ReviewReport with quality assessment.
        """
        has_jd = jd_analysis is not None

        context: dict[str, object] = {
            "resume_yaml": resume_text,
            "has_jd": has_jd,
            "jd_analysis": jd_analysis.model_dump() if jd_analysis else None,
        }

        prompt = self._prompts.render("validate_resume.j2", context)
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        logger.info(
            "Running validation review (with_jd=%s)",
            has_jd,
        )

        raw = await self._llm.complete_structured(
            messages,
            model=model,
            response_model=ReviewReport,
            temperature=0.3,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        report = cast("ReviewReport", raw)

        logger.info("Validation complete: score=%d", report.overall_score)
        return report
