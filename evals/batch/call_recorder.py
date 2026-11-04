"""What every transport shares: the batch queue lookup and the usage ledger."""

from collections.abc import Callable
from typing import Any

from evals.batch.batch_queue import BatchQueue
from evals.batch.call_scope import current_scope, next_call_key, request_id
from evals.batch.usage_ledger import UsageLedger
from evals.models.call_usage import CallUsage

type QueueSource = Callable[[str], BatchQueue | None]
"""The batch queue for a model, or None to call it online."""


class CallRecorder:
    """Sends a call through its model's batch queue (or not) and records usage."""

    def __init__(
        self, provider: str, ledger: UsageLedger, queues: QueueSource | None
    ) -> None:
        self.provider = provider
        self._ledger = ledger
        self._queues = queues

    def queue_for(self, model: str) -> BatchQueue | None:
        """The model's batch queue, or None when calls go online."""
        return self._queues(model) if self._queues is not None else None

    async def batched(
        self, queue: BatchQueue, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send ``params`` in a batch under the current call's request ID."""
        return await queue.request(request_id(next_call_key()), params)

    def online(self) -> None:
        """Count an online call in the current scope (keeps keys aligned)."""
        next_call_key()

    def record(self, model: str, *, batched: bool, **tokens: int) -> None:
        """Record one call's tokens for the current scope."""
        self._ledger.record(
            CallUsage(
                scope=current_scope(),
                provider=self.provider,
                model=model,
                batched=batched,
                **tokens,
            )
        )
