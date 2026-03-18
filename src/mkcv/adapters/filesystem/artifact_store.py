"""Filesystem-based artifact store for pipeline outputs."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class FileSystemArtifactStore:
    """Reads and writes pipeline artifacts to the filesystem.

    Artifacts are JSON files stored in run directories. In workspace mode,
    run directories are inside application directories. In non-workspace
    mode, they're under a .mkcv/ directory in the output path.

    Implements: ArtifactStorePort
    """

    def save(
        self,
        artifact_name: str,
        data: dict[str, Any],
        *,
        run_dir: Path,
    ) -> Path:
        """Save a JSON artifact to the run directory.

        Args:
            artifact_name: Name for the artifact file (e.g., 'stage1_analysis').
            data: Dictionary to serialize as JSON.
            run_dir: Directory to save the artifact in.

        Returns:
            Path to the saved artifact file.
        """
        run_dir.mkdir(parents=True, exist_ok=True)

        filename = _ensure_json_ext(artifact_name)
        artifact_path = run_dir / filename

        artifact_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        return artifact_path

    def load(
        self,
        artifact_name: str,
        *,
        run_dir: Path,
    ) -> dict[str, Any]:
        """Load a previously saved JSON artifact.

        Args:
            artifact_name: Name of the artifact file.
            run_dir: Directory containing the artifact.

        Returns:
            The deserialized artifact data.

        Raises:
            FileNotFoundError: If the artifact doesn't exist.
        """
        filename = _ensure_json_ext(artifact_name)
        artifact_path = run_dir / filename

        if not artifact_path.is_file():
            msg = f"Artifact not found: {artifact_path}"
            raise FileNotFoundError(msg)

        return json.loads(artifact_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def create_run_dir(
        self,
        base_dir: Path,
        *,
        company: str = "",
        position: str = "",
    ) -> Path:
        """Create a timestamped run directory for pipeline artifacts.

        In non-workspace mode, creates: base_dir/.mkcv/{timestamp}_{company}/
        The workspace mode uses WorkspaceManager for application directories.

        Args:
            base_dir: Base directory for the run.
            company: Company name for directory naming.
            position: Position title (unused in non-workspace mode).

        Returns:
            Path to the created run directory.
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H-%M-%S")
        dir_name = f"{timestamp}_{_sanitize(company)}" if company else timestamp

        run_dir = base_dir / ".mkcv" / dir_name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_final_output(
        self,
        filename: str,
        content: str | bytes,
        *,
        output_dir: Path,
    ) -> Path:
        """Save a final output file to the output directory.

        Final outputs (resume.yaml, resume.pdf) go to the output directory
        root, not inside .mkcv/.

        Args:
            filename: Output filename (e.g., 'resume.yaml').
            content: File content (str for text, bytes for binary).
            output_dir: Directory to save the output in.

        Returns:
            Path to the saved output file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename

        if isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            output_path.write_text(content, encoding="utf-8")

        return output_path


def _ensure_json_ext(name: str) -> str:
    """Append .json extension if not already present."""
    return name if name.endswith(".json") else f"{name}.json"


def _sanitize(text: str) -> str:
    """Sanitize a string for use in a directory name.

    Converts to lowercase, replaces spaces and special chars with hyphens,
    and removes consecutive hyphens.

    Args:
        text: Raw text to sanitize.

    Returns:
        Filesystem-safe string.
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
