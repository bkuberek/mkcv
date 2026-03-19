"""Tests for PipelineResult model."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from mkcv.core.models.pipeline_result import PipelineResult
from mkcv.core.models.stage_metadata import StageMetadata


def _make_stage(
    stage_number: int = 1,
    stage_name: str = "analyze_jd",
    cost_usd: float = 0.01,
    duration_seconds: float = 1.5,
) -> StageMetadata:
    return StageMetadata(
        stage_number=stage_number,
        stage_name=stage_name,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        temperature=0.3,
        input_tokens=1000,
        output_tokens=500,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )


class TestPipelineResult:
    """Tests for PipelineResult model."""

    def test_valid_creation(self) -> None:
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="Acme Corp",
            role_title="Staff Engineer",
            stages=[_make_stage()],
            total_cost_usd=0.01,
            total_duration_seconds=1.5,
            review_score=85,
            output_paths={"yaml": "resume.yaml", "pdf": "resume.pdf"},
        )
        assert result.run_id == "run-001"

    def test_company_field(self) -> None:
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="DeepL",
            role_title="ML Engineer",
            stages=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            review_score=90,
            output_paths={},
        )
        assert result.company == "DeepL"

    def test_empty_stages_allowed(self) -> None:
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="Acme Corp",
            role_title="Staff Engineer",
            stages=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            review_score=0,
            output_paths={},
        )
        assert result.stages == []

    def test_multiple_stages(self) -> None:
        stages = [
            _make_stage(1, "analyze_jd", 0.01, 1.0),
            _make_stage(2, "select_experience", 0.02, 2.0),
            _make_stage(3, "tailor_content", 0.03, 3.0),
        ]
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="Acme Corp",
            role_title="Staff Engineer",
            stages=stages,
            total_cost_usd=0.06,
            total_duration_seconds=6.0,
            review_score=92,
            output_paths={"yaml": "resume.yaml"},
        )
        assert len(result.stages) == 3

    def test_run_id_required(self) -> None:
        with pytest.raises(ValidationError):
            PipelineResult(
                timestamp=datetime(2025, 6, 15, 10, 30, 0),  # type: ignore[call-arg]
                jd_source="job.txt",
                kb_source="career.md",
                company="Acme Corp",
                role_title="Staff Engineer",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                review_score=0,
                output_paths={},
            )

    def test_timestamp_required(self) -> None:
        with pytest.raises(ValidationError):
            PipelineResult(
                run_id="run-001",  # type: ignore[call-arg]
                jd_source="job.txt",
                kb_source="career.md",
                company="Acme Corp",
                role_title="Staff Engineer",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                review_score=0,
                output_paths={},
            )

    def test_output_paths_preserved(self) -> None:
        paths = {"yaml": "out/resume.yaml", "pdf": "out/resume.pdf"}
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="Acme Corp",
            role_title="Staff Engineer",
            stages=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            review_score=85,
            output_paths=paths,
        )
        assert result.output_paths == paths

    def test_model_dump_includes_all_fields(self) -> None:
        result = PipelineResult(
            run_id="run-001",
            timestamp=datetime(2025, 6, 15, 10, 30, 0),
            jd_source="job.txt",
            kb_source="career.md",
            company="Acme Corp",
            role_title="Staff Engineer",
            stages=[],
            total_cost_usd=0.0,
            total_duration_seconds=0.0,
            review_score=85,
            output_paths={},
        )
        data = result.model_dump()
        expected_keys = {
            "run_id",
            "timestamp",
            "jd_source",
            "kb_source",
            "company",
            "role_title",
            "stages",
            "total_cost_usd",
            "total_duration_seconds",
            "review_score",
            "output_paths",
        }
        assert set(data.keys()) == expected_keys
