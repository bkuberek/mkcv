"""Tests for PipelineService."""

import json
from pathlib import Path
from typing import Any

import pytest

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.jd_frontmatter import JDFrontmatter
from mkcv.core.models.keyword_coverage import KeywordCoverage
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.profile_preset import BUILT_IN_PRESETS
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.selected_experience import SelectedExperience
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_metadata import StageMetadata
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole
from mkcv.core.services.pipeline import PipelineService, _strip_code_fences

# ------------------------------------------------------------------
# Fixtures: canned model instances for the stub adapter
# ------------------------------------------------------------------


@pytest.fixture
def sample_jd_analysis() -> JDAnalysis:
    """Canned JDAnalysis for testing."""
    return JDAnalysis(
        company="TestCorp",
        role_title="Senior Software Engineer",
        seniority_level="senior",
        team_or_org="Platform",
        location="Remote",
        compensation=None,
        core_requirements=[
            Requirement(
                skill="Python",
                importance="must_have",
                years_implied=5,
                context="Backend development",
            ),
        ],
        technical_stack=["Python", "AWS", "Docker"],
        soft_skills=["Communication", "Mentoring"],
        leadership_signals=["Team lead experience"],
        culture_keywords=["fast-paced", "collaborative"],
        ats_keywords=["Python", "AWS", "CI/CD", "microservices"],
        hidden_requirements=["Mentoring junior engineers"],
        role_summary="Senior engineer to build and maintain platform services.",
    )


@pytest.fixture
def sample_selection() -> ExperienceSelection:
    """Canned ExperienceSelection for testing."""
    return ExperienceSelection(
        selected_experiences=[
            SelectedExperience(
                company="PrevCo",
                role="Software Engineer",
                period="2020 - 2023",
                relevance_score=85,
                match_reasons=["Python expertise", "AWS experience"],
                suggested_bullets=[
                    "Built microservices handling 10K RPS",
                    "Led migration to Kubernetes",
                ],
                bullets_to_drop=["Updated documentation"],
                reframe_suggestion="Emphasize platform scale",
            ),
        ],
        skills_to_highlight=["Python", "AWS", "Docker"],
        skills_to_omit=["jQuery"],
        gap_analysis="No explicit CI/CD pipeline ownership.",
        mission_themes=["scalable platforms", "engineering excellence"],
    )


@pytest.fixture
def sample_tailored_content() -> TailoredContent:
    """Canned TailoredContent for testing."""
    return TailoredContent(
        mission=MissionStatement(
            text="Senior engineer building scalable platform services.",
            rationale="Matches the platform focus of the role.",
        ),
        skills=[
            SkillGroup(label="Languages", skills=["Python", "Go"]),
            SkillGroup(label="Infrastructure", skills=["AWS", "Docker", "K8s"]),
        ],
        roles=[
            TailoredRole(
                company="PrevCo",
                position="Software Engineer",
                location="Remote",
                start_date="2020-01",
                end_date="2023-06",
                summary=None,
                bullets=[
                    TailoredBullet(
                        original="Built microservices handling 10K RPS",
                        rewritten=(
                            "Built Python microservices processing 10K requests/sec "
                            "on AWS infrastructure"
                        ),
                        keywords_incorporated=["Python", "AWS", "microservices"],
                        confidence="high",
                    ),
                ],
                tech_stack="Python, AWS, Docker",
            ),
        ],
        earlier_experience=None,
        languages=None,
        low_confidence_flags=[],
    )


@pytest.fixture
def sample_review_report() -> ReviewReport:
    """Canned ReviewReport for testing."""
    return ReviewReport(
        overall_score=82,
        bullet_reviews=[
            BulletReview(
                bullet_text="Built Python microservices processing 10K requests/sec",
                classification="faithful",
                explanation=None,
                suggested_fix=None,
            ),
        ],
        keyword_coverage=KeywordCoverage(
            total_keywords=4,
            matched_keywords=3,
            coverage_percent=75.0,
            missing_keywords=["CI/CD"],
            suggestions=["Add CI/CD experience in a bullet"],
        ),
        ats_check=ATSCheck(
            single_column=True,
            no_tables=True,
            no_text_boxes=True,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=True,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=True,
            issues=[],
        ),
        tone_consistency="Consistent active voice throughout.",
        section_balance="Good distribution across experience and skills.",
        length_assessment="Appropriate for senior-level: 1 page.",
        top_suggestions=["Add CI/CD mention", "Quantify team size"],
        low_confidence_items=[],
    )


@pytest.fixture
def stub_llm(
    sample_jd_analysis: JDAnalysis,
    sample_selection: ExperienceSelection,
    sample_tailored_content: TailoredContent,
    sample_review_report: ReviewReport,
) -> StubLLMAdapter:
    """StubLLMAdapter pre-loaded with canned responses for all stages."""
    return StubLLMAdapter(
        default_response="cv:\n  name: Test\n  summary: Test resume",
        responses={
            JDAnalysis: sample_jd_analysis,
            ExperienceSelection: sample_selection,
            TailoredContent: sample_tailored_content,
            ReviewReport: sample_review_report,
        },
    )


@pytest.fixture
def pipeline(stub_llm: StubLLMAdapter) -> PipelineService:
    """PipelineService wired with stub adapters."""
    prompts = FileSystemPromptLoader()
    artifacts = FileSystemArtifactStore()
    return PipelineService(
        providers={"default": stub_llm},
        prompts=prompts,
        artifacts=artifacts,
    )


@pytest.fixture
def jd_file(tmp_path: Path) -> Path:
    """Temporary JD file."""
    path = tmp_path / "jd.txt"
    path.write_text(
        "Senior Software Engineer at TestCorp\n"
        "Requirements: 5+ years Python, AWS, Docker\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def kb_file(tmp_path: Path) -> Path:
    """Temporary KB file."""
    path = tmp_path / "career.md"
    path.write_text(
        "# John Doe\n"
        "## Experience\n"
        "### PrevCo — Software Engineer (2020-2023)\n"
        "- Built microservices handling 10K RPS\n"
        "- Led migration to Kubernetes\n",
        encoding="utf-8",
    )
    return path


# ------------------------------------------------------------------
# Test: Full pipeline execution
# ------------------------------------------------------------------


class TestPipelineGenerate:
    """Tests for PipelineService.generate()."""

    async def test_generate_runs_all_five_stages(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 5

    async def test_generate_returns_correct_company(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert result.company == "TestCorp"

    async def test_generate_returns_correct_role(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert result.role_title == "Senior Software Engineer"

    async def test_generate_returns_review_score(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert result.review_score == 82

    async def test_generate_has_positive_duration(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert result.total_duration_seconds >= 0

    async def test_generate_has_run_id(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert len(result.run_id) == 12

    async def test_generate_records_source_paths(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert result.jd_source == str(jd_file)
        assert result.kb_source == str(kb_file)


# ------------------------------------------------------------------
# Test: Artifact saving
# ------------------------------------------------------------------


class TestPipelineArtifacts:
    """Tests for artifact creation during pipeline execution."""

    async def test_stage1_artifact_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage1_analysis.json"
        assert artifact.is_file()

    async def test_stage2_artifact_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage2_selection.json"
        assert artifact.is_file()

    async def test_stage3_artifact_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage3_content.json"
        assert artifact.is_file()

    async def test_stage4_artifact_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage4_structure.json"
        assert artifact.is_file()

    async def test_stage5_artifact_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage5_review.json"
        assert artifact.is_file()

    async def test_resume_yaml_saved(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert "resume_yaml" in result.output_paths
        yaml_path = Path(result.output_paths["resume_yaml"])
        assert yaml_path.is_file()

    async def test_stage1_artifact_is_valid_json(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage1_analysis.json"
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["company"] == "TestCorp"

    async def test_stage5_artifact_contains_score(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        artifact = output_dir / ".mkcv" / "stage5_review.json"
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["overall_score"] == 82

    async def test_resume_yaml_not_in_mkcv_subdir(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """resume.yaml should be at output_dir root, not inside .mkcv/."""
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert (output_dir / "resume.yaml").is_file()
        assert not (output_dir / ".mkcv" / "resume.yaml").is_file()


# ------------------------------------------------------------------
# Test: Stage metadata
# ------------------------------------------------------------------


class TestPipelineStageMetadata:
    """Tests for stage metadata in pipeline results."""

    async def test_stage_names_are_correct(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        stage_names = [s.stage_name for s in result.stages]
        assert stage_names == [
            "analyze_jd",
            "select_experience",
            "tailor_content",
            "structure_yaml",
            "review",
        ]

    async def test_stage_numbers_are_sequential(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        stage_numbers = [s.stage_number for s in result.stages]
        assert stage_numbers == [1, 2, 3, 4, 5]

    async def test_each_stage_has_duration(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        for stage in result.stages:
            assert stage.duration_seconds >= 0


# ------------------------------------------------------------------
# Test: from_stage (skip earlier stages)
# ------------------------------------------------------------------


class TestPipelineFromStage:
    """Tests for resuming from a specific stage."""

    async def test_from_stage_2_loads_stage1_artifact(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
    ) -> None:
        """When from_stage=2, stage 1 artifact must already exist."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        # Pre-save stage 1 artifact into .mkcv/
        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=2
        )

        # Should have 4 stages (2-5)
        assert len(result.stages) == 4

    async def test_from_stage_2_skips_stage1(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
    ) -> None:
        """Stage 1 should not appear in stages when from_stage=2."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=2
        )

        stage_numbers = [s.stage_number for s in result.stages]
        assert 1 not in stage_numbers

    async def test_from_stage_2_missing_artifact_raises(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """from_stage=2 without stage 1 artifact should fail."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError):
            await pipeline.generate(
                jd_file, kb_file, output_dir=output_dir, from_stage=2
            )

    async def test_from_stage_3_runs_stages_3_to_5(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
    ) -> None:
        """from_stage=3 loads stages 1-2, runs 3-5."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage2_selection",
            sample_selection.model_dump(),
            run_dir=artifact_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=3
        )

        assert len(result.stages) == 3
        stage_numbers = [s.stage_number for s in result.stages]
        assert stage_numbers == [3, 4, 5]

    async def test_from_stage_4_runs_stages_4_to_5(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
        sample_tailored_content: TailoredContent,
    ) -> None:
        """from_stage=4 loads stages 1-3, runs 4-5."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage2_selection",
            sample_selection.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage3_content",
            sample_tailored_content.model_dump(),
            run_dir=artifact_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=4
        )

        assert len(result.stages) == 2
        stage_numbers = [s.stage_number for s in result.stages]
        assert stage_numbers == [4, 5]

    async def test_from_stage_5_runs_review_only(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
        sample_tailored_content: TailoredContent,
    ) -> None:
        """from_stage=5 loads everything, runs review only."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage2_selection",
            sample_selection.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage3_content",
            sample_tailored_content.model_dump(),
            run_dir=artifact_dir,
        )
        # Stage 4 saves resume.yaml at the output root (not inside .mkcv/)
        resume_yaml = "cv:\n  name: Test\n  summary: Test resume\n"
        (output_dir / "resume.yaml").write_text(resume_yaml, encoding="utf-8")

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=5
        )

        assert len(result.stages) == 1
        assert result.stages[0].stage_number == 5

    async def test_from_stage_3_makes_three_llm_calls(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
    ) -> None:
        """from_stage=3 should make 3 LLM calls (stages 3, 4, 5)."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )
        artifacts.save(
            "stage2_selection",
            sample_selection.model_dump(),
            run_dir=artifact_dir,
        )

        await pipeline.generate(jd_file, kb_file, output_dir=output_dir, from_stage=3)

        assert len(stub_llm.call_log) == 3

    async def test_from_stage_3_missing_stage2_raises(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
    ) -> None:
        """from_stage=3 without stage 2 artifact should fail."""
        output_dir = tmp_path / "output"
        artifact_dir = output_dir / ".mkcv"
        artifact_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=artifact_dir,
        )
        # Stage 2 artifact intentionally missing

        with pytest.raises(FileNotFoundError):
            await pipeline.generate(
                jd_file, kb_file, output_dir=output_dir, from_stage=3
            )


# ------------------------------------------------------------------
# Test: Backward compatibility (old layout with artifacts at root)
# ------------------------------------------------------------------


class TestPipelineBackwardCompatibility:
    """Tests that --from-stage works with artifacts saved in the old layout."""

    async def test_from_stage_2_loads_artifact_from_root_dir(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
    ) -> None:
        """Artifacts in output_dir root (old layout) are found by fallback."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        # Save artifact at the old location (output_dir root, not .mkcv/)
        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=output_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=2
        )

        assert len(result.stages) == 4

    async def test_from_stage_3_loads_artifacts_from_root_dir(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
    ) -> None:
        """Multiple artifacts in root dir (old layout) all load correctly."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=output_dir,
        )
        artifacts.save(
            "stage2_selection",
            sample_selection.model_dump(),
            run_dir=output_dir,
        )

        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, from_stage=3
        )

        assert len(result.stages) == 3
        stage_numbers = [s.stage_number for s in result.stages]
        assert stage_numbers == [3, 4, 5]

    async def test_new_artifacts_saved_to_mkcv_even_when_loading_from_root(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
        sample_jd_analysis: JDAnalysis,
    ) -> None:
        """New stage artifacts go to .mkcv/ even when old ones loaded from root."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        # Save stage 1 in old layout (root)
        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=output_dir,
        )

        await pipeline.generate(jd_file, kb_file, output_dir=output_dir, from_stage=2)

        # New artifacts (stages 2-5) should be in .mkcv/
        assert (output_dir / ".mkcv" / "stage2_selection.json").is_file()
        assert (output_dir / ".mkcv" / "stage3_content.json").is_file()
        assert (output_dir / ".mkcv" / "stage4_structure.json").is_file()
        assert (output_dir / ".mkcv" / "stage5_review.json").is_file()


# ------------------------------------------------------------------
# Test: LLM call log
# ------------------------------------------------------------------


class TestPipelineLLMCalls:
    """Tests verifying the pipeline makes correct LLM calls."""

    async def test_pipeline_makes_five_llm_calls(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert len(stub_llm.call_log) == 5

    async def test_stage4_uses_complete_not_structured(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        # Stage 4 (index 3) should use 'complete' for YAML output
        assert stub_llm.call_log[3]["method"] == "complete"

    async def test_stages_1_2_3_5_use_complete_structured(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        for idx in [0, 1, 2, 4]:
            assert stub_llm.call_log[idx]["method"] == "complete_structured"


# ------------------------------------------------------------------
# Test: Error handling
# ------------------------------------------------------------------


class TestPipelineErrorHandling:
    """Tests for pipeline error handling."""

    async def test_llm_error_wraps_in_pipeline_stage_error(
        self,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Unconfigured stub wraps NotImplementedError as PipelineStageError."""
        bad_llm = StubLLMAdapter()  # No canned responses
        prompts = FileSystemPromptLoader()
        artifacts = FileSystemArtifactStore()
        pipeline = PipelineService(
            providers={"default": bad_llm},
            prompts=prompts,
            artifacts=artifacts,
        )

        output_dir = tmp_path / "output"
        with pytest.raises(PipelineStageError, match="Stage 1"):
            await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

    async def test_pipeline_stage_error_has_stage_info(
        self,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        bad_llm = StubLLMAdapter()
        prompts = FileSystemPromptLoader()
        artifacts = FileSystemArtifactStore()
        pipeline = PipelineService(
            providers={"default": bad_llm},
            prompts=prompts,
            artifacts=artifacts,
        )

        output_dir = tmp_path / "output"
        with pytest.raises(PipelineStageError) as exc_info:
            await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        assert exc_info.value.stage_number == 1
        assert exc_info.value.stage == "analyze_jd"


# ------------------------------------------------------------------
# Test: _strip_code_fences helper
# ------------------------------------------------------------------


class TestStripCodeFences:
    """Tests for the _strip_code_fences utility."""

    def test_strips_yaml_fences(self) -> None:
        text = "```yaml\nfoo: bar\n```"
        assert _strip_code_fences(text) == "foo: bar"

    def test_strips_plain_fences(self) -> None:
        text = "```\nfoo: bar\n```"
        assert _strip_code_fences(text) == "foo: bar"

    def test_no_fences_unchanged(self) -> None:
        text = "foo: bar"
        assert _strip_code_fences(text) == "foo: bar"

    def test_strips_surrounding_whitespace(self) -> None:
        text = "  \n```yaml\nfoo: bar\n```\n  "
        assert _strip_code_fences(text) == "foo: bar"

    def test_preserves_internal_content(self) -> None:
        text = "```yaml\nfoo: bar\nbaz: qux\n```"
        assert _strip_code_fences(text) == "foo: bar\nbaz: qux"


# ------------------------------------------------------------------
# Test: Per-stage provider selection
# ------------------------------------------------------------------


class TestPerStageProviders:
    """Tests for per-stage LLM provider routing."""

    async def test_each_stage_can_use_different_provider(
        self,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
        sample_tailored_content: TailoredContent,
        sample_review_report: ReviewReport,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Different named providers get different call logs."""
        # Create two stub adapters to track which stages use which
        provider_a = StubLLMAdapter(
            default_response="cv:\n  name: Test",
            responses={
                JDAnalysis: sample_jd_analysis,
                ExperienceSelection: sample_selection,
                TailoredContent: sample_tailored_content,
            },
        )
        provider_b = StubLLMAdapter(
            default_response="cv:\n  name: Test",
            responses={ReviewReport: sample_review_report},
        )

        stage_configs = {
            1: StageConfig(provider="alpha", model="m1", temperature=0.2),
            2: StageConfig(provider="alpha", model="m1", temperature=0.3),
            3: StageConfig(provider="alpha", model="m1", temperature=0.5),
            4: StageConfig(provider="alpha", model="m1", temperature=0.1),
            5: StageConfig(provider="beta", model="m2", temperature=0.3),
        }

        pipeline = PipelineService(
            providers={"alpha": provider_a, "beta": provider_b},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            stage_configs=stage_configs,
        )

        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        # Provider A handled stages 1-4 (4 calls)
        assert len(provider_a.call_log) == 4
        # Provider B handled stage 5 (1 call)
        assert len(provider_b.call_log) == 1

    async def test_stage_metadata_records_provider_name(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Stage metadata should include the provider name."""
        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        for stage in result.stages:
            assert stage.provider == "default"

    async def test_stage_metadata_records_per_stage_model(
        self,
        sample_jd_analysis: JDAnalysis,
        sample_selection: ExperienceSelection,
        sample_tailored_content: TailoredContent,
        sample_review_report: ReviewReport,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Stage metadata should reflect the model from stage config."""
        stub = StubLLMAdapter(
            default_response="cv:\n  name: Test",
            responses={
                JDAnalysis: sample_jd_analysis,
                ExperienceSelection: sample_selection,
                TailoredContent: sample_tailored_content,
                ReviewReport: sample_review_report,
            },
        )

        stage_configs = {
            1: StageConfig(provider="p", model="model-a", temperature=0.2),
            2: StageConfig(provider="p", model="model-b", temperature=0.3),
            3: StageConfig(provider="p", model="model-a", temperature=0.5),
            4: StageConfig(provider="p", model="model-c", temperature=0.1),
            5: StageConfig(provider="p", model="model-b", temperature=0.3),
        }

        pipeline = PipelineService(
            providers={"p": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            stage_configs=stage_configs,
        )

        output_dir = tmp_path / "output"
        result = await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        models = [s.model for s in result.stages]
        assert models == [
            "model-a",
            "model-b",
            "model-a",
            "model-c",
            "model-b",
        ]

    async def test_missing_provider_raises_pipeline_stage_error(
        self,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Missing provider in providers dict raises PipelineStageError."""
        stage_configs = {
            1: StageConfig(provider="nonexistent", model="m", temperature=0.2),
            2: StageConfig(provider="x", model="m", temperature=0.3),
            3: StageConfig(provider="x", model="m", temperature=0.5),
            4: StageConfig(provider="x", model="m", temperature=0.1),
            5: StageConfig(provider="x", model="m", temperature=0.3),
        }

        pipeline = PipelineService(
            providers={},  # No providers at all
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            stage_configs=stage_configs,
        )

        output_dir = tmp_path / "output"
        with pytest.raises(PipelineStageError, match="nonexistent"):
            await pipeline.generate(jd_file, kb_file, output_dir=output_dir)


# ------------------------------------------------------------------
# Test: Interactive mode (stage_callback)
# ------------------------------------------------------------------


class _TrackingCallback:
    """Test callback that records calls and optionally stops."""

    def __init__(self, stop_after: int | None = None) -> None:
        self._stop_after = stop_after
        self.calls: list[int] = []
        self.starts: list[int] = []

    def on_stage_start(self, stage_number: int) -> None:
        self.starts.append(stage_number)

    def on_stage_complete(
        self,
        stage_number: int,
        stage_name: str,
        metadata: StageMetadata,
    ) -> bool:
        self.calls.append(stage_number)
        if self._stop_after is not None:
            return stage_number < self._stop_after
        return True


class TestInteractiveMode:
    """Tests for stage_callback (interactive mode) support."""

    async def test_callback_called_for_each_stage(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        cb = _TrackingCallback()
        output_dir = tmp_path / "output"
        await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, stage_callback=cb
        )
        assert cb.calls == [1, 2, 3, 4, 5]

    async def test_callback_stops_after_stage_1(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        cb = _TrackingCallback(stop_after=1)
        output_dir = tmp_path / "output"
        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, stage_callback=cb
        )
        assert len(result.stages) == 1
        assert cb.calls == [1]
        assert len(stub_llm.call_log) == 1

    async def test_callback_stops_after_stage_3(
        self,
        pipeline: PipelineService,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        cb = _TrackingCallback(stop_after=3)
        output_dir = tmp_path / "output"
        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, stage_callback=cb
        )
        assert len(result.stages) == 3
        assert cb.calls == [1, 2, 3]

    async def test_stopped_early_has_zero_review_score(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        cb = _TrackingCallback(stop_after=2)
        output_dir = tmp_path / "output"
        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, stage_callback=cb
        )
        assert result.review_score == 0

    async def test_no_callback_runs_all_stages(
        self,
        pipeline: PipelineService,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        result = await pipeline.generate(
            jd_file, kb_file, output_dir=output_dir, stage_callback=None
        )
        assert len(result.stages) == 5


# ------------------------------------------------------------------
# Test: Density context
# ------------------------------------------------------------------


class TestDensityContext:
    """Tests for density parameters being passed to prompts."""

    def test_density_context_returns_empty_when_no_preset(self) -> None:
        pipeline = PipelineService(
            providers={"default": StubLLMAdapter()},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )
        assert pipeline._density_context() == {}

    def test_density_context_returns_params_from_preset(self) -> None:
        preset = BUILT_IN_PRESETS["concise"]
        pipeline = PipelineService(
            providers={"default": StubLLMAdapter()},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        ctx = pipeline._density_context()
        assert ctx["max_roles"] == 3
        assert ctx["max_bullets_primary"] == 4
        assert ctx["max_bullets_secondary"] == 2
        assert ctx["page_budget"] == "1"
        assert ctx["density"] == "concise"
        assert ctx["include_earlier_experience"] is False

    def test_density_context_for_standard_preset(self) -> None:
        preset = BUILT_IN_PRESETS["standard"]
        pipeline = PipelineService(
            providers={"default": StubLLMAdapter()},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        ctx = pipeline._density_context()
        assert ctx["density"] == "standard"
        assert ctx["max_roles"] == 4
        assert ctx["page_budget"] == "1-2"
        assert ctx["include_earlier_experience"] is True

    def test_density_context_for_comprehensive_preset(self) -> None:
        preset = BUILT_IN_PRESETS["comprehensive"]
        pipeline = PipelineService(
            providers={"default": StubLLMAdapter()},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        ctx = pipeline._density_context()
        assert ctx["density"] == "comprehensive"
        assert ctx["max_roles"] == 6
        assert ctx["max_bullets_primary"] == 7
        assert ctx["page_budget"] == "2+"


class _PromptCapture:
    """Mock prompt loader that captures render context."""

    def __init__(self) -> None:
        self.render_calls: list[tuple[str, dict[str, Any]]] = []

    def load(self, template_name: str) -> str:
        return ""

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        self.render_calls.append((template_name, dict(context)))
        return "mock prompt"

    def list_templates(self) -> list[str]:
        return []


class TestDensityPassedToPrompts:
    """Tests that density params are forwarded to prompt rendering."""

    async def test_stage2_prompt_receives_density_params(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        prompt_capture = _PromptCapture()
        preset = BUILT_IN_PRESETS["concise"]
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        # Find the select_experience.j2 call
        select_calls = [
            (name, ctx)
            for name, ctx in prompt_capture.render_calls
            if name == "select_experience.j2"
        ]
        assert len(select_calls) == 1
        ctx = select_calls[0][1]
        assert ctx["max_roles"] == 3
        assert ctx["density"] == "concise"

    async def test_stage3_prompt_receives_bullet_params(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        prompt_capture = _PromptCapture()
        preset = BUILT_IN_PRESETS["standard"]
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        tailor_calls = [
            (name, ctx)
            for name, ctx in prompt_capture.render_calls
            if name == "tailor_bullets.j2"
        ]
        assert len(tailor_calls) == 1
        ctx = tailor_calls[0][1]
        assert ctx["max_bullets_primary"] == 5
        assert ctx["max_bullets_secondary"] == 3

    async def test_stage4_prompt_receives_page_budget(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        prompt_capture = _PromptCapture()
        preset = BUILT_IN_PRESETS["comprehensive"]
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        structure_calls = [
            (name, ctx)
            for name, ctx in prompt_capture.render_calls
            if name == "structure_yaml.j2"
        ]
        assert len(structure_calls) == 1
        ctx = structure_calls[0][1]
        assert ctx["page_budget"] == "2+"
        assert ctx["density"] == "comprehensive"

    async def test_stage5_prompt_receives_density(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        prompt_capture = _PromptCapture()
        preset = BUILT_IN_PRESETS["concise"]
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        review_calls = [
            (name, ctx)
            for name, ctx in prompt_capture.render_calls
            if name == "review.j2"
        ]
        assert len(review_calls) == 1
        ctx = review_calls[0][1]
        assert ctx["density"] == "concise"
        assert ctx["page_budget"] == "1"

    async def test_no_preset_omits_density_from_prompts(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        prompt_capture = _PromptCapture()
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        # When no preset, density keys should not be in context
        for _name, ctx in prompt_capture.render_calls:
            assert "density" not in ctx
            assert "max_roles" not in ctx

    async def test_stage1_does_not_receive_density(
        self,
        stub_llm: StubLLMAdapter,
        jd_file: Path,
        kb_file: Path,
        tmp_path: Path,
    ) -> None:
        """Stage 1 (analyze_jd) should not include density params."""
        prompt_capture = _PromptCapture()
        preset = BUILT_IN_PRESETS["concise"]
        pipeline = PipelineService(
            providers={"default": stub_llm},
            prompts=prompt_capture,
            artifacts=FileSystemArtifactStore(),
            preset=preset,
        )
        output_dir = tmp_path / "output"
        await pipeline.generate(jd_file, kb_file, output_dir=output_dir)

        analyze_calls = [
            (name, ctx)
            for name, ctx in prompt_capture.render_calls
            if name == "analyze_jd.j2"
        ]
        assert len(analyze_calls) == 1
        ctx = analyze_calls[0][1]
        assert "density" not in ctx


# ------------------------------------------------------------------
# Tests for extract_jd_metadata
# ------------------------------------------------------------------


class TestExtractJDMetadata:
    """Tests for PipelineService.extract_jd_metadata."""

    @pytest.fixture
    def sample_frontmatter(self) -> JDFrontmatter:
        return JDFrontmatter(
            company="TestCorp",
            position="Senior Engineer",
            location="Remote",
            workplace="remote",
        )

    @pytest.mark.asyncio
    async def test_extract_returns_frontmatter(
        self, sample_frontmatter: JDFrontmatter
    ) -> None:
        stub = StubLLMAdapter(responses={JDFrontmatter: sample_frontmatter})
        pipeline = PipelineService(
            providers={"default": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )

        result = await pipeline.extract_jd_metadata("Some JD text")
        assert result.company == "TestCorp"
        assert result.position == "Senior Engineer"

    @pytest.mark.asyncio
    async def test_extract_uses_stage1_provider(
        self, sample_frontmatter: JDFrontmatter
    ) -> None:
        stub = StubLLMAdapter(responses={JDFrontmatter: sample_frontmatter})
        pipeline = PipelineService(
            providers={"default": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )

        await pipeline.extract_jd_metadata("JD text")
        assert len(stub.call_log) == 1
        assert stub.call_log[0]["response_model"] == "JDFrontmatter"

    @pytest.mark.asyncio
    async def test_extract_raises_pipeline_error_on_failure(self) -> None:
        stub = StubLLMAdapter()  # no response configured -> raises
        pipeline = PipelineService(
            providers={"default": stub},
            prompts=FileSystemPromptLoader(),
            artifacts=FileSystemArtifactStore(),
        )

        with pytest.raises(PipelineStageError, match="JD metadata extraction"):
            await pipeline.extract_jd_metadata("Some JD text")
