"""Tests for the cover letter service hooks the harness runs one stage with."""

from collections.abc import Callable
from pathlib import Path

import pytest
from dynaconf import Dynaconf

from mkcv.adapters.factory import create_cover_letter_service_for_stage_configs
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.cover_letter import CoverLetterError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.cover_letter_review import CoverLetterReview
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.ports.llm import LLMPort
from mkcv.core.services.cover_letter import CoverLetterService
from tests.test_evals.conftest import COVER_LETTER, COVER_LETTER_REVIEW

CONFIGS = {
    1: StageConfig(provider="stub", model="writer", temperature=0.6),
    2: StageConfig(provider="stub", model="reviewer", temperature=0.2),
}


@pytest.fixture
def stub(install_adapter: Callable[[LLMPort], LLMPort]) -> StubLLMAdapter:
    adapter = StubLLMAdapter(
        responses={CoverLetter: COVER_LETTER, CoverLetterReview: COVER_LETTER_REVIEW}
    )
    install_adapter(adapter)
    return adapter


@pytest.fixture
def service(
    make_settings: Callable[..., Dynaconf], stub: StubLLMAdapter
) -> CoverLetterService:
    """The service, built after ``stub`` is installed so that it uses the stub."""
    return create_cover_letter_service_for_stage_configs(make_settings(), CONFIGS)


class TestGenerateLetter:
    async def test_it_writes_the_letter_with_one_call(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        letter, _ = await service.generate_letter(
            "JD text", kb_text="KB text", output_dir=tmp_path
        )
        assert letter == COVER_LETTER
        assert [c["response_model"] for c in stub.call_log] == ["CoverLetter"]

    async def test_it_uses_the_pinned_stage_one_model(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        _, metadata = await service.generate_letter(
            "JD text", kb_text="KB text", output_dir=tmp_path
        )
        assert (metadata.stage_number, metadata.model) == (1, "writer")
        assert stub.call_log[0]["model"] == "writer"

    async def test_the_prompt_carries_the_inputs(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        await service.generate_letter(
            "Needs Go.",
            kb_text="Wrote Go.",
            resume_text="cv: resume",
            company="Acme Corp",
            role_title="Platform Engineer",
            output_dir=tmp_path,
        )
        prompt = stub.call_log[0]["messages"][0]["content"]
        for text in ("Needs Go.", "Wrote Go.", "cv: resume", "Acme Corp"):
            assert text in prompt

    async def test_it_saves_the_letter_artifact(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        await service.generate_letter("JD", kb_text="KB", output_dir=tmp_path)
        assert (tmp_path / ".mkcv" / "cover_letter_content.json").is_file()

    async def test_it_does_not_review_or_render(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        await service.generate_letter("JD", kb_text="KB", output_dir=tmp_path)
        assert "CoverLetterReview" not in [c["response_model"] for c in stub.call_log]
        assert not (tmp_path / "cover_letter.pdf").exists()

    async def test_it_needs_a_knowledge_base_or_a_resume(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        with pytest.raises(CoverLetterError, match="resume_text or kb_text"):
            await service.generate_letter("JD", output_dir=tmp_path)


class TestReviewLetter:
    async def test_it_reviews_the_given_letter_with_one_call(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        review, metadata = await service.review_letter(
            COVER_LETTER, "JD text", output_dir=tmp_path
        )
        assert review == COVER_LETTER_REVIEW
        assert [c["response_model"] for c in stub.call_log] == ["CoverLetterReview"]
        assert (metadata.stage_number, metadata.model) == (2, "reviewer")

    async def test_the_prompt_carries_the_letter_and_the_jd(
        self, service: CoverLetterService, stub: StubLLMAdapter, tmp_path: Path
    ) -> None:
        await service.review_letter(COVER_LETTER, "Needs Go.", output_dir=tmp_path)
        prompt = stub.call_log[0]["messages"][0]["content"]
        assert "Needs Go." in prompt
        assert COVER_LETTER.opening_paragraph in prompt

    async def test_a_failing_review_raises_instead_of_being_skipped(
        self,
        make_settings: Callable[..., Dynaconf],
        install_adapter: Callable[[LLMPort], LLMPort],
        tmp_path: Path,
    ) -> None:
        install_adapter(StubLLMAdapter())
        service = create_cover_letter_service_for_stage_configs(
            make_settings(), CONFIGS
        )
        with pytest.raises(CoverLetterError):
            await service.review_letter(COVER_LETTER, "JD", output_dir=tmp_path)
