"""The claims a stage output makes: bullets, skills, employers, and titles."""

from typing import Any

from pydantic import BaseModel, Field

from evals.graders.resume_yaml import load_cv
from evals.graders.text_normalization import iter_mappings, iter_strings
from mkcv.core.models.stage_key import StageKey

SKILL_SECTIONS = frozenset({"skills", "technical skills", "technologies"})


class ExtractedClaims(BaseModel):
    """What an output asserts about the candidate, as plain strings.

    Bullets are the achievement lines; skills are skill names or lists;
    employers and titles come from the roles. Checking them against the
    knowledge base is the grader's job.
    """

    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    employers: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)


def extract_claims(
    stage: StageKey, output: dict[str, Any] | str | None
) -> ExtractedClaims | None:
    """Return the claims in ``output``, or None if there is nothing to read.

    Stage 2 yields the suggested bullets, highlighted skills, companies, and
    roles; stage 3 the rewritten bullets, skills, tech stacks, companies, and
    positions; stage 4 the highlights, skill sections, companies, and
    positions of the YAML. Other stages make no claims.
    """
    if stage is StageKey.STRUCTURE:
        return _from_resume(output) if isinstance(output, str) else None
    if not isinstance(output, dict):
        return None
    if stage is StageKey.SELECT:
        return _from_selection(output)
    if stage is StageKey.TAILOR:
        return _from_tailored_content(output)
    return None


def _from_selection(output: dict[str, Any]) -> ExtractedClaims:
    claims = ExtractedClaims(skills=_texts(output.get("skills_to_highlight")))
    for experience in _mappings(output.get("selected_experiences")):
        claims.employers += _texts(experience.get("company"))
        claims.titles += _texts(experience.get("role"))
        claims.bullets += _texts(experience.get("suggested_bullets"))
    return claims


def _from_tailored_content(output: dict[str, Any]) -> ExtractedClaims:
    claims = ExtractedClaims()
    for group in _mappings(output.get("skills")):
        claims.skills += _texts(group.get("skills"))
    for role in _mappings(output.get("roles")):
        claims.employers += _texts(role.get("company"))
        claims.titles += _texts(role.get("position"))
        claims.skills += _texts(role.get("tech_stack"))
        claims.bullets += [
            text
            for bullet in _mappings(role.get("bullets"))
            for text in _texts(bullet.get("rewritten"))
        ]
    return claims


def _from_resume(text: str) -> ExtractedClaims | None:
    try:
        cv = load_cv(text)
    except ValueError:
        return None
    sections = cv.get("sections")
    if not isinstance(sections, dict):
        return ExtractedClaims()

    claims = ExtractedClaims()
    for key, section in sections.items():
        if str(key).lower().replace("_", " ").strip() in SKILL_SECTIONS:
            claims.skills += list(iter_strings(section))
        for entry in iter_mappings(section):
            claims.employers += _texts(entry.get("company"))
            claims.titles += _texts(entry.get("position"))
            claims.bullets += _texts(entry.get("highlights"))
    return claims


def _mappings(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _texts(value: Any) -> list[str]:
    """Return the non-blank strings of ``value`` (a string or a list of them)."""
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, str) and item.strip()]
