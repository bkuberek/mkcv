# Spec: Google Gemini Adapter

Design references: §7.6, §5.2, §12.2.

Scenarios construct `GoogleGeminiAdapter(api_key="g", resolver=...)` and replace `adapter._client.aio.models.generate_content` with an `AsyncMock` returning a `types.GenerateContentResponse` (or an equivalent `SimpleNamespace` with `text`, `usage_metadata`, `candidates`, `prompt_feedback`).

## REQ-GG-1: Structured request shape

- **When** `complete_structured(messages, model="gemini-3.8-flash", response_model=M, temperature=0.3, max_tokens=4096)` is called with a system message and a user message, **then** the call has `model="gemini-3.8-flash"`, `contents` with one item of role `user`, and `config` with:
  - `system_instruction` equal to the system message text;
  - `response_mime_type == "application/json"`;
  - `response_json_schema == resolve_schema_refs(M.model_json_schema())`;
  - `max_output_tokens == 16000`;
  - `temperature is None`.

## REQ-GG-2: Role mapping

- **Given** messages `system`, `user`, `assistant`, `user`, **then** `contents` roles are `user`, `model`, `user`, and the system text is in `system_instruction` only.
- **Given** two system messages, **then** `system_instruction` is their texts joined by a blank line.

## REQ-GG-3: Parsing and usage

- **Given** `text` is valid JSON and `usage_metadata` has `prompt_token_count=120`, `candidates_token_count=40`, `thoughts_token_count=300`, **then** the result validates and `get_last_usage()` is `TokenUsage(120, 340)`.
- **Given** `thoughts_token_count=None`, **then** output tokens equal `candidates_token_count`.

## REQ-GG-4: Empty or blocked responses

- **Given** empty `text` and `prompt_feedback.block_reason == "SAFETY"`, **then** `ProviderError` contains `Gemini blocked the prompt`.
- **Given** empty `text` and the first candidate's `finish_reason == "MAX_TOKENS"`, **then** `ProviderError` contains `truncated`.
- **Given** empty `text` and no other signal, **then** `ProviderError` contains `Gemini returned no text`.

## REQ-GG-5: Repair retry

- **Given** a first response with text `nope` and a second with valid JSON, **then** two calls are made, the second call's `contents` end with a `model` turn (`nope`) and a `user` turn starting with `Your previous reply was not valid JSON`, and the result validates.
- **Given** two invalid responses, **then** `ValidationError` is raised.

## REQ-GG-6: Plain completion

- **When** `complete(messages, model="gemini-4-argon", ...)` is called, **then** `config.response_mime_type` and `config.response_json_schema` are unset and the return value is `response.text`.

## REQ-GG-7: Error mapping

| SDK error | Raised |
|---|---|
| `errors.ClientError` code 429 | `RateLimitError(provider="google")` |
| `errors.ClientError` code 401 or 403 | `AuthenticationError` |
| `errors.ClientError` code 400 whose message contains `token` or `context` | `ContextLengthError` |
| `errors.ClientError` code 400, other message | `ProviderError` |
| `errors.ServerError` | `ProviderError` |

## REQ-GG-8: Request adaptation

- **Given** a catalog entry overlay that sets `accepts_sampling_params=True` for the model, and the first call raises `errors.ClientError` 400 with a message naming `temperature` as unsupported, **then** a second call is made with `temperature is None`.

## REQ-GG-9: Registry wiring

- **Given** `GEMINI_API_KEY=g`, **when** `registry.create_adapter("google", with_retry=False)`, **then** a `GoogleGeminiAdapter` is returned.
- **Given** `[default.providers.google] base_url = "https://proxy.example.com"`, **then** the adapter's client is created with `http_options.base_url == "https://proxy.example.com"`.
- Importing `mkcv.adapters.factory` MUST NOT import `google.genai` (lazy import). Test: run `python -c "import sys, mkcv.adapters.factory; assert 'google.genai' not in sys.modules"` in a subprocess.

## REQ-GG-10: Dependency

- `pyproject.toml` lists `google-genai>=2.34.0` in `[project] dependencies`, and `uv.lock` resolves it.
