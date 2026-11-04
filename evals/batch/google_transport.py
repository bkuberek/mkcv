"""Stand in for ``google.genai.Client`` under the online adapter.

``GoogleGeminiAdapter`` builds the ``generate_content`` request (schema,
token floor, sampling rules) and parses the reply; this transport sends it
in a Vertex AI batch or online and records its tokens. Gemini caches long
prompt prefixes on its own, so nothing is marked.
"""

from typing import Any

from google.genai import types

from evals.batch.call_recorder import CallRecorder

_SUPPORTED_CONFIG = frozenset(
    {
        "system_instruction",
        "max_output_tokens",
        "temperature",
        "response_mime_type",
        "response_json_schema",
    }
)
_REST_NAMES = {
    "max_output_tokens": "maxOutputTokens",
    "temperature": "temperature",
    "response_mime_type": "responseMimeType",
    "response_json_schema": "responseJsonSchema",
}


def vertex_request(request: dict[str, Any]) -> dict[str, Any]:
    """Return the REST body of a ``generate_content`` request for a batch file.

    Raises:
        ValueError: If the request sets a config field this conversion does
            not carry, so a batch never silently drops part of a request.
    """
    config: types.GenerateContentConfig = request["config"]
    unsupported = sorted(
        name
        for name, value in config
        if value is not None and name not in _SUPPORTED_CONFIG
    )
    if unsupported:
        raise ValueError(f"cannot batch config fields: {', '.join(unsupported)}")
    body: dict[str, Any] = {
        "contents": [
            content.model_dump(mode="json", by_alias=True, exclude_none=True)
            for content in request["contents"]
        ]
    }
    system = config.system_instruction
    if isinstance(system, str) and system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    generation = {
        rest: getattr(config, name)
        for name, rest in _REST_NAMES.items()
        if getattr(config, name) is not None
    }
    if generation:
        body["generationConfig"] = generation
    return body


class GoogleTransport:
    """The ``aio.models.generate_content`` the adapter uses."""

    def __init__(self, client: Any, recorder: CallRecorder) -> None:
        self._client = client
        self._recorder = recorder
        self.aio = _Aio(self)

    @property
    def client(self) -> Any:
        """The real SDK client (the batch backend uses it too)."""
        return self._client

    async def send(self, request: dict[str, Any]) -> types.GenerateContentResponse:
        """Send one request and return the response."""
        model = str(request["model"])
        queue = self._recorder.queue_for(model)
        if queue is not None:
            response = types.GenerateContentResponse.model_validate(
                await self._recorder.batched(queue, vertex_request(request))
            )
        else:
            self._recorder.online()
            response = await self._client.aio.models.generate_content(**request)
        metadata = response.usage_metadata
        output = 0
        if metadata is not None:
            output = (metadata.candidates_token_count or 0) + (
                metadata.thoughts_token_count or 0
            )
        self._recorder.record(
            model,
            batched=queue is not None,
            input_tokens=(metadata.prompt_token_count or 0) if metadata else 0,
            output_tokens=output,
            cache_read_tokens=(metadata.cached_content_token_count or 0)
            if metadata
            else 0,
        )
        return response


class _Aio:
    def __init__(self, transport: GoogleTransport) -> None:
        self.models = _Models(transport)


class _Models:
    def __init__(self, transport: GoogleTransport) -> None:
        self._transport = transport

    async def generate_content(self, **request: Any) -> types.GenerateContentResponse:
        return await self._transport.send(request)
