"""Anthropic Message Batches."""

from collections.abc import Sequence
from typing import Any

import anthropic

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.submitted_batch import SubmittedBatch
from mkcv.core.exceptions.provider import ProviderError


class AnthropicBatchBackend:
    """Sends requests as one Message Batch and reads its results.

    ``client`` is an ``anthropic.AsyncAnthropic``. Each request's body is the
    ``messages.create`` parameters the online adapter built.

    Implements: BatchBackend
    """

    def __init__(self, client: Any, provider: str) -> None:
        self._client = client
        self._provider = provider

    async def submit(
        self, model: str, requests: Sequence[BatchRequest]
    ) -> SubmittedBatch:
        """Create the batch."""
        try:
            batch = await self._client.messages.batches.create(
                requests=[
                    {"custom_id": request.custom_id, "params": request.params}
                    for request in requests
                ]
            )
        except anthropic.APIError as error:
            raise ProviderError(str(error), provider=self._provider) from error
        return SubmittedBatch(
            provider=self._provider,
            model=model,
            batch_id=batch.id,
            custom_ids=tuple(request.custom_id for request in requests),
        )

    async def poll(self, batch: SubmittedBatch) -> list[BatchOutcome] | None:
        """Return the outcomes once processing has ended."""
        try:
            current = await self._client.messages.batches.retrieve(batch.batch_id)
            if current.processing_status != "ended":
                return None
            results = await self._client.messages.batches.results(batch.batch_id)
            return [_outcome(item) async for item in results]
        except anthropic.APIError as error:
            raise ProviderError(str(error), provider=self._provider) from error


def _outcome(item: Any) -> BatchOutcome:
    result = item.result
    if result.type == "succeeded":
        return BatchOutcome(
            custom_id=item.custom_id, response=result.message.model_dump(mode="json")
        )
    detail = getattr(getattr(result, "error", None), "error", None)
    message = getattr(detail, "message", None) or result.type
    return BatchOutcome(custom_id=item.custom_id, error=str(message))
