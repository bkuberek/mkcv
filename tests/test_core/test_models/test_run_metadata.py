"""Tests for RunMetadata model."""

import json

from mkcv.core.models.run_metadata import RunMetadata


class TestRunMetadata:
    """Tests for RunMetadata model."""

    def test_creation_with_required_fields(self) -> None:
        meta = RunMetadata(
            preset="standard",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
        assert meta.preset == "standard"
        assert meta.provider == "anthropic"
        assert meta.model == "claude-sonnet-4-20250514"

    def test_defaults_for_optional_fields(self) -> None:
        meta = RunMetadata(
            preset="standard",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
        assert meta.duration_seconds == 0.0
        assert meta.review_score == 0
        assert meta.total_cost_usd == 0.0

    def test_timestamp_auto_populated(self) -> None:
        meta = RunMetadata(
            preset="standard",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
        assert meta.timestamp is not None

    def test_model_dump_json_serializable(self) -> None:
        meta = RunMetadata(
            preset="standard",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            duration_seconds=12.5,
            review_score=85,
            total_cost_usd=0.05,
        )
        json_str = meta.model_dump_json()
        data = json.loads(json_str)
        assert data["preset"] == "standard"
        assert data["duration_seconds"] == 12.5
        assert data["review_score"] == 85
