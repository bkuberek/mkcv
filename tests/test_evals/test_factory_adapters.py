"""Tests for handing prebuilt LLM adapters to the stage-config factories."""

from collections.abc import Callable
from pathlib import Path

from dynaconf import Dynaconf

from mkcv.adapters.factory import (
    create_cover_letter_service_for_stage_configs,
    create_pipeline_service_for_stage_configs,
)
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.stage_config import StageConfig
from tests.test_evals.conftest import COVER_LETTER

CONFIG = StageConfig(provider="anthropic", model="claude-opus-5-5", temperature=0.5)


async def test_the_cover_letter_service_uses_the_given_adapter(
    make_settings: Callable[..., Dynaconf], tmp_path: Path
) -> None:
    given = StubLLMAdapter(responses={CoverLetter: COVER_LETTER})
    service = create_cover_letter_service_for_stage_configs(
        make_settings(), {1: CONFIG, 2: CONFIG}, providers={"anthropic": given}
    )
    await service.generate_letter("JD", kb_text="KB", output_dir=tmp_path)
    assert [c["model"] for c in given.call_log] == ["claude-opus-5-5"]


def test_the_pipeline_service_uses_the_given_adapters(
    make_settings: Callable[..., Dynaconf],
) -> None:
    given = StubLLMAdapter()
    service = create_pipeline_service_for_stage_configs(
        make_settings(),
        dict.fromkeys(range(1, 6), CONFIG),
        providers={"anthropic": given},
    )
    assert service._providers == {"anthropic": given}
