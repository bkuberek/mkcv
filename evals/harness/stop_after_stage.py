"""A pipeline callback that stops the run after one stage."""

from mkcv.core.models.stage_metadata import StageMetadata


class StopAfterStage:
    """Stop the pipeline once stage ``stage_number`` completes.

    Pairs with ``PipelineService.generate(from_stage=stage_number)`` to run
    exactly one stage. Implements: StageCallbackPort
    """

    def __init__(self, stage_number: int) -> None:
        self._stage_number = stage_number
        self._metadata: StageMetadata | None = None

    @property
    def metadata(self) -> StageMetadata | None:
        """Metadata of the target stage, or None until it has completed."""
        return self._metadata

    def on_stage_start(self, stage_number: int) -> None:
        """Do nothing: the harness only cares about completion."""

    def on_stage_complete(
        self,
        stage_number: int,
        stage_name: str,
        metadata: StageMetadata,
    ) -> bool:
        """Keep the target stage's metadata and stop after it."""
        if stage_number != self._stage_number:
            return True
        self._metadata = metadata
        return False
