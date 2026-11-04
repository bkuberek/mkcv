"""Stand in for ``anthropic.AsyncAnthropic`` under the online adapter.

``AnthropicAdapter`` builds every request (sampling rules, output floors,
structured output) and parses every reply; this transport only decides how
a request travels: in a Message Batch or online, with the stable prompt
prefix marked for caching when asked. Repair and fallback calls the adapter
makes go through it again, so they land in the next batch.
"""

from types import TracebackType
from typing import Any, Self

from anthropic.types import Message

from evals.batch.call_recorder import CallRecorder

EPHEMERAL = {"type": "ephemeral"}
MAX_CACHE_BREAKPOINTS = 4


def mark_cacheable(params: dict[str, Any]) -> dict[str, Any]:
    """Return ``params`` with the system prompt and every message but the last cached.

    The last message holds what varies between calls (the output to judge);
    everything before it is the stable prefix. Anthropic takes at most four
    cache breakpoints, so at most three messages are marked after the system
    prompt. Text is left untouched, so the prefix stays byte-stable.
    """
    marked = dict(params)
    breakpoints = 0
    system = marked.get("system")
    if isinstance(system, str) and system:
        marked["system"] = [
            {"type": "text", "text": system, "cache_control": EPHEMERAL}
        ]
        breakpoints += 1
    messages = list(marked.get("messages", []))
    for index, message in enumerate(messages[:-1]):
        if breakpoints >= MAX_CACHE_BREAKPOINTS:
            break
        content = message.get("content")
        if isinstance(content, str) and content:
            messages[index] = {
                **message,
                "content": [
                    {"type": "text", "text": content, "cache_control": EPHEMERAL}
                ],
            }
            breakpoints += 1
    marked["messages"] = messages
    return marked


class AnthropicTransport:
    """The ``messages.stream`` the adapter uses, sent in batches or online."""

    def __init__(
        self, client: Any, recorder: CallRecorder, *, cache_prefix: bool = False
    ) -> None:
        self._client = client
        self._recorder = recorder
        self._cache_prefix = cache_prefix
        self.messages = _Messages(self)

    @property
    def client(self) -> Any:
        """The real SDK client (the batch backend uses it too)."""
        return self._client

    async def send(self, params: dict[str, Any]) -> Message:
        """Send one ``messages.create`` request and return the message."""
        request = mark_cacheable(params) if self._cache_prefix else params
        model = str(request["model"])
        queue = self._recorder.queue_for(model)
        if queue is not None:
            message = Message.model_validate(
                await self._recorder.batched(queue, request)
            )
        else:
            self._recorder.online()
            async with self._client.messages.stream(**request) as stream:
                message = await stream.get_final_message()
        usage = message.usage
        read = usage.cache_read_input_tokens or 0
        written = usage.cache_creation_input_tokens or 0
        self._recorder.record(
            model,
            batched=queue is not None,
            input_tokens=usage.input_tokens + read + written,
            output_tokens=usage.output_tokens,
            cache_read_tokens=read,
            cache_write_tokens=written,
        )
        return message


class _Messages:
    def __init__(self, transport: AnthropicTransport) -> None:
        self._transport = transport

    def stream(self, **params: Any) -> "_Stream":
        return _Stream(self._transport, params)


class _Stream:
    """An async context like the SDK's stream; it yields no events.

    The adapter falls back to the final message when the stream gave it no
    tool-input fragments, which is the path every reply takes here.
    """

    def __init__(self, transport: AnthropicTransport, params: dict[str, Any]) -> None:
        self._transport = transport
        self._params = params

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        return None

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Any:
        raise StopAsyncIteration

    async def get_final_message(self) -> Message:
        return await self._transport.send(self._params)
