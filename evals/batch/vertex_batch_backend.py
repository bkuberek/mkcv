"""Vertex AI batch prediction for Gemini, with input and output in Cloud Storage."""

import json
import uuid
from collections.abc import Sequence
from typing import Any

from google.genai import errors, types

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.cloud_storage import CloudStorage
from evals.batch.submitted_batch import SubmittedBatch
from mkcv.core.exceptions.provider import ProviderError

REQUEST_LABEL = "mkcv_request"
"""The request label that carries each request's ID through the batch."""

_ENDED = frozenset(
    {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_PARTIALLY_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }
)


class VertexBatchBackend:
    """Writes the requests to ``<prefix>/<batch>/input.jsonl`` and runs a job.

    ``client`` is a ``google.genai.Client`` in Vertex AI mode; ``prefix`` is
    the run's folder in the bucket (``gs://bucket/runs/<run id>/batches``),
    so runs never share files. Each request's ID travels in its labels, and
    the paths are kept with the submitted batch for a resumed run.

    Implements: BatchBackend
    """

    def __init__(
        self, client: Any, provider: str, storage: CloudStorage, prefix: str
    ) -> None:
        self._client = client
        self._provider = provider
        self._storage = storage
        self._prefix = prefix.rstrip("/")

    async def submit(
        self, model: str, requests: Sequence[BatchRequest]
    ) -> SubmittedBatch:
        """Upload the input file and create the batch prediction job."""
        folder = f"{self._prefix}/{uuid.uuid4().hex}"
        input_uri, output_uri = f"{folder}/input.jsonl", f"{folder}/output"
        lines = "".join(
            json.dumps(
                {
                    "request": {
                        **request.params,
                        "labels": {REQUEST_LABEL: request.custom_id},
                    }
                }
            )
            + "\n"
            for request in requests
        )
        try:
            await self._storage.upload(input_uri, lines)
            job = await self._client.aio.batches.create(
                model=model,
                src=input_uri,
                config=types.CreateBatchJobConfig(dest=output_uri),
            )
        except (errors.APIError, OSError) as error:
            raise ProviderError(str(error), provider=self._provider) from error
        return SubmittedBatch(
            provider=self._provider,
            model=model,
            batch_id=str(job.name),
            custom_ids=tuple(request.custom_id for request in requests),
            extra={"input_uri": input_uri, "output_uri": output_uri},
        )

    async def poll(self, batch: SubmittedBatch) -> list[BatchOutcome] | None:
        """Return the outcomes once the job has ended."""
        try:
            job = await self._client.aio.batches.get(name=batch.batch_id)
            state = getattr(job.state, "name", str(job.state))
            if state not in _ENDED:
                return None
            lines = await self._storage.read_jsonl(batch.extra["output_uri"])
        except (errors.APIError, OSError) as error:
            raise ProviderError(str(error), provider=self._provider) from error
        found = {outcome.custom_id: outcome for outcome in map(_outcome, lines)}
        return [
            found.get(cid, BatchOutcome(cid, error=f"the job ended as {state}"))
            for cid in batch.custom_ids
        ]


def _outcome(line: dict[str, Any]) -> BatchOutcome:
    labels = (line.get("request") or {}).get("labels") or {}
    custom_id = str(labels.get(REQUEST_LABEL, ""))
    response = line.get("response")
    if isinstance(response, dict) and response.get("candidates"):
        return BatchOutcome(custom_id=custom_id, response=response)
    return BatchOutcome(
        custom_id=custom_id, error=str(line.get("status") or "no response")
    )
