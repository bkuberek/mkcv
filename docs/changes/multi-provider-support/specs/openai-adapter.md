# Spec: OpenAI Adapter (Native Structured Outputs)

Design references: §7.2–§7.5, §5.5.

All scenarios patch `adapter._client.chat.completions.create` with an `AsyncMock` and inspect its call kwargs. "Valid JSON" means JSON that validates against the response model used in the test (a small test model with one required string, one defaulted string, one optional int, and one nested model list).

## REQ-OAI-1: Strict JSON-schema request

- **When** `complete_structured(messages, model="gpt-6.1-sol", response_model=M, temperature=0.3, max_tokens=4096)` is called, **then** the request has `response_format["type"] == "json_schema"`, `response_format["json_schema"]["strict"] is True`, `response_format["json_schema"]["name"] == "M"`, and `response_format["json_schema"]["schema"] == to_strict_json_schema(M)`.
- The request MUST NOT contain `temperature`.
- The request MUST contain `max_completion_tokens == 16000` and MUST NOT contain `max_tokens`.
- The system message content MUST be unchanged (no schema instruction appended).

## REQ-OAI-2: Models that accept sampling

- **When** `complete_structured(..., model="gpt-4o", temperature=0.3, max_tokens=4096)`, **then** the request contains `temperature == 0.3` and `max_completion_tokens == 4096`.

## REQ-OAI-3: Parsing and usage

- **Given** a response whose content is valid JSON and usage `prompt_tokens=100, completion_tokens=50`, **then** the result is an instance of `M` and `get_last_usage()` returns `TokenUsage(100, 50)`.
- **Given** valid JSON where the defaulted string field is `null`, **then** validation succeeds and the field holds its default.

## REQ-OAI-4: Refusal

- **Given** a response whose message has `refusal="I can't help with that"` and `content=None`, **then** `ProviderError` is raised with a message containing `Model refused the request`.

## REQ-OAI-5: Truncation

- **Given** `finish_reason == "length"`, **then** `ProviderError` is raised with a message containing `truncated` and `increase max_tokens`; no repair call is made.

## REQ-OAI-6: Repair retry

- **Given** a first response with content `not json` and a second response with valid JSON, **then** the result is valid, exactly two calls were made, the second call's messages end with an `assistant` message (`not json`) followed by a `user` message starting with `Your previous reply was not valid JSON`, and `get_last_usage()` is the sum of both calls.
- **Given** two invalid responses, **then** `mkcv.core.exceptions.ValidationError` is raised with a message containing `after one repair attempt`, and exactly two calls were made.

## REQ-OAI-7: No structured degradation for native OpenAI

- **Given** `create` raises `openai.BadRequestError` with message `Invalid schema for response_format 'M'`, **then** `ProviderError` is raised after exactly one call (no `json_object` attempt).

## REQ-OAI-8: Request adaptation

- **Given** `model="gpt-4o"` and the first call raises `openai.BadRequestError("Unsupported value: 'temperature' does not support 0.3 with this model.")`, **then** a second call is made without `temperature`, and it succeeds. A third structured call on the same adapter for `gpt-4o` omits `temperature` from the start.
- **Given** the first call raises `BadRequestError("Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.")` on a compatible-provider request that used `max_tokens`, **then** the retry uses `max_completion_tokens`.
- **Given** two consecutive rejections, **then** `ProviderError` is raised after two calls.

## REQ-OAI-9: Error mapping

| SDK error | Raised |
|---|---|
| `openai.RateLimitError` | `RateLimitError(provider="openai")` |
| `openai.AuthenticationError`, `openai.PermissionDeniedError` | `AuthenticationError` |
| `openai.BadRequestError` with `maximum context length` in the message | `ContextLengthError` |
| `openai.APIConnectionError` | `ProviderError` whose message contains `Cannot connect to openai` |
| other `openai.APIError` | `ProviderError` |

## REQ-OAI-10: Plain completion

- **When** `complete(messages, model="gpt-6-luna", temperature=0.5, max_tokens=1000)`, **then** the request has `max_completion_tokens == 16000`, no `temperature`, and no `response_format`; the return value is the message content (`""` when `None`).

## REQ-OAI-11: Strict schema transformer

- For every response model in design §7.5, `to_strict_json_schema(model)`:
  - contains no `$ref` and no `$defs`;
  - every object node has `additionalProperties: false` and `required` equal to its property names in order;
  - contains no key outside the whitelist of design §7.5 step 2;
  - has nesting depth ≤ 10 and ≤ 5000 properties in total;
  - has a root `type == "object"` without `anyOf`.
- **Given** a model with field `note: str = "x"`, **then** the strict schema types `note` as `["string", "null"]` and lists it in `required`.
- **Given** a field `count: int | None = None`, **then** its schema allows `null` exactly once (no duplicate null branch).
- **Given** a field with `Field(min_length=3)`, **then** `minLength` is absent from the strict schema.
