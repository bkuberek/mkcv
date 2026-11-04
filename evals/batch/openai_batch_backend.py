"""The OpenAI Batch API on ``/v1/chat/completions``."""

import json
from collections.abc import Sequence
from typing import Any

import openai

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.submitted_batch import SubmittedBatch
from mkcv.core.exceptions.provider import ProviderError

ENDPOINT = "/v1/chat/completions"
_RUNNING = frozenset({"validating", "in_progress", "finalizing", "cancelling"})
_HTTP_OK = 200


class OpenAIBatchBackend:
    """Uploads the requests as JSONL, creates the batch, and reads its files.

    ``client`` is an ``openai.AsyncOpenAI``. Each request's body is the
    ``chat.completions.create`` parameters the online adapter built.

    Implements: BatchBackend
    """

    def __init__(self, client: Any, provider: str) -> None:
        self._client = client
        self._provider = provider

    async def submit(
        self, model: str, requests: Sequence[BatchRequest]
    ) -> SubmittedBatch:
        """Upload the input file and create the batch."""
        lines = "".join(
            json.dumps(
                {
                    "custom_id": request.custom_id,
                    "method": "POST",
                    "url": ENDPOINT,
                    "body": request.params,
                }
            )
            + "\n"
            for request in requests
        )
        try:
            upload = await self._client.files.create(
                file=("batch.jsonl", lines.encode("utf-8")), purpose="batch"
            )
            batch = await self._client.batches.create(
                input_file_id=upload.id, endpoint=ENDPOINT, completion_window="24h"
            )
        except openai.APIError as error:
            raise ProviderError(str(error), provider=self._provider) from error
        return SubmittedBatch(
            provider=self._provider,
            model=model,
            batch_id=batch.id,
            custom_ids=tuple(request.custom_id for request in requests),
            extra={"input_file_id": upload.id},
        )

    async def poll(self, batch: SubmittedBatch) -> list[BatchOutcome] | None:
        """Return the outcomes once the batch has ended."""
        try:
            current = await self._client.batches.retrieve(batch.batch_id)
            if current.status in _RUNNING:
                return None
            found: dict[str, BatchOutcome] = {}
            for file_id in (current.output_file_id, current.error_file_id):
                if file_id:
                    content = await self._client.files.content(file_id)
                    for line in content.text.splitlines():
                        if line.strip():
                            outcome = _outcome(json.loads(line))
                            found[outcome.custom_id] = outcome
        except openai.APIError as error:
            raise ProviderError(str(error), provider=self._provider) from error
        missing = BatchOutcome("", error=f"the batch ended as '{current.status}'")
        return [
            found.get(cid, BatchOutcome(cid, error=missing.error))
            for cid in batch.custom_ids
        ]


def _outcome(line: dict[str, Any]) -> BatchOutcome:
    custom_id = str(line.get("custom_id", ""))
    response = line.get("response") or {}
    if response.get("status_code") == _HTTP_OK and isinstance(
        response.get("body"), dict
    ):
        return BatchOutcome(custom_id=custom_id, response=response["body"])
    error = line.get("error") or response.get("body", {}).get("error") or {}
    message = error.get("message") if isinstance(error, dict) else str(error)
    return BatchOutcome(custom_id=custom_id, error=message or "request failed")
