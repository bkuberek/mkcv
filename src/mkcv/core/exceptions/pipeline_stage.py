"""Pipeline stage execution error."""

from mkcv.core.exceptions.base import MkcvError


class PipelineStageError(MkcvError):
    """A pipeline stage failed during execution."""

    def __init__(self, message: str, *, stage: str = "", stage_number: int = 0) -> None:
        self.stage = stage
        self.stage_number = stage_number
        super().__init__(message, exit_code=5)
