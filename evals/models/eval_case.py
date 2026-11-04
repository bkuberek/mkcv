"""One persona and job description pair the harness evaluates."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evals.models.cover_letter_expectations import CoverLetterExpectations
from evals.stages import EVALUATED_STAGES, STAGE_ORDER
from mkcv.core.models.stage_key import StageKey

COVER_LETTER_FILE = "cover_letter_content.json"

REFERENCE_FILES: dict[StageKey, tuple[str, ...]] = {
    StageKey.ANALYZE: ("stage1_analysis.json",),
    StageKey.SELECT: ("stage2_selection.json",),
    StageKey.TAILOR: ("stage3_content.json",),
    StageKey.STRUCTURE: ("stage4_structure.json", "resume.yaml"),
    StageKey.COVER_LETTER_GENERATE: (COVER_LETTER_FILE,),
}
"""Files a case's reference directory holds for each upstream stage.

The names are the ones ``FileSystemArtifactStore``, ``PipelineService``, and
``CoverLetterService`` use, so the files can be copied into a work directory
unchanged.
"""

PIPELINE_REFERENCE_STAGES: tuple[StageKey, ...] = (
    StageKey.ANALYZE,
    StageKey.SELECT,
    StageKey.TAILOR,
    StageKey.STRUCTURE,
)
"""The resume stages whose references ``bootstrap-reference`` runs together."""

UPSTREAM_STAGES: dict[StageKey, tuple[StageKey, ...]] = {
    StageKey.ANALYZE: (),
    StageKey.SELECT: (StageKey.ANALYZE,),
    StageKey.TAILOR: (StageKey.ANALYZE, StageKey.SELECT),
    StageKey.STRUCTURE: (StageKey.ANALYZE, StageKey.SELECT, StageKey.TAILOR),
    StageKey.REVIEW: PIPELINE_REFERENCE_STAGES,
    StageKey.COVER_LETTER_GENERATE: (StageKey.ANALYZE, StageKey.STRUCTURE),
    StageKey.COVER_LETTER_REVIEW: (StageKey.COVER_LETTER_GENERATE,),
}
"""The reference stages each evaluated stage reads its input from.

The cover letter is written from the knowledge base, the job description,
the reference resume, and the company and role of the reference analysis;
its review reads the reference letter.
"""

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class EvalCase(BaseModel):
    """A persona knowledge base plus job description, with what to check for."""

    model_config = ConfigDict(extra="forbid")

    id: str
    persona: str = Field(description="Persona file, relative to the fixtures directory")
    jd: str = Field(description="Job description file, relative to the fixtures dir")
    expected_keywords: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(
        default_factory=list,
        description="Terms the job description asks for that the persona lacks",
    )
    review_probe_defects: list[str] = Field(
        default_factory=list,
        description="Defects seeded in the reference resume for the review stage",
    )
    stages: list[StageKey] | None = Field(
        default=None,
        description="Stages this case applies to; None means every stage run",
    )
    cover_letter: CoverLetterExpectations = Field(
        default_factory=CoverLetterExpectations
    )
    fixtures_dir: Path = Field(default=DEFAULT_FIXTURES_DIR, exclude=True, repr=False)

    @field_validator("stages")
    @classmethod
    def _only_evaluated_stages(
        cls, stages: list[StageKey] | None
    ) -> list[StageKey] | None:
        invalid = [
            stage.value for stage in stages or [] if stage not in EVALUATED_STAGES
        ]
        if invalid:
            raise ValueError(f"not stages the harness evaluates: {', '.join(invalid)}")
        return stages

    @property
    def is_cover_letter_probe(self) -> bool:
        """True when the reference cover letter is hand-written with defects."""
        return bool(self.cover_letter.review_defects)

    @property
    def cover_letter_forbidden(self) -> list[str]:
        """What the letter must not claim: forbidden claims and ``must_not_claim``."""
        terms = [*self.forbidden_claims, *self.cover_letter.must_not_claim]
        return list(dict.fromkeys(terms))

    @property
    def persona_path(self) -> Path:
        """Absolute path of the persona knowledge base."""
        return self.fixtures_dir / self.persona

    @property
    def jd_path(self) -> Path:
        """Absolute path of the job description."""
        return self.fixtures_dir / self.jd

    @property
    def reference_dir(self) -> Path:
        """Directory holding this case's reference stage artifacts."""
        return self.fixtures_dir / "reference" / self.id

    @property
    def kb_text(self) -> str:
        """The persona knowledge base text."""
        return self.persona_path.read_text(encoding="utf-8")

    @property
    def jd_text(self) -> str:
        """The job description text."""
        return self.jd_path.read_text(encoding="utf-8")

    def applies_to(self, stage: StageKey) -> bool:
        """Return True if this case should be evaluated at ``stage``."""
        return self.stages is None or stage in self.stages

    def existing_reference_files(self) -> list[Path]:
        """Return every reference file already on disk, complete stage or not."""
        return [
            path
            for names in REFERENCE_FILES.values()
            for name in names
            if (path := self.reference_dir / name).is_file()
        ]

    def reference_stages(self) -> list[StageKey]:
        """Return the stages whose reference files all exist, in pipeline order."""
        return [
            stage
            for stage, names in REFERENCE_FILES.items()
            if all((self.reference_dir / name).is_file() for name in names)
        ]

    def needed_reference_stages(self) -> list[StageKey]:
        """Return the reference stages the case's evaluated stages read from."""
        needed = {
            upstream
            for stage in EVALUATED_STAGES
            if self.applies_to(stage)
            for upstream in UPSTREAM_STAGES[stage]
        }
        return sorted(needed, key=STAGE_ORDER.__getitem__)
