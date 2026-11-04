"""Create the judge model that scores outputs the graders cannot check by rule."""

from collections.abc import Sequence

from evals.harness.credentials import missing_key_reason
from evals.models.judge_config import JudgeConfig
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.ports.llm import LLMPort


def judge_unavailable_reason(
    registry: ProviderRegistry, judge: JudgeConfig
) -> str | None:
    """Return why the judge cannot run (no API key), or None if it can.

    Raises:
        ConfigurationError: If mkcv does not know the judge's provider.
    """
    return missing_key_reason(registry, judge.provider)


def split_judges(
    registry: ProviderRegistry, panel: Sequence[JudgeConfig]
) -> tuple[list[JudgeConfig], dict[str, str]]:
    """Split ``panel`` into the judges that can run and why the others cannot.

    Returns:
        ``(runnable, skipped)``: runnable judges in panel order, and the
        reason for each skipped one by ``provider/model``.

    Raises:
        ConfigurationError: If mkcv does not know a judge's provider.
    """
    runnable: list[JudgeConfig] = []
    skipped: dict[str, str] = {}
    for judge in panel:
        reason = judge_unavailable_reason(registry, judge)
        if reason is None:
            runnable.append(judge)
        else:
            skipped[judge.label] = reason
    return runnable, skipped


def create_judge(registry: ProviderRegistry, judge: JudgeConfig) -> tuple[LLMPort, str]:
    """Return the judge's adapter and model name.

    The adapter comes from the provider registry, so the judge's own request
    rules (a model that rejects ``temperature``, say) apply to its calls.

    Raises:
        ConfigurationError: If the provider is unknown or has no API key (the
            registry would otherwise hand back an offline stub).
    """
    reason = judge_unavailable_reason(registry, judge)
    if reason is not None:
        raise ConfigurationError(f"Cannot use {judge.label} as the judge: {reason}")
    return registry.create_adapter(judge.provider), judge.model
