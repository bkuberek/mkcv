"""Resume validation service."""

from pathlib import Path

from mkcv.core.models.review_report import ReviewReport
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort


class ValidationService:
    """Validates resumes for ATS compliance and quality."""

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
    ) -> ReviewReport:
        """Validate a resume for ATS compliance and quality.

        Args:
            resume_path: Path to resume file (PDF or YAML).
            jd_path: Optional JD for keyword coverage analysis.

        Returns:
            ReviewReport with scores and suggestions.
        """
        raise NotImplementedError("Resume validation not yet implemented")
