"""OpenAI LLM adapter with native strict structured outputs."""

from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel


class OpenAIAdapter(OpenAICompatibleAdapter):
    """LLM adapter for the OpenAI API (Chat Completions).

    Shares request shaping, refusal and truncation handling, error mapping,
    and repair with ``OpenAICompatibleAdapter``. What makes it "native" is
    configuration, not code: the ``openai`` provider kind forbids structured
    output degradation (strict JSON schema or an error), sends
    ``max_completion_tokens``, and omits ``temperature`` for models that
    reject it. A model the catalog does not know may still degrade from the
    strict schema to JSON mode, so an older model that rejects the schema
    keeps working; a catalogued model never does.

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

    def _may_degrade(self, resolved: ResolvedModel) -> bool:
        return resolved.allow_structured_fallback or not resolved.known
