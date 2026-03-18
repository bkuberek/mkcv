"""Tests for workspace-related models."""

from datetime import date

import pytest
from pydantic import ValidationError

from mkcv.core.models.application_metadata import ApplicationMetadata
from mkcv.core.models.workspace_config import (
    WorkspaceConfig,
    WorkspaceDefaults,
    WorkspaceNaming,
    WorkspacePaths,
)


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig model."""

    def test_defaults(self) -> None:
        config = WorkspaceConfig()
        assert config.version == "0.1.0"

    def test_default_paths(self) -> None:
        config = WorkspaceConfig()
        assert config.paths.knowledge_base == "knowledge-base/career.md"

    def test_default_applications_dir(self) -> None:
        config = WorkspaceConfig()
        assert config.paths.applications_dir == "applications"

    def test_default_templates_dir(self) -> None:
        config = WorkspaceConfig()
        assert config.paths.templates_dir == "templates"

    def test_default_naming(self) -> None:
        config = WorkspaceConfig()
        assert config.naming.company_slug is True
        assert config.naming.application_pattern == "{date}-{position}"

    def test_default_theme(self) -> None:
        config = WorkspaceConfig()
        assert config.defaults.theme == "sb2nov"

    def test_default_profile(self) -> None:
        config = WorkspaceConfig()
        assert config.defaults.profile == "premium"

    def test_default_voice_guidelines(self) -> None:
        config = WorkspaceConfig()
        assert config.voice_guidelines == ""

    def test_custom_values(self) -> None:
        config = WorkspaceConfig(
            version="1.0.0",
            paths=WorkspacePaths(knowledge_base="kb/resume.md"),
            naming=WorkspaceNaming(company_slug=False),
            defaults=WorkspaceDefaults(theme="classic", profile="budget"),
            voice_guidelines="Be concise",
        )
        assert config.version == "1.0.0"
        assert config.paths.knowledge_base == "kb/resume.md"
        assert config.naming.company_slug is False
        assert config.defaults.theme == "classic"
        assert config.defaults.profile == "budget"
        assert config.voice_guidelines == "Be concise"


class TestApplicationMetadata:
    """Tests for ApplicationMetadata model."""

    def test_creation(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
        )
        assert meta.company == "DeepL"
        assert meta.position == "Staff Engineer"

    def test_default_status_is_draft(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
        )
        assert meta.status == "draft"

    def test_status_applied(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            status="applied",
        )
        assert meta.status == "applied"

    def test_status_interviewing(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            status="interviewing",
        )
        assert meta.status == "interviewing"

    def test_status_offered(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            status="offered",
        )
        assert meta.status == "offered"

    def test_status_rejected(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            status="rejected",
        )
        assert meta.status == "rejected"

    def test_status_withdrawn(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            status="withdrawn",
        )
        assert meta.status == "withdrawn"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ApplicationMetadata(
                company="DeepL",
                position="Staff Engineer",
                date=date(2025, 6, 15),
                status="accepted",  # type: ignore[arg-type]
            )

    def test_url_defaults_to_none(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
        )
        assert meta.url is None

    def test_url_with_value(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
            url="https://deepl.com/jobs/123",
        )
        assert meta.url == "https://deepl.com/jobs/123"

    def test_created_at_is_auto_populated(self) -> None:
        meta = ApplicationMetadata(
            company="DeepL",
            position="Staff Engineer",
            date=date(2025, 6, 15),
        )
        assert meta.created_at is not None
