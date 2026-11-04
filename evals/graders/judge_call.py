"""What the LLM-judge graders share: rubrics, the call, and the provenance."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from evals.graders.grading_context import GradingContext
from mkcv.core.exceptions.provider import ProviderError

RUBRICS_DIR = Path(__file__).parent / "rubrics"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 8192


def load_rubric(name: str) -> str:
    """Return the text of ``rubrics/<name>.md``."""
    return (RUBRICS_DIR / f"{name}.md").read_text(encoding="utf-8")


def has_judge(ctx: GradingContext) -> bool:
    """Return True if the context carries a judge and the model to ask."""
    return ctx.judge is not None and ctx.judge_model is not None


async def ask_judge[Judgement: BaseModel](
    ctx: GradingContext,
    *,
    rubric: str,
    user: str,
    response_model: type[Judgement],
) -> Judgement:
    """Send the rubric and the material to the judge and return its judgement.

    The request is deterministic (temperature 0.0); the judge's own adapter
    drops the temperature if its model rejects sampling settings.

    Raises:
        MkcvError: If the judge call fails (a provider error).
    """
    assert ctx.judge is not None
    assert ctx.judge_model is not None
    judgement = await ctx.judge.complete_structured(
        [
            {"role": "system", "content": rubric},
            {"role": "user", "content": user},
        ],
        model=ctx.judge_model,
        response_model=response_model,
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
    )
    if not isinstance(judgement, response_model):
        raise ProviderError(
            f"The judge returned {type(judgement).__name__}, "
            f"expected {response_model.__name__}"
        )
    return judgement


def judge_details(ctx: GradingContext) -> dict[str, Any]:
    """Return who judged and whether the evaluated model judged itself."""
    return {
        "judge": f"{ctx.judge_provider}/{ctx.judge_model}",
        "self_judged": ctx.judge_provider == ctx.evaluated_provider,
    }
