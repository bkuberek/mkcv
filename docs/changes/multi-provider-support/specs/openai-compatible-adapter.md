# Spec: OpenAI-Compatible Adapter and Structured-Output Fallback Chain

Design references: §7.2, §7.4, §5.2 (kind and provider defaults), §5.5.

Scenarios construct `OpenAICompatibleAdapter(api_key="k", base_url="http://localhost:9999/v1", resolver=..., provider_name="local-test")` with a resolver built from a test catalog and `KIND_DEFAULTS[OPENAI_COMPATIBLE]`, and patch `_client.chat.completions.create`.

## REQ-OC-1: Chain starts at JSON schema for unknown models

- **Given** an unknown model and a response with valid JSON, **when** `complete_structured` runs, **then** exactly one call is made, with `response_format["type"] == "json_schema"`, `temperature` present, and `max_tokens` (not `max_completion_tokens`) equal to the requested value.

## REQ-OC-2: Degrade to JSON object

- **Given** the first call raises `openai.BadRequestError("response_format json_schema is not supported by this backend")` and the second returns valid JSON, **then** two calls are made; the second has `response_format == {"type": "json_object"}` and its system message ends with the schema instruction from `build_schema_prompt`.
- A warning is logged containing `falling back to json_object`.
- **When** `complete_structured` runs again for the same model on the same adapter instance, **then** the first call already uses `json_object`.

## REQ-OC-3: Degrade to prompt-only

- **Given** rejections for `json_schema` and for `json_object` (`BadRequestError("response_format is not supported")` twice), and a third response with JSON inside a ```json fence, **then** three calls are made, the third has no `response_format`, includes the schema instruction, and the result validates.

## REQ-OC-4: No degradation past the last mode

- **Given** the start mode is `prompt` (catalog entry `structured_output = "prompt"`) and the call raises a `response_format` rejection, **then** `ProviderError` is raised after one call.

## REQ-OC-5: Provider default `json_object` (Ollama)

- **Given** the registry's `ollama` provider and model `llama3.1:8b`, **when** `complete_structured` runs, **then** the first call uses `response_format == {"type": "json_object"}` with the schema instruction (today's Ollama behaviour), `temperature` is sent, and `max_tokens` is sent.
- **Given** no system message in the input, **then** a system message `You are a helpful assistant.` + schema instruction is prepended.

## REQ-OC-6: Repair retry in every mode

- **Given** start mode `json_object`, a first response `{"wrong": 1}` and a second valid response, **then** the result validates after two calls and the second call's last message is the repair prompt.
- **Given** two invalid responses, **then** `ValidationError` is raised.

## REQ-OC-7: Parameter adaptation precedes degradation

- **Given** the first call raises `BadRequestError("temperature is not supported for this model")`, **then** the retry keeps `response_format["type"] == "json_schema"` and drops `temperature`.

## REQ-OC-8: Connection errors

- **Given** `create` raises `openai.APIConnectionError`, **then** `ProviderError` is raised whose message contains `Cannot connect to local-test at http://localhost:9999/v1`.

## REQ-OC-9: Provider label in errors

- Every `ProviderError`, `RateLimitError`, `AuthenticationError`, and `ContextLengthError` raised by the adapter MUST carry `provider == "local-test"` (the adapter's `provider_name`).

## REQ-OC-10: Backward compatibility of names

- **Given** a config with `[default.pipeline.stages.analyze] provider = "ollama"`, `model = "llama3.1:8b"`, **when** `create_pipeline_service` runs, **then** the analyze stage's adapter is (or wraps) an `OpenAICompatibleAdapter` whose client `base_url` starts with `http://localhost:11434/v1`.
- **Given** `[default.pipeline.stages.analyze] provider = "openrouter"`, `model = "openai/gpt-4o"`, and `OPENROUTER_API_KEY=k`, **then** the adapter's client `base_url` starts with `https://openrouter.ai/api/v1`.
- `src/mkcv/adapters/llm/ollama.py` MUST no longer exist.
