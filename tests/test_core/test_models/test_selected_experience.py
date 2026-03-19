"""Tests for SelectedExperience model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.selected_experience import SelectedExperience


class TestSelectedExperience:
    """Tests for SelectedExperience model."""

    def test_valid_creation(self) -> None:
        exp = SelectedExperience(
            company="Acme Corp",
            role="Staff Engineer",
            period="2020-2024",
            relevance_score=90,
            match_reasons=["Strong Python background"],
            suggested_bullets=["Led platform migration"],
            bullets_to_drop=["Fixed CSS issues"],
            reframe_suggestion="Emphasize system design",
        )
        assert exp.company == "Acme Corp"

    def test_role_field(self) -> None:
        exp = SelectedExperience(
            company="DeepL",
            role="ML Engineer",
            period="2019-2023",
            relevance_score=75,
            match_reasons=["ML experience"],
            suggested_bullets=["Trained models"],
            bullets_to_drop=[],
            reframe_suggestion="Focus on production ML",
        )
        assert exp.role == "ML Engineer"

    def test_relevance_score_zero(self) -> None:
        exp = SelectedExperience(
            company="Old Co",
            role="Intern",
            period="2010-2011",
            relevance_score=0,
            match_reasons=[],
            suggested_bullets=[],
            bullets_to_drop=["Everything"],
            reframe_suggestion="Consider omitting",
        )
        assert exp.relevance_score == 0

    def test_relevance_score_100(self) -> None:
        exp = SelectedExperience(
            company="Perfect Match",
            role="Exact Role",
            period="2023-2025",
            relevance_score=100,
            match_reasons=["Perfect fit"],
            suggested_bullets=["All bullets"],
            bullets_to_drop=[],
            reframe_suggestion="No reframing needed",
        )
        assert exp.relevance_score == 100

    def test_relevance_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SelectedExperience(
                company="Acme",
                role="Engineer",
                period="2020-2024",
                relevance_score=-1,
                match_reasons=[],
                suggested_bullets=[],
                bullets_to_drop=[],
                reframe_suggestion="N/A",
            )

    def test_relevance_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SelectedExperience(
                company="Acme",
                role="Engineer",
                period="2020-2024",
                relevance_score=101,
                match_reasons=[],
                suggested_bullets=[],
                bullets_to_drop=[],
                reframe_suggestion="N/A",
            )

    def test_company_required(self) -> None:
        with pytest.raises(ValidationError):
            SelectedExperience(
                role="Engineer",  # type: ignore[call-arg]
                period="2020-2024",
                relevance_score=50,
                match_reasons=[],
                suggested_bullets=[],
                bullets_to_drop=[],
                reframe_suggestion="N/A",
            )

    def test_reframe_suggestion_required(self) -> None:
        with pytest.raises(ValidationError):
            SelectedExperience(
                company="Acme",  # type: ignore[call-arg]
                role="Engineer",
                period="2020-2024",
                relevance_score=50,
                match_reasons=[],
                suggested_bullets=[],
                bullets_to_drop=[],
            )

    def test_empty_match_reasons_allowed(self) -> None:
        exp = SelectedExperience(
            company="Acme",
            role="Engineer",
            period="2020-2024",
            relevance_score=50,
            match_reasons=[],
            suggested_bullets=["Some bullet"],
            bullets_to_drop=[],
            reframe_suggestion="N/A",
        )
        assert exp.match_reasons == []

    def test_model_dump(self) -> None:
        exp = SelectedExperience(
            company="Acme",
            role="Engineer",
            period="2020-2024",
            relevance_score=80,
            match_reasons=["Python"],
            suggested_bullets=["Built API"],
            bullets_to_drop=["Fixed typos"],
            reframe_suggestion="Focus on API design",
        )
        data = exp.model_dump()
        expected_keys = {
            "company",
            "role",
            "period",
            "relevance_score",
            "match_reasons",
            "suggested_bullets",
            "bullets_to_drop",
            "reframe_suggestion",
        }
        assert set(data.keys()) == expected_keys
