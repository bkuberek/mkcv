"""Pipeline orchestration service."""

from pathlib import Path

from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.ports.artifacts import ArtifactStorePort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort


class PipelineService:
    """Orchestrates the 5-stage resume generation pipeline.

    Stages:
        1. Analyze JD → JDAnalysis
        2. Select experience → ExperienceSelection
        3. Tailor content → TailoredContent
        4. Structure YAML → RenderCVResume
        5. Review → ReviewReport
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
        from_stage: int = 1,
    ) -> PipelineResult:
        """Run the full pipeline from JD + KB to structured resume.

        Args:
            jd_path: Path to job description file.
            kb_path: Path to knowledge base file.
            output_dir: Directory for pipeline artifacts.
            from_stage: Resume from this stage number (1-5).

        Returns:
            PipelineResult with metadata about the run.
        """
        raise NotImplementedError("Pipeline execution not yet implemented")
