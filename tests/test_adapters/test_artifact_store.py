"""Tests for FileSystemArtifactStore."""

import json
from pathlib import Path

import pytest

from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore


class TestFileSystemArtifactStore:
    """Tests for artifact save/load operations."""

    def test_saves_json_artifact(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = tmp_path / "run1"
        data = {"stage": "analyze", "result": "ok"}
        path = store.save("stage1_analysis", data, run_dir=run_dir)
        assert path.is_file()

    def test_loads_saved_json_artifact(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = tmp_path / "run1"
        data = {"stage": "analyze", "result": "ok"}
        store.save("stage1_analysis", data, run_dir=run_dir)
        loaded = store.load("stage1_analysis", run_dir=run_dir)
        assert loaded == data

    def test_save_appends_json_extension(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = tmp_path / "run1"
        path = store.save("my_artifact", {"key": "val"}, run_dir=run_dir)
        assert path.name == "my_artifact.json"

    def test_save_preserves_existing_json_extension(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = tmp_path / "run1"
        path = store.save("my_artifact.json", {"key": "val"}, run_dir=run_dir)
        assert path.name == "my_artifact.json"

    def test_create_run_dir_creates_directory(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = store.create_run_dir(tmp_path)
        assert run_dir.is_dir()

    def test_create_run_dir_is_inside_mkcv_dir(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = store.create_run_dir(tmp_path)
        assert ".mkcv" in run_dir.parts

    def test_create_run_dir_with_company_includes_company(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = store.create_run_dir(tmp_path, company="DeepL")
        assert "deepl" in run_dir.name

    def test_save_final_output_writes_text_file(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        path = store.save_final_output(
            "resume.yaml", "cv:\n  name: John", output_dir=tmp_path
        )
        assert path.is_file()
        assert path.read_text() == "cv:\n  name: John"

    def test_save_final_output_writes_binary_file(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        content = b"%PDF-1.4 fake pdf content"
        path = store.save_final_output("resume.pdf", content, output_dir=tmp_path)
        assert path.is_file()
        assert path.read_bytes() == content

    def test_load_raises_file_not_found_for_missing_artifact(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemArtifactStore()
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent", run_dir=tmp_path)

    def test_saved_artifact_is_valid_json(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        run_dir = tmp_path / "run1"
        data = {"nested": {"key": [1, 2, 3]}}
        path = store.save("complex", data, run_dir=run_dir)
        parsed = json.loads(path.read_text())
        assert parsed == data

    def test_create_run_dir_creates_parents(self, tmp_path: Path) -> None:
        store = FileSystemArtifactStore()
        base = tmp_path / "deep" / "nested"
        run_dir = store.create_run_dir(base)
        assert run_dir.is_dir()
