"""Section types and builders for interactive resume review."""

from dataclasses import dataclass, field
from enum import Enum, auto

from mkcv.core.models.tailored_content import TailoredContent


class SectionKind(Enum):
    """Kinds of resume sections presented in interactive review."""

    MISSION = auto()
    SKILLS = auto()
    EXPERIENCE = auto()
    EARLIER_EXPERIENCE = auto()
    LANGUAGES = auto()


class SectionState(Enum):
    """Review state for a section."""

    PENDING = auto()
    ACCEPTED = auto()
    SKIPPED = auto()


@dataclass
class SectionInfo:
    """Metadata for a single reviewable section."""

    kind: SectionKind
    label: str
    state: SectionState = field(default=SectionState.PENDING)
    role_index: int | None = None


def build_sections(content: TailoredContent) -> list[SectionInfo]:
    """Map a TailoredContent to an ordered list of reviewable sections."""
    sections: list[SectionInfo] = []

    if content.mission:
        sections.append(SectionInfo(kind=SectionKind.MISSION, label="Mission"))

    if content.skills:
        sections.append(SectionInfo(kind=SectionKind.SKILLS, label="Skills"))

    for idx, role in enumerate(content.roles):
        label = f"Experience: {role.company}, {role.position}"
        sections.append(
            SectionInfo(
                kind=SectionKind.EXPERIENCE,
                label=label,
                role_index=idx,
            )
        )

    if content.earlier_experience:
        sections.append(
            SectionInfo(kind=SectionKind.EARLIER_EXPERIENCE, label="Earlier Experience")
        )

    if content.languages:
        sections.append(SectionInfo(kind=SectionKind.LANGUAGES, label="Languages"))

    return sections
