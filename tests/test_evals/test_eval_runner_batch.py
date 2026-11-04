"""The runner in batch mode: real adapters over a fake Message Batches client."""

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from anthropic.types import Message
from dynaconf import Dynaconf

from evals.batch.usage_ledger import read_usage
from evals.harness.case_loader import load_cases
from evals.harness.eval_runner import EvalRunner
from evals.models.batch_settings import BatchSettings
from evals.models.eval_case import EvalCase
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_settings import RunSettings
from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.batch_fakes import anthropic_message
from tests.test_evals.conftest import COVER_LETTER, RESUME_YAML
from tests.test_evals.grading_support import judging_stub

if TYPE_CHECKING:
    from pydantic import BaseModel

RUN_ID = "20261104-010203-abc1234"
JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
MODEL = MatrixModel(provider="anthropic", model="claude-sonnet-5-5")


class SchemaBatches:
    """``messages.batches`` that answers each request with the canned reply
    whose schema has the same required fields as the requested one."""

    def __init__(self) -> None:
        stub = judging_stub()
        self._canned: list[BaseModel] = [*stub._responses.values(), COVER_LETTER]
        self.created: list[list[dict[str, Any]]] = []

    async def create(self, *, requests: list[dict[str, Any]]) -> Any:
        self.created.append(requests)
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}")

    async def retrieve(self, batch_id: str) -> Any:
        return SimpleNamespace(processing_status="ended")

    async def results(self, batch_id: str) -> Any:
        requests = self.created[int(batch_id.rsplit("_", 1)[1]) - 1]

        async def items() -> Any:
            for request in requests:
                yield SimpleNamespace(
                    custom_id=request["custom_id"],
                    result=SimpleNamespace(
                        type="succeeded",
                        message=Message.model_validate(
                            anthropic_message(self._reply(request["params"]))
                        ),
                    ),
                )

        return items()

    def _reply(self, params: dict[str, Any]) -> str:
        if "output_config" not in params:
            return RESUME_YAML
        schema = params["output_config"]["format"]["schema"]
        wanted = set(schema.get("required", []))
        for model in self._canned:
            if set(type(model).model_json_schema().get("required", [])) == wanted:
                return model.model_dump_json()
        raise AssertionError(f"no canned reply for {sorted(wanted)}")


@pytest.fixture
def batches(monkeypatch: pytest.MonkeyPatch) -> SchemaBatches:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake = SchemaBatches()

    def create(self: ProviderRegistry, name: str, **_: object) -> LLMPort:
        adapter = AnthropicAdapter(api_key="test-key")
        adapter._client = SimpleNamespace(messages=SimpleNamespace(batches=fake))  # type: ignore[assignment]
        return adapter

    monkeypatch.setattr(ProviderRegistry, "create_adapter", create)
    return fake


@pytest.fixture
def case(tmp_fixtures: Path, add_reference: Callable[..., None]) -> EvalCase:
    found = load_cases(tmp_fixtures)[0]
    add_reference(found)
    return found


def _matrix() -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(stages=[StageKey.TAILOR]),
        judges=[JUDGE],
        reference=JUDGE,
        models=[MODEL],
        batch=BatchSettings(enabled=True, flush_seconds=0.0, poll_seconds=0.0),
    )


def _runner(
    make_settings: Callable[..., Dynaconf], tmp_path: Path, **options: Any
) -> EvalRunner:
    return EvalRunner(
        make_settings(), out_dir=tmp_path / "out", run_id=RUN_ID, **options
    )


async def test_stage_and_judge_calls_go_out_in_batches(
    make_settings: Callable[..., Dynaconf],
    tmp_path: Path,
    batches: SchemaBatches,
    case: EvalCase,
) -> None:
    [record] = await _runner(make_settings, tmp_path).run(_matrix(), [case])
    assert record.status == "ok"
    assert record.batched is True
    assert {g.name for g in record.grades} >= {"faithfulness_judge", "tailoring_judge"}
    sent = [r["params"]["model"] for group in batches.created for r in group]
    assert sent.count("claude-sonnet-5-5") == 1
    assert sent.count("claude-opus-5-5") == 2


async def test_every_call_is_in_the_usage_file(
    make_settings: Callable[..., Dynaconf],
    tmp_path: Path,
    batches: SchemaBatches,
    case: EvalCase,
) -> None:
    await _runner(make_settings, tmp_path).run(_matrix(), [case])
    usage = read_usage(tmp_path / "out" / "usage.jsonl")
    assert len(usage) == 3
    assert all(call.batched for call in usage)
    assert sum("/judge/" in (call.scope or "") for call in usage) == 2


async def test_a_resumed_run_does_not_submit_again(
    make_settings: Callable[..., Dynaconf],
    tmp_path: Path,
    batches: SchemaBatches,
    case: EvalCase,
) -> None:
    await _runner(make_settings, tmp_path).run(_matrix(), [case])
    out = tmp_path / "out"
    lines = (out / "results.jsonl").read_text().splitlines()
    (out / "results.jsonl").write_text("")  # as if interrupted before any record
    submitted = len(batches.created)
    [record] = await _runner(make_settings, tmp_path, resume=True).run(
        _matrix(), [case]
    )
    assert len(batches.created) == submitted
    assert json.loads(lines[0])["grades"] == [
        g.model_dump(mode="json") for g in record.grades
    ]


async def test_with_caching_the_judges_prefix_is_marked(
    make_settings: Callable[..., Dynaconf],
    tmp_path: Path,
    batches: SchemaBatches,
    case: EvalCase,
) -> None:
    from evals.models.caching_settings import CachingSettings

    matrix = _matrix().model_copy(update={"caching": CachingSettings(enabled=True)})
    await _runner(make_settings, tmp_path).run(matrix, [case])
    judged = [
        r["params"]
        for group in batches.created
        for r in group
        if r["params"]["model"] == "claude-opus-5-5"
    ]
    assert judged
    for params in judged:
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert params["messages"][0]["content"][0]["cache_control"]
        assert isinstance(params["messages"][-1]["content"], str)
