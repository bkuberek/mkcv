"""Build the LLM adapters an eval run calls models with.

Each adapter is mkcv's own online adapter for the provider, with its SDK
client swapped for a transport (see ``evals.batch.*_transport``). The
adapter still builds and parses every request, so batches carry exactly the
request an online call would; the transport sends it in a provider batch
(when batching applies) or online, marks the stable prompt prefix for
caching (Anthropic, when asked), and records the call's tokens.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from evals.batch.anthropic_batch_backend import AnthropicBatchBackend
from evals.batch.anthropic_transport import AnthropicTransport
from evals.batch.batch_backend import BatchBackend
from evals.batch.batch_queue import BatchQueue, Sleep
from evals.batch.batch_store import BatchStore
from evals.batch.call_recorder import CallRecorder
from evals.batch.cloud_storage import CloudStorage
from evals.batch.google_cloud_storage import GoogleCloudStorage
from evals.batch.google_transport import GoogleTransport
from evals.batch.openai_batch_backend import OpenAIBatchBackend
from evals.batch.openai_transport import OpenAITransport
from evals.batch.usage_ledger import UsageLedger
from evals.batch.vertex_batch_backend import VertexBatchBackend
from evals.models.batch_settings import BatchSettings
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.ports.llm import LLMPort

logger = logging.getLogger(__name__)

_BATCH_KINDS = frozenset(
    {ProviderKind.ANTHROPIC, ProviderKind.OPENAI, ProviderKind.GOOGLE}
)


class EvalAdapters:
    """Creates transport-backed adapters and owns the run's batch queues.

    Args:
        registry: Where provider specs, keys, and online adapters come from.
        settings: Whether and how to batch.
        store: Where submitted batches and results persist (needed to batch).
        ledger: Where every call's tokens are recorded.
        run_id: Names the run's folder in the Vertex AI bucket.
        cache_prefix: Mark the stable prompt prefix of Anthropic calls.
        storage: Cloud Storage for Vertex AI batch files (ADC by default).
        sleep: How queues wait between flushes and polls (tests pass a fake).
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        settings: BatchSettings,
        store: BatchStore | None,
        ledger: UsageLedger,
        run_id: str,
        cache_prefix: bool = False,
        storage: CloudStorage | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._store = store
        self._ledger = ledger
        self._run_id = run_id
        self._cache_prefix = cache_prefix
        self._storage = storage
        self._sleep = sleep
        self._queues: dict[tuple[str, str], BatchQueue] = {}
        self._backends: dict[str, BatchBackend] = {}
        self._warned: set[str] = set()

    @property
    def ledger(self) -> UsageLedger:
        """The usage of every call made through these adapters."""
        return self._ledger

    def create(self, provider: str) -> LLMPort:
        """Return an adapter for ``provider`` whose calls go through a transport.

        An adapter without an SDK client (the stub, or a test double) is
        returned as the registry made it.

        Raises:
            ConfigurationError: If the provider is unknown or has no key.
        """
        adapter = self._registry.create_adapter(provider, with_retry=False)
        client = getattr(adapter, "_client", None)
        if client is None:
            return adapter
        kind = self._registry.get(provider).kind
        recorder = CallRecorder(
            provider, self._ledger, self._queue_source(provider, kind, client)
        )
        transport: Any
        if kind is ProviderKind.ANTHROPIC:
            transport = AnthropicTransport(
                client, recorder, cache_prefix=self._cache_prefix
            )
        elif kind is ProviderKind.GOOGLE:
            transport = GoogleTransport(client, recorder)
        else:
            transport = OpenAITransport(client, recorder)
        adapter._client = transport  # type: ignore[attr-defined]
        return RetryingLLMAdapter(adapter)

    def _queue_source(
        self, provider: str, kind: ProviderKind, client: Any
    ) -> Callable[[str], BatchQueue | None] | None:
        backend = self._backend(provider, kind, client)
        if backend is None or self._store is None:
            return None
        store = self._store

        def queue_for(model: str) -> BatchQueue:
            key = (provider, model)
            if key not in self._queues:
                self._queues[key] = BatchQueue(
                    provider, model, backend, store, self._settings, sleep=self._sleep
                )
            return self._queues[key]

        return queue_for

    def _backend(
        self, provider: str, kind: ProviderKind, client: Any
    ) -> BatchBackend | None:
        if not self._settings.enabled or kind not in _BATCH_KINDS:
            return None
        if provider in self._backends:
            return self._backends[provider]
        backend: BatchBackend | None
        if kind is ProviderKind.ANTHROPIC:
            backend = AnthropicBatchBackend(client, provider)
        elif kind is ProviderKind.OPENAI:
            backend = OpenAIBatchBackend(client, provider)
        else:
            backend = self._vertex_backend(provider, client)
        if backend is not None:
            self._backends[provider] = backend
        return backend

    def _vertex_backend(self, provider: str, client: Any) -> BatchBackend | None:
        bucket = self._settings.google_gcs_bucket
        if not self._registry.uses_vertex(provider) or not bucket:
            if provider not in self._warned:
                self._warned.add(provider)
                logger.warning(
                    "%s batches need Vertex AI and [batch] google_gcs_bucket; "
                    "calling it online",
                    provider,
                )
            return None
        prefix = f"{bucket.rstrip('/')}/runs/{self._run_id}/batches"
        return VertexBatchBackend(
            client, provider, self._storage or GoogleCloudStorage(), prefix
        )
