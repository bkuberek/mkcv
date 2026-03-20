"""Tests for generate command progress callbacks."""

from rich.console import Console

from mkcv.cli.commands.generate import (
    _ProgressCallback,
    _StopAfterStageCallback,
)
from mkcv.core.models.stage_metadata import StageMetadata


def _make_metadata(
    stage_number: int = 1,
    duration: float = 2.5,
    model: str = "test-model",
) -> StageMetadata:
    """Create a StageMetadata for testing."""
    return StageMetadata(
        stage_number=stage_number,
        stage_name=f"stage_{stage_number}",
        provider="stub",
        model=model,
        temperature=0.3,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        duration_seconds=duration,
    )


class TestProgressCallback:
    """Tests for _ProgressCallback (non-interactive spinner)."""

    def test_on_stage_start_creates_status(self) -> None:
        console = Console(force_terminal=False)
        cb = _ProgressCallback(console)
        cb.on_stage_start(1)
        assert cb._status is not None

    def test_on_stage_complete_clears_status(self) -> None:
        console = Console(force_terminal=False)
        cb = _ProgressCallback(console)
        cb.on_stage_start(1)
        meta = _make_metadata(stage_number=1)
        result = cb.on_stage_complete(1, "analyze_jd", meta)
        assert result is True
        assert cb._status is None

    def test_on_stage_complete_always_returns_true(self) -> None:
        console = Console(force_terminal=False)
        cb = _ProgressCallback(console)
        for stage in range(1, 6):
            cb.on_stage_start(stage)
            meta = _make_metadata(stage_number=stage)
            assert cb.on_stage_complete(stage, f"stage_{stage}", meta) is True

    def test_on_stage_complete_without_prior_start(self) -> None:
        console = Console(force_terminal=False)
        cb = _ProgressCallback(console)
        meta = _make_metadata(stage_number=1)
        result = cb.on_stage_complete(1, "analyze_jd", meta)
        assert result is True

    def test_spinner_does_not_crash_on_all_stages(self) -> None:
        console = Console(force_terminal=False)
        cb = _ProgressCallback(console)
        for stage in range(1, 6):
            cb.on_stage_start(stage)
            meta = _make_metadata(stage_number=stage, duration=1.5)
            cb.on_stage_complete(stage, f"stage_{stage}", meta)


class TestStopAfterStageCallback:
    """Tests for _StopAfterStageCallback (stops pipeline at a given stage)."""

    def test_on_stage_start_creates_status(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=3)
        cb.on_stage_start(1)
        assert cb._status is not None

    def test_on_stage_complete_clears_status(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=3)
        cb.on_stage_start(2)
        meta = _make_metadata(stage_number=2)
        result = cb.on_stage_complete(2, "select_experience", meta)
        assert result is True
        assert cb._status is None

    def test_continues_before_stop_stage(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=3)
        for stage in (1, 2):
            cb.on_stage_start(stage)
            meta = _make_metadata(stage_number=stage)
            assert cb.on_stage_complete(stage, f"stage_{stage}", meta) is True

    def test_stops_at_designated_stage(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=3)
        cb.on_stage_start(3)
        meta = _make_metadata(stage_number=3)
        result = cb.on_stage_complete(3, "tailor_content", meta)
        assert result is False

    def test_stops_after_stage_number(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=2)
        cb.on_stage_start(2)
        meta = _make_metadata(stage_number=2)
        assert cb.on_stage_complete(2, "select_experience", meta) is False

    def test_on_stage_complete_without_prior_start(self) -> None:
        console = Console(force_terminal=False)
        cb = _StopAfterStageCallback(console, stop_after=3)
        meta = _make_metadata(stage_number=1)
        result = cb.on_stage_complete(1, "analyze_jd", meta)
        assert result is True
