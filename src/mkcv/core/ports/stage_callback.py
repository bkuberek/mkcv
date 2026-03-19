"""Port interface for pipeline stage completion callbacks."""

from typing import Protocol, runtime_checkable

from mkcv.core.models.stage_metadata import StageMetadata


@runtime_checkable
class StageCallbackPort(Protocol):
    """Callback invoked after each pipeline stage completes.

    Used by interactive mode to display stage results and let the
    user decide whether to continue.

    Return True to proceed to the next stage, False to stop.
    """

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
