"""Port interface for pipeline stage completion callbacks."""

from typing import Protocol, runtime_checkable

from mkcv.core.models.stage_metadata import StageMetadata


@runtime_checkable
class StageCallbackPort(Protocol):
    """Callback invoked before and after each pipeline stage.

    Used to show progress (spinners) and let interactive mode
    pause between stages.

    Return True from on_stage_complete to proceed, False to stop.
    """

    def on_stage_start(
        self,
        stage_number: int,
    ) -> None:
        """Called just before a pipeline stage begins.

        Args:
            stage_number: Stage number (1-5).
        """
        ...

    def on_stage_complete(
        self,
        stage_number: int,
        stage_name: str,
        metadata: StageMetadata,
    ) -> bool:
        """Called after a pipeline stage finishes.

        Args:
            stage_number: Stage number (1-5).
            stage_name: Human-readable stage name.
            metadata: Timing and model metadata for the stage.

        Returns:
            True to continue to the next stage, False to stop.
        """
        ...
