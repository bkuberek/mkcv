"""One persona and job description pair the harness evaluates."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

REFERENCE_FILES: dict[StageKey, tuple[str, ...]] = {
    StageKey.ANALYZE: ("stage1_analysis.json",),
    StageKey.SELECT: ("stage2_selection.json",),
    StageKey.TAILOR: ("stage3_content.json",),
    StageKey.STRUCTURE: ("stage4_structure.json", "resume.yaml"),
}
"""Files a case's reference directory holds for each upstream stage.

The names are the ones ``FileSystemArtifactStore`` and ``PipelineService`` use,
so the files can be copied into a work directory unchanged.
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
    fixtures_dir: Path = Field(default=DEFAULT_FIXTURES_DIR, exclude=True, repr=False)

    @field_validator("stages")
    @classmethod
    def _only_pipeline_stages(
        cls, stages: list[StageKey] | None
    ) -> list[StageKey] | None:
        invalid = [
            stage.value for stage in stages or [] if stage not in PIPELINE_STAGES
        ]
        if invalid:
            raise ValueError(f"not resume pipeline stages: {', '.join(invalid)}")
        return stages

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
