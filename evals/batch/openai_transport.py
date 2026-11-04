"""Stand in for ``openai.AsyncOpenAI`` under the online adapter.

``OpenAICompatibleAdapter`` builds the ``chat.completions.create`` request
(strict JSON schema, sampling and token rules) and parses the reply; this
transport sends it in a batch or online and records its tokens. OpenAI
caches long prompt prefixes on its own, so nothing is marked.
"""

from typing import Any

from openai.types.chat import ChatCompletion

from evals.batch.call_recorder import CallRecorder


class OpenAITransport:
    """The ``chat.completions.create`` the adapter uses."""

    def __init__(self, client: Any, recorder: CallRecorder) -> None:
        self._client = client
        self._recorder = recorder
        self.chat = _Chat(self)

    @property
    def client(self) -> Any:
        """The real SDK client (the batch backend uses it too)."""
        return self._client

    @property
    def base_url(self) -> Any:
        """The endpoint, as the adapter reports it in connection errors."""
        return self._client.base_url

    async def send(self, params: dict[str, Any]) -> ChatCompletion:
        """Send one request and return the completion."""
        model = str(params["model"])
        queue = self._recorder.queue_for(model)
        if queue is not None:
            completion = ChatCompletion.model_validate(
                await self._recorder.batched(queue, params)
            )
        else:
            self._recorder.online()
            completion = await self._client.chat.completions.create(**params)
        usage = completion.usage
        details = usage.prompt_tokens_details if usage is not None else None
        self._recorder.record(
            model,
            batched=queue is not None,
            input_tokens=usage.prompt_tokens if usage is not None else 0,
            output_tokens=usage.completion_tokens if usage is not None else 0,
            cache_read_tokens=(details.cached_tokens or 0) if details else 0,
        )
        return completion


class _Chat:
    def __init__(self, transport: OpenAITransport) -> None:
        self.completions = _Completions(transport)


class _Completions:
    def __init__(self, transport: OpenAITransport) -> None:
        self._transport = transport

    async def create(self, **params: Any) -> ChatCompletion:
        return await self._transport.send(params)
