"""Everything a grader may look at when scoring one stage output."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evals.models.eval_case import EvalCase
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort


class GradingContext(BaseModel):
    """One output with its case, its inputs, and (for judges) the judge model.

    ``output`` is the parsed artifact for stages 1-3 and 5 and the YAML text
    for stage 4. ``reference`` maps the artifact names of the stages before
    this one (``stage1_analysis``, ...) to their reference contents.
    ``evaluated_provider`` and ``judge_provider`` let a judge grade say
    whether the model graded itself.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    case: EvalCase
    stage: StageKey
    kb_text: str
    jd_text: str
    output: dict[str, Any] | str | None
    reference: dict[str, Any] = Field(default_factory=dict)
    judge: LLMPort | None = None
    judge_model: str | None = None
    judge_provider: str | None = None
    evaluated_provider: str | None = None
