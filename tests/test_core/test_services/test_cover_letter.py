"""Tests for CoverLetterService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.cover_letter import CoverLetterError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.cover_letter_result import CoverLetterResult
from mkcv.core.models.cover_letter_review import CoverLetterReview
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.ports.cover_letter_renderer import CoverLetterRenderedOutput
from mkcv.core.services.cover_letter import CoverLetterService

# ------------------------------------------------------------------
# Fixtures: canned model instances for the stub adapter
# ------------------------------------------------------------------


@pytest.fixture
def sample_cover_letter() -> CoverLetter:
    """Canned CoverLetter for testing."""
    return CoverLetter(
        company="TestCorp",
        role_title="Senior Software Engineer",
        salutation="Dear Hiring Manager,",
        opening_paragraph=(
            "I am excited to apply for the Senior Software Engineer role."
        ),
        body_paragraphs=[
            "With 8 years of Python experience, I have built scalable systems.",
            "At PrevCo, I led a team that reduced latency by 40%.",
        ],
        closing_paragraph="I look forward to discussing how I can contribute.",
        sign_off="Sincerely,",
        candidate_name="Jane Doe",
        tone_notes="Professional yet enthusiastic",
    )


@pytest.fixture
def sample_review() -> CoverLetterReview:
    """Canned CoverLetterReview for testing."""
    return CoverLetterReview(
        overall_score=88,
        tone_assessment="Professional and well-matched to the company culture.",
        specificity_score=75,
        keyword_alignment=["Python", "scalable systems", "team lead"],
        length_assessment="Appropriate length — concise but thorough.",
        strengths=["Strong opening hook", "Specific metrics"],
        improvements=["Could mention cloud experience more explicitly"],
        red_flags=[],
    )


@pytest.fixture
def stub_llm(
    sample_cover_letter: CoverLetter,
    sample_review: CoverLetterReview,
) -> StubLLMAdapter:
    """StubLLMAdapter pre-loaded with canned responses for both stages."""
    return StubLLMAdapter(
        responses={
            CoverLetter: sample_cover_letter,
            CoverLetterReview: sample_review,
        },
    )


@pytest.fixture
def mock_renderer() -> MagicMock:
    """Mock cover letter renderer that returns a fake output."""
    renderer = MagicMock()
    renderer.render.return_value = CoverLetterRenderedOutput(
        pdf_path=Path("/tmp/cover_letter.pdf"),
    )
    return renderer


@pytest.fixture
def service(
    stub_llm: StubLLMAdapter,
    mock_renderer: MagicMock,
) -> CoverLetterService:
    """CoverLetterService wired with stub adapters."""
    prompts = FileSystemPromptLoader()
    artifacts = FileSystemArtifactStore()
    return CoverLetterService(
        providers={"default": stub_llm},
        prompts=prompts,
        artifacts=artifacts,
        renderer=mock_renderer,
    )


# ------------------------------------------------------------------
# Test: Full pipeline execution
# ------------------------------------------------------------------


class TestCoverLetterGenerate:
    """Tests for CoverLetterService.generate()."""

    async def test_generate_runs_both_stages(
        self,
        service: CoverLetterService,
        stub_llm: StubLLMAdapter,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "Senior SWE at TestCorp",
            kb_text="# Jane Doe\n## Skills\n- Python",
            output_dir=output_dir,
        )

        assert isinstance(result, CoverLetterResult)
        assert len(result.stages) == 2

    async def test_generate_returns_review_score(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "Senior SWE at TestCorp",
            kb_text="# Jane Doe\n## Skills\n- Python",
            output_dir=output_dir,
        )

        assert result.review_score == 88

    async def test_generate_with_resume_text(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "Senior SWE at TestCorp",
            resume_text="cv:\n  name: Jane Doe",
            output_dir=output_dir,
        )

        assert isinstance(result, CoverLetterResult)
        assert len(result.stages) == 2

    async def test_generate_without_resume(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        """KB-only mode: no resume_text provided."""
        output_dir = tmp_path / "output"
        result = await service.generate(
            "Senior SWE at TestCorp",
            kb_text="# Jane Doe\n## Skills\n- Python",
            output_dir=output_dir,
        )

        assert isinstance(result, CoverLetterResult)

    async def test_generate_has_run_id(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert len(result.run_id) == 12

    async def test_generate_has_positive_duration(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert result.total_duration_seconds >= 0

    async def test_generate_records_company(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
            company="TestCorp",
        )

        assert result.company == "TestCorp"

    async def test_generate_records_role_title(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
            role_title="Senior SWE",
        )

        assert result.role_title == "Senior SWE"


# ------------------------------------------------------------------
# Test: Review failure is graceful
# ------------------------------------------------------------------


class TestCoverLetterReviewGraceful:
    """Tests that review stage failure is handled gracefully."""

    async def test_review_failure_returns_zero_score(
        self,
        sample_cover_letter: CoverLetter,
        mock_renderer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When review fails, score should be 0 and no crash."""
        # Only provide stage 1 response, not stage 2
        stub = StubLLMAdapter(
            responses={CoverLetter: sample_cover_letter},
        )
        service = CoverLetterService(
            providers={"default": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            renderer=mock_renderer,
        )

        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert result.review_score == 0

    async def test_review_failure_still_has_one_stage(
        self,
        sample_cover_letter: CoverLetter,
        mock_renderer: MagicMock,
        tmp_path: Path,
    ) -> None:
        stub = StubLLMAdapter(
            responses={CoverLetter: sample_cover_letter},
        )
        service = CoverLetterService(
            providers={"default": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            renderer=mock_renderer,
        )

        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert len(result.stages) == 1


# ------------------------------------------------------------------
# Test: Text output saving
# ------------------------------------------------------------------


class TestCoverLetterTextOutputs:
    """Tests for text file output generation."""

    async def test_generate_saves_txt_file(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert "cover_letter_txt" in result.output_paths
        txt_path = Path(result.output_paths["cover_letter_txt"])
        assert txt_path.is_file()

    async def test_generate_saves_md_file(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert "cover_letter_md" in result.output_paths
        md_path = Path(result.output_paths["cover_letter_md"])
        assert md_path.is_file()

    async def test_txt_file_contains_salutation(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        txt_path = Path(result.output_paths["cover_letter_txt"])
        content = txt_path.read_text(encoding="utf-8")
        assert "Dear Hiring Manager," in content

    async def test_txt_file_contains_candidate_name(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        txt_path = Path(result.output_paths["cover_letter_txt"])
        content = txt_path.read_text(encoding="utf-8")
        assert "Jane Doe" in content

    async def test_md_file_contains_company_heading(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        md_path = Path(result.output_paths["cover_letter_md"])
        content = md_path.read_text(encoding="utf-8")
        assert "TestCorp" in content


# ------------------------------------------------------------------
# Test: Artifact saving
# ------------------------------------------------------------------


class TestCoverLetterArtifacts:
    """Tests for artifact creation during pipeline execution."""

    async def test_generate_saves_artifacts(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        artifact_dir = output_dir / ".mkcv"
        assert (artifact_dir / "cover_letter_content.json").is_file()

    async def test_generate_saves_review_artifact(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        artifact_dir = output_dir / ".mkcv"
        assert (artifact_dir / "cover_letter_review.json").is_file()


# ------------------------------------------------------------------
# Test: PDF rendering
# ------------------------------------------------------------------


class TestCoverLetterRendering:
    """Tests for PDF rendering integration."""

    async def test_generate_calls_renderer(
        self,
        service: CoverLetterService,
        mock_renderer: MagicMock,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
            render=True,
        )

        mock_renderer.render.assert_called_once()

    async def test_generate_no_render_skips_renderer(
        self,
        service: CoverLetterService,
        mock_renderer: MagicMock,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
            render=False,
        )

        mock_renderer.render.assert_not_called()

    async def test_generate_pdf_path_in_output(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
            render=True,
        )

        assert "cover_letter_pdf" in result.output_paths


# ------------------------------------------------------------------
# Test: Error handling
# ------------------------------------------------------------------


class TestCoverLetterErrorHandling:
    """Tests for error conditions."""

    async def test_generate_requires_resume_or_kb(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        with pytest.raises(CoverLetterError, match="At least one of"):
            await service.generate(
                "SWE at TestCorp",
                output_dir=output_dir,
            )

    async def test_generate_missing_provider_raises_error(
        self,
        mock_renderer: MagicMock,
        tmp_path: Path,
    ) -> None:
        stage_configs = {
            1: StageConfig(provider="nonexistent", model="m", temperature=0.6),
            2: StageConfig(provider="nonexistent", model="m", temperature=0.2),
        }
        service = CoverLetterService(
            providers={},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            renderer=mock_renderer,
            stage_configs=stage_configs,
        )

        output_dir = tmp_path / "output"
        with pytest.raises(CoverLetterError, match="nonexistent"):
            await service.generate(
                "SWE at TestCorp",
                kb_text="# Jane Doe",
                output_dir=output_dir,
            )


# ------------------------------------------------------------------
# Test: Stage metadata
# ------------------------------------------------------------------


class TestCoverLetterStageMetadata:
    """Tests for stage metadata in results."""

    async def test_stage_names_are_correct(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        stage_names = [s.stage_name for s in result.stages]
        assert stage_names == ["generate_cover_letter", "review_cover_letter"]

    async def test_stage_numbers_are_sequential(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        stage_numbers = [s.stage_number for s in result.stages]
        assert stage_numbers == [1, 2]

    async def test_each_stage_has_duration(
        self,
        service: CoverLetterService,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        for stage in result.stages:
            assert stage.duration_seconds >= 0


# ------------------------------------------------------------------
# Test: LLM call tracking
# ------------------------------------------------------------------


class TestCoverLetterLLMCalls:
    """Tests verifying the service makes correct LLM calls."""

    async def test_makes_two_llm_calls(
        self,
        service: CoverLetterService,
        stub_llm: StubLLMAdapter,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        assert len(stub_llm.call_log) == 2

    async def test_both_calls_use_complete_structured(
        self,
        service: CoverLetterService,
        stub_llm: StubLLMAdapter,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await service.generate(
            "SWE at TestCorp",
            kb_text="# Jane Doe",
            output_dir=output_dir,
        )

        for call in stub_llm.call_log:
            assert call["method"] == "complete_structured"
