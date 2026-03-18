"""Port interface for pipeline artifact persistence."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ArtifactStorePort(Protocol):
    """Interface for reading and writing pipeline artifacts.

    Artifacts are intermediate JSON/YAML outputs from pipeline stages.
    Implementations: FileSystemArtifactStore.
    """

    def save(
        self,
        artifact_name: str,
        data: dict[str, Any],
        *,
        run_dir: Path,
    ) -> Path:
        """Save an artifact to the store. Returns the written path."""
        ...

    def load(
        self,
        artifact_name: str,
        *,
        run_dir: Path,
    ) -> dict[str, Any]:
        """Load a previously saved artifact."""
        ...

    def create_run_dir(
        self,
        base_dir: Path,
        *,
        company: str = "",
        position: str = "",
    ) -> Path:
        """Create a new run directory for pipeline artifacts."""
        ...

    def save_final_output(
        self,
        filename: str,
        content: str | bytes,
        *,
        output_dir: Path,
    ) -> Path:
        """Save a final output file (resume.yaml, resume.pdf) to the output dir."""
        ...
