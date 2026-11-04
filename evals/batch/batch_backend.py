"""What a provider's batch API must do for the queue."""

from collections.abc import Sequence
from typing import Protocol

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.submitted_batch import SubmittedBatch


class BatchBackend(Protocol):
    """Submit a batch of requests for one model, then collect its outcomes."""

    async def submit(
        self, model: str, requests: Sequence[BatchRequest]
    ) -> SubmittedBatch:
        """Send ``requests`` as one batch and return what the provider accepted."""
        ...

    async def poll(self, batch: SubmittedBatch) -> list[BatchOutcome] | None:
        """Return the batch's outcomes once it has ended, else None."""
        ...
