"""Tests for PipelineService."""

import json
from pathlib import Path

import pytest

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.keyword_coverage import KeywordCoverage
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.selected_experience import SelectedExperience
from mkcv.core.models.skill_group import SkillGroup
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

        artifact = output_dir / "stage1_analysis.json"
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

        artifact = output_dir / "stage2_selection.json"
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

        artifact = output_dir / "stage3_content.json"
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

        artifact = output_dir / "stage4_structure.json"
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

        artifact = output_dir / "stage5_review.json"
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

        artifact = output_dir / "stage1_analysis.json"
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

        artifact = output_dir / "stage5_review.json"
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["overall_score"] == 82


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
        output_dir.mkdir(parents=True)

        # Pre-save stage 1 artifact
        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=output_dir,
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
        output_dir.mkdir(parents=True)

        artifacts = FileSystemArtifactStore()
        artifacts.save(
            "stage1_analysis",
            sample_jd_analysis.model_dump(),
            run_dir=output_dir,
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
        from mkcv.core.models.stage_config import StageConfig

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
        from mkcv.core.models.stage_config import StageConfig

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
        from mkcv.core.models.stage_config import StageConfig

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
