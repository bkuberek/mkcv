"""Tests for RegenerationService."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.earlier_experience_section import EarlierExperienceSection
from mkcv.core.models.languages_section import LanguagesSection
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.regeneration_context import RegenerationContext
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.skills_section import SkillsSection
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole
from mkcv.core.services.regeneration import RegenerationService

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_bullet(text: str = "Built a widget") -> TailoredBullet:
    return TailoredBullet(
        original=text,
        rewritten=text,
        keywords_incorporated=["Python"],
        confidence="high",
    )


def _make_role(
    company: str = "Acme Corp",
    position: str = "Senior Engineer",
) -> TailoredRole:
    return TailoredRole(
        company=company,
        position=position,
        start_date="2020-01",
        end_date="2023-06",
        bullets=[_make_bullet("Led migration"), _make_bullet("Reduced deploy time")],
        summary="Platform engineering lead",
        tech_stack="Python, AWS, Docker",
    )


def _make_content() -> TailoredContent:
    return TailoredContent(
        mission=MissionStatement(
            text="Experienced engineer specializing in cloud infrastructure.",
            rationale="Matches the JD emphasis on cloud.",
        ),
        skills=[
            SkillGroup(label="Languages", skills=["Python", "Go"]),
            SkillGroup(label="Cloud", skills=["AWS", "GCP"]),
        ],
        roles=[_make_role(), _make_role(company="OtherCo", position="Developer")],
        earlier_experience="Junior developer at StartupX (2015-2018).",
        languages=["English", "Spanish"],
    )


def _make_context() -> RegenerationContext:
    return RegenerationContext(
        jd_analysis={
            "company": "TestCorp",
            "role_title": "Senior Software Engineer",
            "ats_keywords": ["Python", "AWS"],
        },
        ats_keywords=["Python", "AWS", "CI/CD"],
        kb_text="# Career Knowledge Base\n\nExperienced engineer...",
    )


def _make_mock_llm() -> MagicMock:
    """Create a mock LLMPort."""
    llm = MagicMock()
    llm.complete_structured = AsyncMock()
    llm.get_last_usage = MagicMock(return_value=None)
    return llm


def _make_mock_prompts() -> MagicMock:
    """Create a mock PromptLoaderPort."""
    prompts = MagicMock()
    prompts.render = MagicMock(return_value="<rendered prompt>")
    return prompts


def _make_service(
    llm: MagicMock | None = None,
    prompts: MagicMock | None = None,
) -> tuple[RegenerationService, MagicMock, MagicMock]:
    """Create a RegenerationService with mock dependencies.

    Returns:
        Tuple of (service, mock_llm, mock_prompts).
    """
    mock_llm = llm or _make_mock_llm()
    mock_prompts = prompts or _make_mock_prompts()
    service = RegenerationService(
        llm=mock_llm,
        prompts=mock_prompts,
        model="test-model",
        temperature=0.5,
    )
    return service, mock_llm, mock_prompts


# ------------------------------------------------------------------
# Tests: regenerate each section type
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_mission_returns_updated_content() -> None:
    """Regenerating mission replaces mission in returned content."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_mission = MissionStatement(
        text="Cloud infrastructure expert with 8 years of experience.",
        rationale="Emphasizes cloud as requested.",
    )
    mock_llm.complete_structured.return_value = new_mission

    result = await service.regenerate_section(
        content=content,
        section_type="mission",
        instructions=["make it shorter"],
        context=context,
    )

    assert result.mission.text == new_mission.text
    assert result.mission.rationale == new_mission.rationale


@pytest.mark.asyncio
async def test_regenerate_skills_returns_updated_content() -> None:
    """Regenerating skills replaces skills list in returned content."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_skills = SkillsSection(
        skills=[
            SkillGroup(label="Programming", skills=["Python", "Go", "Rust"]),
        ]
    )
    mock_llm.complete_structured.return_value = new_skills

    result = await service.regenerate_section(
        content=content,
        section_type="skills",
        instructions=["add Rust"],
        context=context,
    )

    assert len(result.skills) == 1
    assert result.skills[0].label == "Programming"
    assert "Rust" in result.skills[0].skills


@pytest.mark.asyncio
async def test_regenerate_experience_returns_updated_content() -> None:
    """Regenerating experience replaces the targeted role."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_role = TailoredRole(
        company="Acme Corp",
        position="Principal Engineer",
        start_date="2020-01",
        end_date="2023-06",
        bullets=[_make_bullet("Led platform migration to Kubernetes")],
        summary="Led platform engineering team",
        tech_stack="Python, Kubernetes, AWS",
    )
    mock_llm.complete_structured.return_value = new_role

    result = await service.regenerate_section(
        content=content,
        section_type="experience",
        instructions=["emphasize Kubernetes"],
        context=context,
        role_index=0,
    )

    assert result.roles[0].position == "Principal Engineer"
    assert result.roles[0].bullets[0].rewritten == (
        "Led platform migration to Kubernetes"
    )
    # Second role unchanged
    assert result.roles[1].company == "OtherCo"


@pytest.mark.asyncio
async def test_regenerate_earlier_experience_returns_updated_content() -> None:
    """Regenerating earlier experience replaces the text."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_ee = EarlierExperienceSection(
        earlier_experience="Senior Dev at StartupX (2015-2018), Intern at BigCo (2014)."
    )
    mock_llm.complete_structured.return_value = new_ee

    result = await service.regenerate_section(
        content=content,
        section_type="earlier_experience",
        instructions=["add the BigCo internship"],
        context=context,
    )

    assert result.earlier_experience == new_ee.earlier_experience


@pytest.mark.asyncio
async def test_regenerate_languages_returns_updated_content() -> None:
    """Regenerating languages replaces the language list."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_languages = LanguagesSection(
        languages=["English (Native)", "Spanish (Proficient)", "French (Basic)"]
    )
    mock_llm.complete_structured.return_value = new_languages

    result = await service.regenerate_section(
        content=content,
        section_type="languages",
        instructions=["add French"],
        context=context,
    )

    assert result.languages == [
        "English (Native)",
        "Spanish (Proficient)",
        "French (Basic)",
    ]


# ------------------------------------------------------------------
# Tests: prompt building
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_includes_all_instructions() -> None:
    """All accumulated instructions are passed to the prompt template."""
    service, mock_llm, mock_prompts = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = MissionStatement(
        text="Updated", rationale="Updated"
    )

    instructions = ["make it shorter", "emphasize cloud", "add AWS mention"]

    await service.regenerate_section(
        content=content,
        section_type="mission",
        instructions=instructions,
        context=context,
    )

    render_call = mock_prompts.render.call_args
    template_name = render_call[0][0]
    template_context: dict[str, Any] = render_call[0][1]

    assert template_name == "regenerate_section.j2"
    assert template_context["instructions"] == instructions


@pytest.mark.asyncio
async def test_prompt_includes_current_section_content() -> None:
    """The current section content is included in the prompt context."""
    service, mock_llm, mock_prompts = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = MissionStatement(
        text="Updated", rationale="Updated"
    )

    await service.regenerate_section(
        content=content,
        section_type="mission",
        instructions=["tweak it"],
        context=context,
    )

    render_call = mock_prompts.render.call_args
    template_context: dict[str, Any] = render_call[0][1]

    assert template_context["current_content"] == content.mission.model_dump()
    assert template_context["section_type"] == "mission"


@pytest.mark.asyncio
async def test_prompt_includes_context_fields() -> None:
    """JD analysis, ATS keywords, and KB text are included in the prompt."""
    service, mock_llm, mock_prompts = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = MissionStatement(
        text="Updated", rationale="Updated"
    )

    await service.regenerate_section(
        content=content,
        section_type="mission",
        instructions=["tweak"],
        context=context,
    )

    render_call = mock_prompts.render.call_args
    template_context: dict[str, Any] = render_call[0][1]

    assert template_context["jd_analysis"] == context.jd_analysis
    assert template_context["ats_keywords"] == context.ats_keywords
    assert template_context["kb_text"] == context.kb_text


# ------------------------------------------------------------------
# Tests: other sections unchanged
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_sections_unchanged_after_mission_regen() -> None:
    """Regenerating mission does not affect skills, roles, or other fields."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = MissionStatement(
        text="New mission", rationale="New rationale"
    )

    result = await service.regenerate_section(
        content=content,
        section_type="mission",
        instructions=["change it"],
        context=context,
    )

    # Mission changed
    assert result.mission.text == "New mission"
    # Everything else preserved
    assert result.skills == content.skills
    assert result.roles == content.roles
    assert result.earlier_experience == content.earlier_experience
    assert result.languages == content.languages
    assert result.low_confidence_flags == content.low_confidence_flags


# ------------------------------------------------------------------
# Tests: error handling
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_section_type_raises_pipeline_stage_error() -> None:
    """An unknown section type raises PipelineStageError."""
    service, _, _ = _make_service()
    content = _make_content()
    context = _make_context()

    with pytest.raises(PipelineStageError, match="Unknown section type"):
        await service.regenerate_section(
            content=content,
            section_type="nonexistent",
            instructions=["do something"],
            context=context,
        )


@pytest.mark.asyncio
async def test_llm_error_propagates_as_pipeline_stage_error() -> None:
    """An LLM exception is wrapped in PipelineStageError."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.side_effect = RuntimeError("LLM connection failed")

    with pytest.raises(PipelineStageError, match="Regeneration failed"):
        await service.regenerate_section(
            content=content,
            section_type="mission",
            instructions=["fix it"],
            context=context,
        )


@pytest.mark.asyncio
async def test_pipeline_stage_error_propagates_directly() -> None:
    """A PipelineStageError from the LLM is re-raised without wrapping."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    original_error = PipelineStageError(
        "Provider unavailable", stage="llm", stage_number=0
    )
    mock_llm.complete_structured.side_effect = original_error

    with pytest.raises(PipelineStageError, match="Provider unavailable"):
        await service.regenerate_section(
            content=content,
            section_type="mission",
            instructions=["fix it"],
            context=context,
        )


# ------------------------------------------------------------------
# Tests: experience with role_index
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experience_uses_role_index() -> None:
    """The correct role is replaced when role_index is specified."""
    service, mock_llm, _ = _make_service()
    content = _make_content()
    context = _make_context()

    new_role = TailoredRole(
        company="OtherCo",
        position="Staff Developer",
        start_date="2018-03",
        end_date="2020-01",
        bullets=[_make_bullet("Redesigned core API")],
    )
    mock_llm.complete_structured.return_value = new_role

    result = await service.regenerate_section(
        content=content,
        section_type="experience",
        instructions=["emphasize API work"],
        context=context,
        role_index=1,
    )

    # Role at index 1 updated
    assert result.roles[1].position == "Staff Developer"
    # Role at index 0 unchanged
    assert result.roles[0].company == "Acme Corp"


@pytest.mark.asyncio
async def test_experience_without_role_index_raises_value_error() -> None:
    """Regenerating experience without role_index raises ValueError."""
    service, _, _ = _make_service()
    content = _make_content()
    context = _make_context()

    with pytest.raises(ValueError, match="role_index is required"):
        await service.regenerate_section(
            content=content,
            section_type="experience",
            instructions=["fix"],
            context=context,
        )


@pytest.mark.asyncio
async def test_experience_with_out_of_range_role_index_raises_value_error() -> None:
    """Regenerating experience with out-of-range role_index raises ValueError."""
    service, _, _ = _make_service()
    content = _make_content()
    context = _make_context()

    with pytest.raises(ValueError, match="role_index 5 out of range"):
        await service.regenerate_section(
            content=content,
            section_type="experience",
            instructions=["fix"],
            context=context,
            role_index=5,
        )


# ------------------------------------------------------------------
# Tests: LLM is called with correct model/temperature/max_tokens
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_called_with_configured_model_and_temperature() -> None:
    """The LLM is called with the model and temperature from the service."""
    mock_llm = _make_mock_llm()
    mock_prompts = _make_mock_prompts()
    service = RegenerationService(
        llm=mock_llm,
        prompts=mock_prompts,
        model="claude-sonnet-4-20250514",
        temperature=0.7,
        max_tokens=2048,
    )

    mock_llm.complete_structured.return_value = MissionStatement(
        text="Test", rationale="Test"
    )

    await service.regenerate_section(
        content=_make_content(),
        section_type="mission",
        instructions=["test"],
        context=_make_context(),
    )

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs.kwargs["temperature"] == 0.7
    assert call_kwargs.kwargs["max_tokens"] == 2048


# ------------------------------------------------------------------
# Tests: prompt template rendering for each section type
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skills_prompt_contains_current_skills() -> None:
    """Skills regeneration passes current skills to the template."""
    service, mock_llm, mock_prompts = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = SkillsSection(
        skills=[SkillGroup(label="Test", skills=["Python"])]
    )

    await service.regenerate_section(
        content=content,
        section_type="skills",
        instructions=["reorder"],
        context=context,
    )

    render_call = mock_prompts.render.call_args
    template_context: dict[str, Any] = render_call[0][1]
    assert template_context["current_content"] == [
        sg.model_dump() for sg in content.skills
    ]


@pytest.mark.asyncio
async def test_experience_prompt_contains_role_data() -> None:
    """Experience regeneration passes the targeted role to the template."""
    service, mock_llm, mock_prompts = _make_service()
    content = _make_content()
    context = _make_context()

    mock_llm.complete_structured.return_value = content.roles[0]

    await service.regenerate_section(
        content=content,
        section_type="experience",
        instructions=["tweak"],
        context=context,
        role_index=0,
    )

    render_call = mock_prompts.render.call_args
    template_context: dict[str, Any] = render_call[0][1]
    assert template_context["current_content"] == content.roles[0].model_dump()
    assert template_context["role_index"] == 0
