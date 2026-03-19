"""Tests for JDAnalysis model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement


def _make_requirement(skill: str = "Python") -> Requirement:
    return Requirement(
        skill=skill,
        importance="must_have",
        context="Backend development",
    )


class TestJDAnalysis:
    """Tests for JDAnalysis model."""

    def test_valid_creation(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[_make_requirement()],
            technical_stack=["Python", "PostgreSQL"],
            soft_skills=["Leadership"],
            leadership_signals=["Mentoring"],
            culture_keywords=["collaborative"],
            ats_keywords=["distributed systems"],
            hidden_requirements=["Strong communication"],
            role_summary="A staff engineer leading platform work.",
        )
        assert analysis.company == "Acme Corp"

    def test_role_title(self) -> None:
        analysis = JDAnalysis(
            company="DeepL",
            role_title="ML Engineer",
            seniority_level="Senior",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Machine learning engineer for translation models.",
        )
        assert analysis.role_title == "ML Engineer"

    def test_team_or_org_defaults_to_none(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.team_or_org is None

    def test_team_or_org_with_value(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            team_or_org="Platform Team",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.team_or_org == "Platform Team"

    def test_location_defaults_to_none(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.location is None

    def test_compensation_defaults_to_none(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.compensation is None

    def test_compensation_with_value(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            compensation="$200k-$250k",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.compensation == "$200k-$250k"

    def test_company_required(self) -> None:
        with pytest.raises(ValidationError):
            JDAnalysis(
                role_title="Staff Engineer",  # type: ignore[call-arg]
                seniority_level="Staff",
                core_requirements=[],
                technical_stack=[],
                soft_skills=[],
                leadership_signals=[],
                culture_keywords=[],
                ats_keywords=[],
                hidden_requirements=[],
                role_summary="Summary.",
            )

    def test_role_summary_required(self) -> None:
        with pytest.raises(ValidationError):
            JDAnalysis(
                company="Acme Corp",  # type: ignore[call-arg]
                role_title="Staff Engineer",
                seniority_level="Staff",
                core_requirements=[],
                technical_stack=[],
                soft_skills=[],
                leadership_signals=[],
                culture_keywords=[],
                ats_keywords=[],
                hidden_requirements=[],
            )

    def test_empty_lists_allowed(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert analysis.core_requirements == []
        assert analysis.technical_stack == []

    def test_multiple_core_requirements(self) -> None:
        reqs = [
            _make_requirement("Python"),
            _make_requirement("Go"),
            _make_requirement("Kubernetes"),
        ]
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=reqs,
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        assert len(analysis.core_requirements) == 3

    def test_model_dump_includes_all_fields(self) -> None:
        analysis = JDAnalysis(
            company="Acme Corp",
            role_title="Staff Engineer",
            seniority_level="Staff",
            core_requirements=[],
            technical_stack=[],
            soft_skills=[],
            leadership_signals=[],
            culture_keywords=[],
            ats_keywords=[],
            hidden_requirements=[],
            role_summary="Summary.",
        )
        data = analysis.model_dump()
        expected_keys = {
            "company",
            "role_title",
            "seniority_level",
            "team_or_org",
            "location",
            "compensation",
            "core_requirements",
            "technical_stack",
            "soft_skills",
            "leadership_signals",
            "culture_keywords",
            "ats_keywords",
            "hidden_requirements",
            "role_summary",
        }
        assert set(data.keys()) == expected_keys
