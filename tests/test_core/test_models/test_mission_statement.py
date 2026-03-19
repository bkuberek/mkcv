"""Tests for MissionStatement model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.mission_statement import MissionStatement


class TestMissionStatement:
    """Tests for MissionStatement model."""

    def test_valid_creation(self) -> None:
        mission = MissionStatement(
            text="Experienced platform engineer with 10+ years",
            rationale="Matches JD emphasis on platform experience",
        )
        assert mission.text == "Experienced platform engineer with 10+ years"

    def test_rationale_field(self) -> None:
        mission = MissionStatement(
            text="Senior ML engineer",
            rationale="JD prioritizes ML expertise",
        )
        assert mission.rationale == "JD prioritizes ML expertise"

    def test_text_at_max_length(self) -> None:
        text = "x" * 200
        mission = MissionStatement(text=text, rationale="Test")
        assert len(mission.text) == 200

    def test_text_exceeds_max_length_rejected(self) -> None:
        text = "x" * 201
        with pytest.raises(ValidationError):
            MissionStatement(text=text, rationale="Test")

    def test_text_required(self) -> None:
        with pytest.raises(ValidationError):
            MissionStatement(
                rationale="Some rationale",  # type: ignore[call-arg]
            )

    def test_rationale_required(self) -> None:
        with pytest.raises(ValidationError):
            MissionStatement(
                text="Some text",  # type: ignore[call-arg]
            )

    def test_empty_text_allowed(self) -> None:
        mission = MissionStatement(text="", rationale="Placeholder")
        assert mission.text == ""

    def test_model_dump(self) -> None:
        mission = MissionStatement(
            text="Platform engineer",
            rationale="Matches JD",
        )
        data = mission.model_dump()
        assert data == {
            "text": "Platform engineer",
            "rationale": "Matches JD",
        }
