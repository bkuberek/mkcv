"""Knowledge base structure validation.

Validates that a Markdown knowledge base file has the expected
sections and content quality for resume generation.
"""

import re

from mkcv.core.models.kb_validation import KBValidationResult

MIN_KB_LENGTH = 500
MAX_KB_LENGTH = 50_000

REQUIRED_SECTIONS: dict[str, list[str]] = {
    "Contact / Personal Info": [
        "personal information",
        "contact",
        "contact info",
        "contact information",
    ],
    "Summary / Profile": [
        "summary",
        "professional summary",
        "profile",
        "about",
        "about me",
        "overview",
    ],
    "Experience / Work History": [
        "experience",
        "work experience",
        "work history",
        "career history",
        "employment",
        "employment history",
        "professional experience",
    ],
    "Education": [
        "education",
        "academic background",
        "academic",
        "degrees",
    ],
    "Skills": [
        "skills",
        "technical skills",
        "core skills",
        "competencies",
        "technologies",
    ],
}

OPTIONAL_SECTIONS: dict[str, list[str]] = {
    "Projects": [
        "projects",
        "key projects",
        "side projects",
        "personal projects",
        "open source",
    ],
    "Certifications": [
        "certifications",
        "certificates",
        "licenses",
        "credentials",
        "professional certifications",
    ],
}

_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_BULLET_PATTERN = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)


def validate_kb(content: str) -> KBValidationResult:
    """Validate knowledge base content for structure and completeness.

    Checks for expected Markdown headings, date patterns in
    experience sections, bullet points, and reasonable length.

    Args:
        content: Raw Markdown text of the knowledge base.

    Returns:
        KBValidationResult with errors, warnings, and section info.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not content.strip():
        return KBValidationResult(
            is_valid=False,
            warnings=[],
            errors=["Knowledge base is empty."],
            sections_found=[],
            sections_missing=list(REQUIRED_SECTIONS.keys()),
        )

    headings = _extract_headings(content)

    if not headings:
        return KBValidationResult(
            is_valid=False,
            warnings=[],
            errors=[
                "No Markdown headings found. "
                "The knowledge base should use # headings to organize sections."
            ],
            sections_found=[],
            sections_missing=list(REQUIRED_SECTIONS.keys()),
        )

    sections_found, sections_missing = _check_sections(headings)

    for section_name in sections_missing:
        warnings.append(f"Missing recommended section: {section_name}.")

    _check_experience_dates(content, headings, warnings)
    _check_experience_bullets(content, headings, warnings)
    _check_length(content, warnings)

    is_valid = len(errors) == 0

    return KBValidationResult(
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
        sections_found=sections_found,
        sections_missing=sections_missing,
    )


def _extract_headings(content: str) -> list[str]:
    """Extract all Markdown heading texts, normalized to lowercase."""
    return [match.group(1).strip() for match in _HEADING_PATTERN.finditer(content)]


def _check_sections(
    headings: list[str],
) -> tuple[list[str], list[str]]:
    """Identify which required sections are present or missing.

    Returns:
        Tuple of (found section names, missing section names).
    """
    headings_lower = [h.lower() for h in headings]

    found: list[str] = []
    missing: list[str] = []

    all_sections = {**REQUIRED_SECTIONS, **OPTIONAL_SECTIONS}

    for section_name, aliases in all_sections.items():
        matched = any(
            _heading_matches_alias(heading, alias)
            for heading in headings_lower
            for alias in aliases
        )
        if matched:
            found.append(section_name)

    for section_name in REQUIRED_SECTIONS:
        if section_name not in found:
            missing.append(section_name)

    return found, missing


def _heading_matches_alias(heading: str, alias: str) -> bool:
    """Check if a heading matches an alias.

    Supports both exact match and substring containment so that
    headings like "Technical Skills -- Master List" match the
    "technical skills" alias.
    """
    return alias in heading


def _check_experience_dates(
    content: str,
    headings: list[str],
    warnings: list[str],
) -> None:
    """Warn if the experience section appears to lack date information."""
    headings_lower = [h.lower() for h in headings]
    has_experience = any(
        _heading_matches_alias(h, alias)
        for h in headings_lower
        for alias in REQUIRED_SECTIONS["Experience / Work History"]
    )

    if not has_experience:
        return

    experience_text = _extract_section_text(
        content, REQUIRED_SECTIONS["Experience / Work History"]
    )

    if experience_text and not _YEAR_PATTERN.search(experience_text):
        warnings.append(
            "Experience section has no year references (e.g. 2020, 2021-2023). "
            "Adding dates helps the AI place your experience chronologically."
        )


def _check_experience_bullets(
    content: str,
    headings: list[str],
    warnings: list[str],
) -> None:
    """Warn if the experience section has no bullet points."""
    headings_lower = [h.lower() for h in headings]
    has_experience = any(
        _heading_matches_alias(h, alias)
        for h in headings_lower
        for alias in REQUIRED_SECTIONS["Experience / Work History"]
    )

    if not has_experience:
        return

    experience_text = _extract_section_text(
        content, REQUIRED_SECTIONS["Experience / Work History"]
    )

    if experience_text and not _BULLET_PATTERN.search(experience_text):
        warnings.append(
            "Experience section has no bullet points. "
            "Use - or * bullets to list achievements and responsibilities."
        )


def _check_length(content: str, warnings: list[str]) -> None:
    """Warn about suspiciously short or long KB content."""
    length = len(content)

    if length < MIN_KB_LENGTH:
        warnings.append(
            f"Knowledge base is very short ({length} characters). "
            f"A comprehensive KB typically has at least {MIN_KB_LENGTH} characters."
        )

    if length > MAX_KB_LENGTH:
        warnings.append(
            f"Knowledge base is very long ({length} characters). "
            f"Consider trimming to under {MAX_KB_LENGTH:,} characters "
            "to stay within LLM context limits."
        )


def _extract_section_text(content: str, aliases: list[str]) -> str:
    """Extract text from the first matching section to the next heading.

    Finds the first heading that matches any alias and returns the
    content between it and the next same-or-higher-level heading.
    """
    for match in _HEADING_PATTERN.finditer(content):
        heading_text = match.group(1).strip().lower()
        if any(_heading_matches_alias(heading_text, alias) for alias in aliases):
            heading_line = match.group(0)
            heading_level = len(heading_line) - len(heading_line.lstrip("#"))

            start = match.end()
            remaining = content[start:]

            next_heading = re.search(
                rf"^#{{1,{heading_level}}}\s+",
                remaining,
                re.MULTILINE,
            )
            if next_heading:
                return remaining[: next_heading.start()]
            return remaining

    return ""
