"""Gather concurrent requests for one model and send them as provider batches."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from evals.batch.batch_backend import BatchBackend
from evals.batch.batch_outcome import BatchOutcome
from evals.batch.batch_request import BatchRequest
from evals.batch.batch_store import BatchStore
from evals.batch.submitted_batch import SubmittedBatch
from evals.models.batch_settings import BatchSettings
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.exceptions.provider import ProviderError

logger = logging.getLogger(__name__)

type Sleep = Callable[[float], Awaitable[None]]


class BatchQueue:
    """Queues requests for one provider and model and resolves each caller.

    A request waits until ``max_requests`` are queued or ``flush_seconds``
    have passed since the first one, then the whole queue goes out as one
    batch; the queue polls it every ``poll_seconds`` until it has ended. A
    request that a stored result already answers, or that sits in a batch
    submitted before (a resumed run), is never sent again.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        backend: BatchBackend,
        store: BatchStore,
        settings: BatchSettings,
        *,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._provider = provider
        self._model = model
        self._backend = backend
        self._store = store
        self._settings = settings
        self._sleep = sleep
        self._waiting: list[tuple[BatchRequest, asyncio.Future[BatchOutcome]]] = []
        self._timer: asyncio.Task[None] | None = None
        self._collectors: dict[str, asyncio.Task[None]] = {}
        self._background: set[asyncio.Task[None]] = set()

    async def request(self, custom_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return the response body for ``params``, sending it in a batch.

        Raises:
            ProviderError: If the batch, or this request in it, failed.
        """
        outcome = self._store.result(custom_id)
        if outcome is None:
            submitted = self._store.batch_of(custom_id)
            if submitted is not None:
                await self._collected(submitted)
                outcome = self._store.result(custom_id)
            else:
                outcome = await self._enqueue(BatchRequest(custom_id, params))
        return _response(self._provider, outcome)

    async def _enqueue(self, request: BatchRequest) -> BatchOutcome:
        future: asyncio.Future[BatchOutcome] = (
            asyncio.get_running_loop().create_future()
        )
        self._waiting.append((request, future))
        if len(self._waiting) >= self._settings.max_requests:
            self._start(self._flush())
        elif self._timer is None:
            self._timer = self._start(self._flush_later())
        return await future

    async def _flush_later(self) -> None:
        await self._sleep(self._settings.flush_seconds)
        self._timer = None
        await self._flush()

    async def _flush(self) -> None:
        waiting, self._waiting = self._waiting, []
        if self._timer is not None and asyncio.current_task() is not self._timer:
            self._timer.cancel()
            self._timer = None
        if not waiting:
            return
        try:
            await self._send(waiting)
        finally:
            for _, future in waiting:
                if not future.done():
                    future.set_exception(
                        ProviderError(
                            "the batch did not complete", provider=self._provider
                        )
                    )

    async def _send(
        self, waiting: list[tuple[BatchRequest, "asyncio.Future[BatchOutcome]"]]
    ) -> None:
        """Submit ``waiting`` as one batch and resolve every caller.

        A caller the batch could not answer is failed by ``_flush`` whatever
        went wrong here, so no caller waits forever.
        """
        try:
            batch = await self._backend.submit(
                self._model, [request for request, _ in waiting]
            )
            self._store.record_submitted(batch)
            logger.info(
                "Submitted %s batch %s (%d requests)",
                self._provider,
                batch.batch_id,
                len(waiting),
            )
            await self._collected(batch)
        except (MkcvError, OSError, ValueError) as error:
            for _, future in waiting:
                if not future.done():
                    future.set_exception(
                        ProviderError(f"batch failed: {error}", provider=self._provider)
                    )
            return
        for request, future in waiting:
            outcome = self._store.result(request.custom_id) or BatchOutcome(
                request.custom_id, error="the batch returned no result for it"
            )
            if not future.done():
                future.set_result(outcome)

    async def _collected(self, batch: SubmittedBatch) -> None:
        """Wait until ``batch`` has ended and its outcomes are stored."""
        task = self._collectors.get(batch.batch_id)
        if task is None:
            task = self._start(self._collect(batch))
            self._collectors[batch.batch_id] = task
        await asyncio.shield(task)

    async def _collect(self, batch: SubmittedBatch) -> None:
        while (outcomes := await self._backend.poll(batch)) is None:
            await self._sleep(self._settings.poll_seconds)
        self._store.record_results(outcomes)

    def _start(self, work: Awaitable[None]) -> asyncio.Task[None]:
        task = asyncio.ensure_future(work)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task


def _response(provider: str, outcome: BatchOutcome | None) -> dict[str, Any]:
    if outcome is None:
        raise ProviderError("the batch returned no result", provider=provider)
    if outcome.response is None:
        raise ProviderError(
            f"batch request failed: {outcome.error or 'no response'}",
            provider=provider,
        )
    return outcome.response
