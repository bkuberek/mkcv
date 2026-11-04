"""OpenAI LLM adapter with native strict structured outputs."""

from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter
from mkcv.core.models.provider_kind import ProviderKind


class OpenAIAdapter(OpenAICompatibleAdapter):
    """LLM adapter for the OpenAI API (Chat Completions).

    Shares request shaping, refusal and truncation handling, error mapping,
    and repair with ``OpenAICompatibleAdapter``. What makes it "native" is
    configuration, not code: the ``openai`` provider kind forbids structured
    output degradation (strict JSON schema or an error), sends
    ``max_completion_tokens``, and omits ``temperature`` for models that
    reject it.

    Implements: LLMPort
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        resolver: ModelResolver | None = None,
        provider_name: str = "openai",
    ) -> None:
        super().__init__(
            api_key,
            base_url=base_url,
            resolver=resolver or builtin_resolver(ProviderKind.OPENAI),
            provider_name=provider_name,
        )
