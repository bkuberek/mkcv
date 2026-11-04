"""Tests for queueing requests into provider batches, and resuming them."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_queue import BatchQueue
from evals.batch.batch_store import BatchStore
from evals.batch.call_scope import call_scope, next_call_key, request_id
from evals.batch.submitted_batch import SubmittedBatch
from evals.models.batch_settings import BatchSettings
from mkcv.core.exceptions.provider import ProviderError
from tests.test_evals.batch_fakes import FakeBackend, no_wait


def _echo(custom_id: str, params: dict[str, Any] | None) -> BatchOutcome:
    return BatchOutcome(custom_id, response={"echo": (params or {}).get("n")})


def _queue(
    backend: FakeBackend, tmp_path: Path, **settings: Any
) -> tuple[BatchQueue, BatchStore]:
    store = BatchStore(tmp_path / "batches")
    options = {"enabled": True, "flush_seconds": 0.0, "poll_seconds": 0.0, **settings}
    return (
        BatchQueue(
            "fake", "m", backend, store, BatchSettings(**options), sleep=no_wait
        ),
        store,
    )


class TestFlushing:
    async def test_concurrent_requests_go_out_as_one_batch(
        self, tmp_path: Path
    ) -> None:
        backend = FakeBackend(_echo)
        queue, _ = _queue(backend, tmp_path)
        replies = await asyncio.gather(
            *(queue.request(f"id{n}", {"n": n}) for n in range(3))
        )
        assert replies == [{"echo": 0}, {"echo": 1}, {"echo": 2}]
        assert [len(batch) for batch in backend.submitted] == [3]

    async def test_a_full_queue_flushes_at_once(self, tmp_path: Path) -> None:
        backend = FakeBackend(_echo)
        queue, _ = _queue(backend, tmp_path, max_requests=2, flush_seconds=3600)
        replies = await asyncio.gather(
            *(queue.request(f"id{n}", {"n": n}) for n in range(2))
        )
        assert len(replies) == 2
        assert [len(batch) for batch in backend.submitted] == [2]

    async def test_it_polls_until_the_batch_has_ended(self, tmp_path: Path) -> None:
        backend = FakeBackend(_echo, polls_before_done=2)
        queue, _ = _queue(backend, tmp_path)
        assert await queue.request("id", {"n": 7}) == {"echo": 7}
        assert backend.polls == 3

    async def test_a_failed_request_fails_only_its_caller(self, tmp_path: Path) -> None:
        def reply(custom_id: str, params: dict[str, Any] | None) -> BatchOutcome:
            if custom_id == "bad":
                return BatchOutcome(custom_id, error="overloaded")
            return _echo(custom_id, params)

        queue, _ = _queue(FakeBackend(reply), tmp_path)
        good, bad = await asyncio.gather(
            queue.request("good", {"n": 1}),
            queue.request("bad", {"n": 2}),
            return_exceptions=True,
        )
        assert good == {"echo": 1}
        assert isinstance(bad, ProviderError)
        assert "overloaded" in str(bad)

    async def test_an_unexpected_error_fails_the_callers_instead_of_hanging(
        self, tmp_path: Path
    ) -> None:
        def broken(custom_id: str, params: dict[str, Any] | None) -> BatchOutcome:
            raise RuntimeError("bad reply")

        queue, _ = _queue(FakeBackend(broken), tmp_path)
        with pytest.raises(ProviderError, match="did not complete"):
            await asyncio.wait_for(queue.request("id", {"n": 1}), timeout=5)

    async def test_a_rejected_batch_fails_every_caller(self, tmp_path: Path) -> None:
        queue, _ = _queue(FakeBackend(_echo, fail_submit=True), tmp_path)
        with pytest.raises(ProviderError, match="quota exceeded"):
            await queue.request("id", {"n": 1})


class TestDurability:
    async def test_submitted_batches_and_results_are_stored(
        self, tmp_path: Path
    ) -> None:
        queue, _ = _queue(FakeBackend(_echo), tmp_path)
        await queue.request("id", {"n": 1})
        reloaded = BatchStore(tmp_path / "batches")
        assert reloaded.result("id") == BatchOutcome("id", response={"echo": 1})
        assert reloaded.batch_of("id") is not None

    async def test_a_stored_result_is_never_requested_again(
        self, tmp_path: Path
    ) -> None:
        first = FakeBackend(_echo)
        queue, _ = _queue(first, tmp_path)
        await queue.request("id", {"n": 1})
        again = FakeBackend(_echo)
        resumed, _ = _queue(again, tmp_path)
        assert await resumed.request("id", {"n": 1}) == {"echo": 1}
        assert (again.submitted, again.polls) == ([], 0)

    async def test_a_resumed_request_waits_for_its_submitted_batch(
        self, tmp_path: Path
    ) -> None:
        BatchStore(tmp_path / "batches").record_submitted(
            SubmittedBatch(
                provider="fake", model="m", batch_id="old", custom_ids=("id",)
            )
        )
        resumed = FakeBackend(
            lambda cid, params: BatchOutcome(cid, response={"done": 1})
        )
        queue, _ = _queue(resumed, tmp_path)
        assert await queue.request("id", {"n": 1}) == {"done": 1}
        assert resumed.submitted == []
        assert resumed.polls == 1


class TestCallScope:
    def test_calls_in_a_scope_get_numbered_keys(self) -> None:
        with call_scope("finals/case/tailor/openai/gpt/r0"):
            assert next_call_key() == "finals/case/tailor/openai/gpt/r0#0"
            assert next_call_key() == "finals/case/tailor/openai/gpt/r0#1"

    def test_outside_a_scope_there_is_no_key(self) -> None:
        assert next_call_key() is None

    def test_the_request_id_is_stable_and_provider_safe(self) -> None:
        first = request_id("finals/a/tailor/x/y/r0#0")
        assert first == request_id("finals/a/tailor/x/y/r0#0")
        assert first.isalnum() and len(first) <= 64
        assert request_id(None) != request_id(None)
