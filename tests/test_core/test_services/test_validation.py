"""Tests for ValidationService."""

from pathlib import Path

import pytest

from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.keyword_coverage import KeywordCoverage
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.services.validation import ValidationService

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_review_report() -> ReviewReport:
    """Canned ReviewReport for validation tests."""
    return ReviewReport(
        overall_score=75,
        bullet_reviews=[
            BulletReview(
                bullet_text="Built microservices processing 10K requests/sec",
                classification="faithful",
                explanation=None,
                suggested_fix=None,
            ),
            BulletReview(
                bullet_text="Led cross-functional team to deliver platform",
                classification="enhanced",
                explanation="Claim is reasonable but vague on team size.",
                suggested_fix="Specify team size if known.",
            ),
        ],
        keyword_coverage=KeywordCoverage(
            total_keywords=5,
            matched_keywords=3,
            coverage_percent=60.0,
            missing_keywords=["CI/CD", "Terraform"],
            suggestions=["Add CI/CD to deployment bullet"],
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
        tone_consistency="Consistent active voice.",
        section_balance="Good distribution.",
        length_assessment="Appropriate for senior level.",
        top_suggestions=["Add CI/CD mention", "Quantify team size"],
        low_confidence_items=[],
    )


@pytest.fixture
def sample_jd_analysis() -> JDAnalysis:
    """Canned JDAnalysis for validation tests."""
    return JDAnalysis(
        company="TestCorp",
        role_title="Senior Software Engineer",
        seniority_level="senior",
        core_requirements=[
            Requirement(
                skill="Python",
                importance="must_have",
                years_implied=5,
                context="Backend development",
            ),
        ],
        technical_stack=["Python", "AWS"],
        soft_skills=["Communication"],
        leadership_signals=["Mentoring"],
        culture_keywords=["fast-paced"],
        ats_keywords=["Python", "AWS", "CI/CD"],
        hidden_requirements=["Code review ability"],
        role_summary="Senior engineer for platform services.",
    )


@pytest.fixture
def stub_llm_no_jd(sample_review_report: ReviewReport) -> StubLLMAdapter:
    """Stub LLM with only ReviewReport (no JD mode)."""
    return StubLLMAdapter(
        responses={ReviewReport: sample_review_report},
    )


@pytest.fixture
def stub_llm_with_jd(
    sample_review_report: ReviewReport,
    sample_jd_analysis: JDAnalysis,
) -> StubLLMAdapter:
    """Stub LLM with both JDAnalysis and ReviewReport (with JD mode)."""
    return StubLLMAdapter(
        responses={
            JDAnalysis: sample_jd_analysis,
            ReviewReport: sample_review_report,
        },
    )


@pytest.fixture
def service_no_jd(stub_llm_no_jd: StubLLMAdapter) -> ValidationService:
    """ValidationService for testing without JD."""
    prompts = FileSystemPromptLoader()
    return ValidationService(llm=stub_llm_no_jd, prompts=prompts)


@pytest.fixture
def service_with_jd(stub_llm_with_jd: StubLLMAdapter) -> ValidationService:
    """ValidationService for testing with JD."""
    prompts = FileSystemPromptLoader()
    return ValidationService(llm=stub_llm_with_jd, prompts=prompts)


@pytest.fixture
def resume_yaml_file(tmp_path: Path) -> Path:
    """Create a temporary resume YAML file."""
    path = tmp_path / "resume.yaml"
    path.write_text(
        "cv:\n"
        '  name: "John Doe"\n'
        '  email: "john@example.com"\n'
        '  summary: "Senior engineer with 10 years experience."\n'
        "  sections:\n"
        "    experience:\n"
        '      - company: "PrevCo"\n'
        '        position: "Software Engineer"\n'
        '        start_date: "2020-01"\n'
        '        end_date: "2023-06"\n'
        "        highlights:\n"
        '          - "Built microservices processing 10K requests/sec"\n',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def jd_file(tmp_path: Path) -> Path:
    """Create a temporary JD file."""
    path = tmp_path / "jd.txt"
    path.write_text(
        "Senior Software Engineer at TestCorp\n"
        "Requirements: 5+ years Python, AWS, Docker\n",
        encoding="utf-8",
    )
    return path


# ------------------------------------------------------------------
# Test: Validation without JD
# ------------------------------------------------------------------


class TestValidateWithoutJD:
    """Tests for resume validation without a job description."""

    async def test_validate_returns_review_report(
        self,
        service_no_jd: ValidationService,
        resume_yaml_file: Path,
    ) -> None:
        report = await service_no_jd.validate(resume_yaml_file)
        assert isinstance(report, ReviewReport)

    async def test_validate_returns_score(
        self,
        service_no_jd: ValidationService,
        resume_yaml_file: Path,
    ) -> None:
        report = await service_no_jd.validate(resume_yaml_file)
        assert report.overall_score == 75

    async def test_validate_returns_bullet_reviews(
        self,
        service_no_jd: ValidationService,
        resume_yaml_file: Path,
    ) -> None:
        report = await service_no_jd.validate(resume_yaml_file)
        assert len(report.bullet_reviews) == 2

    async def test_validate_makes_one_llm_call(
        self,
        service_no_jd: ValidationService,
        stub_llm_no_jd: StubLLMAdapter,
        resume_yaml_file: Path,
    ) -> None:
        await service_no_jd.validate(resume_yaml_file)
        assert len(stub_llm_no_jd.call_log) == 1

    async def test_validate_uses_complete_structured(
        self,
        service_no_jd: ValidationService,
        stub_llm_no_jd: StubLLMAdapter,
        resume_yaml_file: Path,
    ) -> None:
        await service_no_jd.validate(resume_yaml_file)
        assert stub_llm_no_jd.call_log[0]["method"] == "complete_structured"

    async def test_validate_requests_review_report_model(
        self,
        service_no_jd: ValidationService,
        stub_llm_no_jd: StubLLMAdapter,
        resume_yaml_file: Path,
    ) -> None:
        await service_no_jd.validate(resume_yaml_file)
        assert stub_llm_no_jd.call_log[0]["response_model"] == "ReviewReport"


# ------------------------------------------------------------------
# Test: Validation with JD
# ------------------------------------------------------------------


class TestValidateWithJD:
    """Tests for resume validation with a job description."""

    async def test_validate_with_jd_returns_report(
        self,
        service_with_jd: ValidationService,
        resume_yaml_file: Path,
        jd_file: Path,
    ) -> None:
        report = await service_with_jd.validate(resume_yaml_file, jd_path=jd_file)
        assert isinstance(report, ReviewReport)

    async def test_validate_with_jd_makes_two_llm_calls(
        self,
        service_with_jd: ValidationService,
        stub_llm_with_jd: StubLLMAdapter,
        resume_yaml_file: Path,
        jd_file: Path,
    ) -> None:
        await service_with_jd.validate(resume_yaml_file, jd_path=jd_file)
        assert len(stub_llm_with_jd.call_log) == 2

    async def test_validate_with_jd_analyzes_jd_first(
        self,
        service_with_jd: ValidationService,
        stub_llm_with_jd: StubLLMAdapter,
        resume_yaml_file: Path,
        jd_file: Path,
    ) -> None:
        await service_with_jd.validate(resume_yaml_file, jd_path=jd_file)
        assert stub_llm_with_jd.call_log[0]["response_model"] == "JDAnalysis"

    async def test_validate_with_jd_reviews_second(
        self,
        service_with_jd: ValidationService,
        stub_llm_with_jd: StubLLMAdapter,
        resume_yaml_file: Path,
        jd_file: Path,
    ) -> None:
        await service_with_jd.validate(resume_yaml_file, jd_path=jd_file)
        assert stub_llm_with_jd.call_log[1]["response_model"] == "ReviewReport"


# ------------------------------------------------------------------
# Test: File handling
# ------------------------------------------------------------------


class TestValidateFileHandling:
    """Tests for file type validation and error handling."""

    async def test_missing_file_raises_file_not_found(
        self,
        service_no_jd: ValidationService,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="not found"):
            await service_no_jd.validate(missing)

    async def test_pdf_file_raises_validation_error(
        self,
        service_no_jd: ValidationService,
        tmp_path: Path,
    ) -> None:
        pdf_file = tmp_path / "resume.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        with pytest.raises(ValidationError, match="Unsupported file type"):
            await service_no_jd.validate(pdf_file)

    async def test_unsupported_extension_raises_validation_error(
        self,
        service_no_jd: ValidationService,
        tmp_path: Path,
    ) -> None:
        txt_file = tmp_path / "resume.txt"
        txt_file.write_text("not a yaml file")
        with pytest.raises(ValidationError, match="Unsupported file type"):
            await service_no_jd.validate(txt_file)

    async def test_yml_extension_is_supported(
        self,
        service_no_jd: ValidationService,
        tmp_path: Path,
    ) -> None:
        yml_file = tmp_path / "resume.yml"
        yml_file.write_text("cv:\n  name: Test\n", encoding="utf-8")
        report = await service_no_jd.validate(yml_file)
        assert isinstance(report, ReviewReport)

    async def test_yaml_extension_is_supported(
        self,
        service_no_jd: ValidationService,
        resume_yaml_file: Path,
    ) -> None:
        report = await service_no_jd.validate(resume_yaml_file)
        assert isinstance(report, ReviewReport)
