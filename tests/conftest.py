"""Shared test fixtures for mkcv tests."""

from pathlib import Path

import pytest

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager


@pytest.fixture
def sample_jd_text() -> str:
    """Sample job description text for testing."""
    return (
        "Senior Staff Software Engineer - API Platform\n"
        "\n"
        "Company: DeepL\n"
        "Location: Remote (EU)\n"
        "\n"
        "Requirements:\n"
        "- 8+ years of software engineering experience\n"
        "- Strong Python and distributed systems knowledge\n"
        "- Experience with API design and high-traffic services\n"
        "- Leadership and mentoring skills\n"
    )


@pytest.fixture
def sample_kb_text() -> str:
    """Sample knowledge base text for testing."""
    return (
        "# John Doe -- Knowledge Base\n"
        "\n"
        "## Professional Summary\n"
        "Senior software engineer with 10 years of experience.\n"
        "\n"
        "## Technical Skills\n"
        "- Python, Go, TypeScript\n"
        "- AWS, Kubernetes, Docker\n"
    )


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """Create a temporary workspace with mkcv.toml."""
    mgr = WorkspaceManager()
    target = tmp_path / "workspace"
    mgr.create_workspace(target)
    return target


@pytest.fixture
def sample_jd_file(tmp_path: Path, sample_jd_text: str) -> Path:
    """Create a temporary JD file."""
    jd_path = tmp_path / "test-jd.txt"
    jd_path.write_text(sample_jd_text)
    return jd_path
