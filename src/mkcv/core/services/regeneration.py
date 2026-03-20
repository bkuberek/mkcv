"""Section regeneration service for interactive resume editing."""

import logging
from typing import cast

from pydantic import BaseModel

from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.earlier_experience_section import EarlierExperienceSection
from mkcv.core.models.languages_section import LanguagesSection
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.regeneration_context import RegenerationContext
from mkcv.core.models.skills_section import SkillsSection
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort

logger = logging.getLogger(__name__)

# Maps section_type strings to their corresponding response models.
_SECTION_MODELS: dict[str, type[BaseModel]] = {
    "mission": MissionStatement,
    "skills": SkillsSection,
    "experience": TailoredRole,
    "earlier_experience": EarlierExperienceSection,
    "languages": LanguagesSection,
}

_VALID_SECTION_TYPES = frozenset(_SECTION_MODELS.keys())

DEFAULT_MAX_TOKENS = 4096


class RegenerationService:
    """Regenerates individual resume sections via LLM based on user feedback.

    Accepts a ``TailoredContent``, a section identifier (string), accumulated
    user instructions, and pipeline context, then invokes the LLM to produce
    a regenerated version of that specific section.  Returns a new
    ``TailoredContent`` with only the targeted section replaced.

    Depends only on ``LLMPort`` and ``PromptLoaderPort`` protocols —
    never on concrete adapters — following the hexagonal architecture.
    """

    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        model: str,
        temperature: float = 0.5,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def regenerate_section(
        self,
        content: TailoredContent,
        section_type: str,
        instructions: list[str],
        context: RegenerationContext,
        *,
        role_index: int | None = None,
    ) -> TailoredContent:
        """Regenerate a single section and return updated content.

        Args:
            content: The current full tailored content.
            section_type: One of ``"mission"``, ``"skills"``,
                ``"experience"``, ``"earlier_experience"``, ``"languages"``.
            instructions: Accumulated user feedback to apply.
            context: Pipeline context (JD analysis, ATS keywords, KB text).
            role_index: Index into ``content.roles`` when
                ``section_type`` is ``"experience"``.

        Returns:
            A new ``TailoredContent`` with the targeted section replaced.

        Raises:
            PipelineStageError: If the section type is unknown or the
                LLM call fails.
            ValueError: If ``section_type`` is ``"experience"`` but
                ``role_index`` is ``None`` or out of range.
        """
        if section_type not in _VALID_SECTION_TYPES:
            raise PipelineStageError(
                f"Unknown section type: {section_type!r}. "
                f"Valid types: {sorted(_VALID_SECTION_TYPES)}",
                stage="regenerate_section",
                stage_number=0,
            )

        if section_type == "experience":
            if role_index is None:
                raise ValueError(
                    "role_index is required when section_type is 'experience'"
                )
            if role_index < 0 or role_index >= len(content.roles):
                raise ValueError(
                    f"role_index {role_index} out of range "
                    f"(0..{len(content.roles) - 1})"
                )

        current_section = self._extract_section(content, section_type, role_index)
        response_model = _SECTION_MODELS[section_type]

        prompt = self._build_prompt(
            section_type=section_type,
            current_section=current_section,
            instructions=instructions,
            context=context,
            role_index=role_index,
        )

        result = await self._call_llm(prompt, response_model)
        return self._merge_result(content, section_type, result, role_index)

    def _extract_section(
        self,
        content: TailoredContent,
        section_type: str,
        role_index: int | None,
    ) -> object:
        """Extract the current section content for inclusion in the prompt."""
        match section_type:
            case "mission":
                return content.mission.model_dump()
            case "skills":
                return [sg.model_dump() for sg in content.skills]
            case "experience":
                assert role_index is not None
                return content.roles[role_index].model_dump()
            case "earlier_experience":
                return content.earlier_experience or ""
            case "languages":
                return content.languages or []
            case _:  # pragma: no cover
                raise PipelineStageError(
                    f"Cannot extract section: {section_type!r}",
                    stage="regenerate_section",
                    stage_number=0,
                )

    def _build_prompt(
        self,
        *,
        section_type: str,
        current_section: object,
        instructions: list[str],
        context: RegenerationContext,
        role_index: int | None,
    ) -> str:
        """Build the regeneration prompt using the Jinja2 template."""
        template_context: dict[str, object] = {
            "section_type": section_type,
            "current_content": current_section,
            "instructions": instructions,
            "jd_analysis": context.jd_analysis if context.jd_analysis else None,
            "ats_keywords": context.ats_keywords if context.ats_keywords else None,
            "kb_text": context.kb_text if context.kb_text else None,
            "role_index": role_index,
        }

        return self._prompts.render("regenerate_section.j2", template_context)

    async def _call_llm(
        self,
        prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Call the LLM with structured output for the given response model."""
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self._llm.complete_structured(
                messages,
                model=self._model,
                response_model=response_model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except PipelineStageError:
            raise
        except Exception as exc:
            raise PipelineStageError(
                f"Regeneration failed for section: {exc}",
                stage="regenerate_section",
                stage_number=0,
            ) from exc

        return result

    def _merge_result(
        self,
        content: TailoredContent,
        section_type: str,
        result: BaseModel,
        role_index: int | None,
    ) -> TailoredContent:
        """Merge the regenerated section into the full content."""
        match section_type:
            case "mission":
                return content.model_copy(
                    update={"mission": cast("MissionStatement", result)}
                )
            case "skills":
                skills_result = cast("SkillsSection", result)
                return content.model_copy(update={"skills": skills_result.skills})
            case "experience":
                assert role_index is not None
                role = cast("TailoredRole", result)
                updated_roles = list(content.roles)
                updated_roles[role_index] = role
                return content.model_copy(update={"roles": updated_roles})
            case "earlier_experience":
                ee_result = cast("EarlierExperienceSection", result)
                return content.model_copy(
                    update={"earlier_experience": ee_result.earlier_experience}
                )
            case "languages":
                lang_result = cast("LanguagesSection", result)
                return content.model_copy(update={"languages": lang_result.languages})
            case _:  # pragma: no cover
                raise PipelineStageError(
                    f"Cannot merge section: {section_type!r}",
                    stage="regenerate_section",
                    stage_number=0,
                )
