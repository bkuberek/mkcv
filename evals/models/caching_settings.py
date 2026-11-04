"""Prompt caching of the judges' stable prefix: ``[caching]``."""

from pydantic import BaseModel, ConfigDict, Field


class CachingSettings(BaseModel):
    """Whether to mark the judges' stable prompt prefix, and how to plan for it.

    Judge requests put what every output of a case shares first (the
    rubric, the job description, the knowledge base); ``enabled`` marks it
    for Anthropic's prompt cache. OpenAI and Gemini cache such a prefix on
    their own. The estimate assumes the prefix is ``judge_prefix_share`` of
    a judge call's input and that ``estimated_hit_rate`` of the calls that
    could reuse a cached prefix do (batched requests hit the cache on a
    best-effort basis). Stage prompts are mkcv's own templates and are not
    split, so they are not cached.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    judge_prefix_share: float = Field(default=0.7, ge=0.0, le=1.0)
    estimated_hit_rate: float = Field(default=0.5, ge=0.0, le=1.0)
