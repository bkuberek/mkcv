"""Tests for sending mkcv's own adapter requests through provider batches."""

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from dynaconf import Dynaconf
from pydantic import BaseModel

from evals.batch.anthropic_batch_backend import AnthropicBatchBackend
from evals.batch.anthropic_transport import AnthropicTransport, mark_cacheable
from evals.batch.batch_queue import BatchQueue
from evals.batch.batch_store import BatchStore
from evals.batch.call_recorder import CallRecorder
from evals.batch.call_scope import call_scope
from evals.batch.eval_adapters import EvalAdapters
from evals.batch.google_transport import GoogleTransport, vertex_request
from evals.batch.openai_batch_backend import OpenAIBatchBackend
from evals.batch.openai_transport import OpenAITransport
from evals.batch.usage_ledger import UsageLedger
from evals.batch.vertex_batch_backend import REQUEST_LABEL, VertexBatchBackend
from evals.models.batch_settings import BatchSettings
from mkcv.adapters.factory import create_provider_registry
from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.adapters.llm.google import GoogleGeminiAdapter
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.batch_fakes import (
    FakeAnthropicBatches,
    FakeOpenAIClient,
    FakeStorage,
    FakeVertexBatches,
    anthropic_message,
    no_wait,
)

SETTINGS = BatchSettings(enabled=True, flush_seconds=0.0, poll_seconds=0.0)
MESSAGES = [
    {"role": "system", "content": "Rubric."},
    {"role": "user", "content": "Stable prefix: JD and KB."},
    {"role": "user", "content": "The output to judge."},
]


class Verdict(BaseModel):
    score: int


def _queues(backend: Any, tmp_path: Path) -> Callable[[str], BatchQueue]:
    store = BatchStore(tmp_path / "batches")
    queues: dict[str, BatchQueue] = {}

    def queue_for(model: str) -> BatchQueue:
        return queues.setdefault(
            model, BatchQueue("p", model, backend, store, SETTINGS, sleep=no_wait)
        )

    return queue_for


class TestAnthropic:
    def _adapter(
        self, tmp_path: Path, ledger: UsageLedger, *, cache: bool = False
    ) -> tuple[AnthropicAdapter, FakeAnthropicBatches]:
        adapter = AnthropicAdapter(api_key="test-key")
        batches = FakeAnthropicBatches('{"score": 4}')
        client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
        backend = AnthropicBatchBackend(client, "anthropic")
        recorder = CallRecorder("anthropic", ledger, _queues(backend, tmp_path))
        adapter._client = AnthropicTransport(client, recorder, cache_prefix=cache)  # type: ignore[assignment]
        return adapter, batches

    async def test_a_structured_call_goes_out_in_a_message_batch(
        self, tmp_path: Path
    ) -> None:
        adapter, batches = self._adapter(tmp_path, UsageLedger())
        with call_scope("job"):
            verdict = await adapter.complete_structured(
                MESSAGES, model="claude-opus-5-5", response_model=Verdict
            )
        assert verdict == Verdict(score=4)
        [[request]] = batches.created
        assert request["custom_id"].isalnum()

    async def test_the_batch_carries_the_online_request_shape(
        self, tmp_path: Path
    ) -> None:
        adapter, batches = self._adapter(tmp_path, UsageLedger())
        await adapter.complete_structured(
            MESSAGES, model="claude-opus-5-5", response_model=Verdict, max_tokens=512
        )
        params = batches.created[0][0]["params"]
        assert params["model"] == "claude-opus-5-5"
        assert params["max_tokens"] >= 16000  # the Claude 5 output floor
        assert "temperature" not in params  # Claude 5 rejects sampling settings
        assert params["output_config"]["format"]["type"] == "json_schema"
        assert params["system"] == "Rubric."

    async def test_the_stable_prefix_is_marked_for_caching(
        self, tmp_path: Path
    ) -> None:
        adapter, batches = self._adapter(tmp_path, UsageLedger(), cache=True)
        await adapter.complete_structured(
            MESSAGES, model="claude-opus-5-5", response_model=Verdict
        )
        params = batches.created[0][0]["params"]
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        first, last = params["messages"]
        assert first["content"][0]["cache_control"] == {"type": "ephemeral"}
        assert last["content"] == "The output to judge."

    async def test_usage_is_recorded_for_the_scope(self, tmp_path: Path) -> None:
        ledger = UsageLedger()
        adapter, _ = self._adapter(tmp_path, ledger)
        with call_scope("job-1"):
            await adapter.complete_structured(
                MESSAGES, model="claude-opus-5-5", response_model=Verdict
            )
        [usage] = ledger.for_scope("job-1")
        assert (usage.batched, usage.input_tokens, usage.output_tokens) == (
            True,
            100,
            20,
        )


def test_cache_markers_leave_the_text_byte_stable() -> None:
    params = {"model": "m", "system": "S", "messages": MESSAGES[1:]}
    marked = mark_cacheable(params)
    assert marked["system"][0]["text"] == "S"
    assert marked["messages"][0]["content"][0]["text"] == MESSAGES[1]["content"]
    assert params["system"] == "S"  # the original request is untouched


async def test_online_anthropic_calls_record_cache_reads(tmp_path: Path) -> None:
    from anthropic.types import Message

    class Stream:
        async def __aenter__(self) -> "Stream":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get_final_message(self) -> Message:
            return Message.model_validate(
                anthropic_message(
                    '{"score": 3}',
                    cache_read_input_tokens=400,
                    cache_creation_input_tokens=50,
                )
            )

    client = SimpleNamespace(messages=SimpleNamespace(stream=lambda **_: Stream()))
    ledger = UsageLedger()
    adapter = AnthropicAdapter(api_key="test-key")
    adapter._client = AnthropicTransport(
        client, CallRecorder("anthropic", ledger, None)
    )  # type: ignore[assignment]
    assert await adapter.complete_structured(
        MESSAGES, model="claude-opus-5-5", response_model=Verdict
    ) == Verdict(score=3)
    [usage] = ledger.entries
    assert (usage.batched, usage.cache_read_tokens, usage.cache_write_tokens) == (
        False,
        400,
        50,
    )
    assert usage.input_tokens == 550


class TestOpenAI:
    async def test_a_structured_call_goes_out_in_a_batch_file(
        self, tmp_path: Path
    ) -> None:
        fake = FakeOpenAIClient('{"score": 5}')
        adapter = OpenAIAdapter(api_key="test-key")
        backend = OpenAIBatchBackend(fake, "openai")
        recorder = CallRecorder("openai", UsageLedger(), _queues(backend, tmp_path))
        adapter._client = OpenAITransport(fake, recorder)  # type: ignore[assignment]
        verdict = await adapter.complete_structured(
            MESSAGES, model="gpt-6-astra", response_model=Verdict
        )
        assert verdict == Verdict(score=5)
        [line] = [json.loads(line) for line in fake.uploads[0].splitlines()]
        assert (line["method"], line["url"]) == ("POST", "/v1/chat/completions")
        body = line["body"]
        assert body["model"] == "gpt-6-astra"
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "temperature" not in body  # GPT-6 rejects sampling settings


class TestVertex:
    def _adapter(
        self, tmp_path: Path
    ) -> tuple[GoogleGeminiAdapter, FakeStorage, FakeVertexBatches]:
        storage = FakeStorage()
        batches = FakeVertexBatches(storage, '{"score": 2}')
        client = SimpleNamespace(aio=SimpleNamespace(batches=batches))
        backend = VertexBatchBackend(
            client, "google", storage, "gs://bucket/runs/run-1/batches"
        )
        adapter = GoogleGeminiAdapter(api_key="test-key")
        recorder = CallRecorder("google", UsageLedger(), _queues(backend, tmp_path))
        adapter._client = GoogleTransport(client, recorder)  # type: ignore[assignment]
        return adapter, storage, batches

    async def test_a_structured_call_goes_out_as_a_vertex_batch_job(
        self, tmp_path: Path
    ) -> None:
        adapter, _, batches = self._adapter(tmp_path)
        verdict = await adapter.complete_structured(
            MESSAGES, model="gemini-4-argon", response_model=Verdict
        )
        assert verdict == Verdict(score=2)
        [job] = batches.jobs
        assert job["model"] == "gemini-4-argon"
        assert job["src"].startswith("gs://bucket/runs/run-1/batches/")

    async def test_the_batch_file_carries_the_online_request(
        self, tmp_path: Path
    ) -> None:
        adapter, storage, batches = self._adapter(tmp_path)
        await adapter.complete_structured(
            MESSAGES, model="gemini-4-argon", response_model=Verdict, max_tokens=100
        )
        request = json.loads(storage.objects[batches.jobs[0]["src"]])["request"]
        assert request["systemInstruction"] == {"parts": [{"text": "Rubric."}]}
        assert [c["role"] for c in request["contents"]] == ["user", "user"]
        config = request["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert config["maxOutputTokens"] >= 16000  # the Gemini thinking floor
        assert "responseJsonSchema" in config
        assert REQUEST_LABEL in request["labels"]


def test_an_unsupported_config_field_is_never_dropped() -> None:
    from google.genai import types

    request = {
        "model": "m",
        "contents": [],
        "config": types.GenerateContentConfig(top_k=3),
    }
    with pytest.raises(ValueError, match="top_k"):
        vertex_request(request)


class TestEvalAdapters:
    def _adapters(
        self, make_settings: Callable[..., Dynaconf], tmp_path: Path, **settings: Any
    ) -> EvalAdapters:
        return EvalAdapters(
            create_provider_registry(make_settings()),
            settings=BatchSettings(**settings),
            store=BatchStore(tmp_path / "batches"),
            ledger=UsageLedger(),
            run_id="run-1",
        )

    def test_a_real_adapter_gets_a_transport(
        self,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        adapter = self._adapters(make_settings, tmp_path, enabled=True).create(
            "anthropic"
        )
        assert isinstance(adapter, RetryingLLMAdapter)
        inner = adapter._inner  # type: ignore[attr-defined]
        assert isinstance(inner._client, AnthropicTransport)

    def test_an_adapter_without_an_sdk_client_is_left_alone(
        self,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        install_adapter: Callable[[LLMPort], LLMPort],
    ) -> None:
        stub = install_adapter(StubLLMAdapter())
        assert self._adapters(make_settings, tmp_path).create("anthropic") is stub

    def test_google_without_vertex_falls_back_online_with_a_warning(
        self,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        adapters = self._adapters(
            make_settings, tmp_path, enabled=True, google_gcs_bucket="gs://b"
        )
        adapter = adapters.create("google")
        transport = adapter._inner._client  # type: ignore[attr-defined]
        assert transport._recorder.queue_for("gemini-4-argon") is None
        assert "Vertex AI" in caplog.text
