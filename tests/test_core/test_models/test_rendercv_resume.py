"""Tests for RenderCVResume model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.rendercv_resume import RenderCVResume
from mkcv.core.models.resume_cv import ResumeCV
from mkcv.core.models.resume_design import ResumeDesign


def _make_cv() -> ResumeCV:
    return ResumeCV(
        name="John Doe",
        location="San Francisco, CA",
        email="john@example.com",
        phone="+1-555-0123",
        summary="Experienced platform engineer",
        sections={"experience": [{"company": "Acme"}]},
    )


class TestRenderCVResume:
    """Tests for RenderCVResume model."""

    def test_valid_creation(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        assert resume.cv.name == "John Doe"

    def test_design_defaults_to_resume_design(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        assert resume.design.theme == "sb2nov"

    def test_design_default_font(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        assert resume.design.font == "SourceSansPro"

    def test_custom_design(self) -> None:
        design = ResumeDesign(theme="classic", font="Arial")
        resume = RenderCVResume(cv=_make_cv(), design=design)
        assert resume.design.theme == "classic"

    def test_custom_design_font(self) -> None:
        design = ResumeDesign(theme="modern", font="Helvetica")
        resume = RenderCVResume(cv=_make_cv(), design=design)
        assert resume.design.font == "Helvetica"

    def test_cv_required(self) -> None:
        with pytest.raises(ValidationError):
            RenderCVResume()  # type: ignore[call-arg]

    def test_model_dump_includes_cv_and_design(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        data = resume.model_dump()
        assert set(data.keys()) == {"cv", "design"}

    def test_model_dump_cv_has_name(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        data = resume.model_dump()
        assert data["cv"]["name"] == "John Doe"

    def test_model_dump_design_has_theme(self) -> None:
        resume = RenderCVResume(cv=_make_cv())
        data = resume.model_dump()
        assert data["design"]["theme"] == "sb2nov"
