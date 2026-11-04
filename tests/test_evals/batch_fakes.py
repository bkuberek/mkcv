"""Fake SDK batch clients and backends for the batching tests (no network)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.submitted_batch import SubmittedBatch


async def no_wait(seconds: float) -> None:
    """A sleep that returns at once."""


def anthropic_message(text: str, **usage: int) -> dict[str, Any]:
    """A Messages API response body with one text block."""
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20, **usage},
    }


def chat_completion(text: str, *, cached: int = 0) -> dict[str, Any]:
    """A Chat Completions response body."""
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-6-astra",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": text},
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": cached},
        },
    }


def gemini_response(text: str, *, cached: int = 0) -> dict[str, Any]:
    """A generateContent response body, as a batch output file holds it."""
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "cachedContentTokenCount": cached,
        },
    }


@dataclass
class FakeBackend:
    """Answers every request with ``reply(params)``; counts submissions.

    ``polls_before_done`` makes a batch report itself running that many
    times before it ends.
    """

    reply: Any
    polls_before_done: int = 0
    submitted: list[list[BatchRequest]] = field(default_factory=list)
    polls: int = 0
    fail_submit: bool = False

    async def submit(
        self, model: str, requests: Sequence[BatchRequest]
    ) -> SubmittedBatch:
        if self.fail_submit:
            from mkcv.core.exceptions.provider import ProviderError

            raise ProviderError("quota exceeded")
        self.submitted.append(list(requests))
        return SubmittedBatch(
            provider="fake",
            model=model,
            batch_id=f"batch-{len(self.submitted)}",
            custom_ids=tuple(r.custom_id for r in requests),
        )

    async def poll(self, batch: SubmittedBatch) -> list[BatchOutcome] | None:
        self.polls += 1
        if self.polls <= self.polls_before_done:
            return None
        requests = {r.custom_id: r for group in self.submitted for r in group}
        return [
            self.reply(cid, requests[cid].params if cid in requests else None)
            for cid in batch.custom_ids
        ]


class FakeAnthropicBatches:
    """``client.messages.batches`` of the Anthropic SDK."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.created: list[list[dict[str, Any]]] = []

    async def create(self, *, requests: list[dict[str, Any]]) -> Any:
        self.created.append(requests)
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}")

    async def retrieve(self, batch_id: str) -> Any:
        return SimpleNamespace(processing_status="ended")

    async def results(self, batch_id: str) -> Any:
        from anthropic.types import Message

        index = int(batch_id.rsplit("_", 1)[1]) - 1

        async def items() -> Any:
            for request in self.created[index]:
                yield SimpleNamespace(
                    custom_id=request["custom_id"],
                    result=SimpleNamespace(
                        type="succeeded",
                        message=Message.model_validate(anthropic_message(self.text)),
                    ),
                )

        return items()


class FakeOpenAIClient:
    """``files`` and ``batches`` of the OpenAI SDK."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.uploads: list[str] = []
        self.files = SimpleNamespace(create=self._upload, content=self._content)
        self.batches = SimpleNamespace(create=self._create, retrieve=self._retrieve)
        self.base_url = "https://api.openai.com/v1"

    async def _upload(self, *, file: tuple[str, bytes], purpose: str) -> Any:
        self.uploads.append(file[1].decode("utf-8"))
        return SimpleNamespace(id=f"file-{len(self.uploads)}")

    async def _create(self, **options: Any) -> Any:
        return SimpleNamespace(id=f"batch_{len(self.uploads)}", options=options)

    async def _retrieve(self, batch_id: str) -> Any:
        index = batch_id.rsplit("_", 1)[1]
        return SimpleNamespace(
            status="completed", output_file_id=f"out-{index}", error_file_id=None
        )

    async def _content(self, file_id: str) -> Any:
        index = int(file_id.rsplit("-", 1)[1]) - 1
        lines = []
        for line in self.uploads[index].splitlines():
            request = json.loads(line)
            lines.append(
                json.dumps(
                    {
                        "custom_id": request["custom_id"],
                        "response": {
                            "status_code": 200,
                            "body": chat_completion(self.text),
                        },
                        "error": None,
                    }
                )
            )
        return SimpleNamespace(text="\n".join(lines))


class FakeStorage:
    """Cloud Storage held in a dict; the fake Vertex job writes the output."""

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}

    async def upload(self, uri: str, text: str) -> None:
        self.objects[uri] = text

    async def read_jsonl(self, prefix_uri: str) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for uri, text in sorted(self.objects.items())
            if uri.startswith(prefix_uri) and uri.endswith(".jsonl")
            for line in text.splitlines()
            if line.strip()
        ]


class FakeVertexBatches:
    """``client.aio.batches`` of google-genai in Vertex AI mode."""

    def __init__(self, storage: FakeStorage, text: str) -> None:
        self.storage = storage
        self.text = text
        self.jobs: list[dict[str, Any]] = []

    async def create(self, *, model: str, src: str, config: Any) -> Any:
        self.jobs.append({"model": model, "src": src, "dest": config.dest})
        lines = [
            json.dumps(
                {
                    "request": json.loads(line)["request"],
                    "response": gemini_response(self.text),
                    "status": "",
                }
            )
            for line in self.storage.objects[src].splitlines()
        ]
        await self.storage.upload(
            f"{config.dest}/prediction-1/predictions.jsonl", "\n".join(lines)
        )
        return SimpleNamespace(name=f"projects/p/batchPredictionJobs/{len(self.jobs)}")

    async def get(self, *, name: str) -> Any:
        return SimpleNamespace(state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"))
