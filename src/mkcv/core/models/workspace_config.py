"""Workspace configuration model (parsed from mkcv.toml)."""

from pydantic import BaseModel, Field


class WorkspacePaths(BaseModel):
    """Path configuration within a workspace."""

    knowledge_base: str = "knowledge-base/career.md"
    applications_dir: str = "applications"
    templates_dir: str = "templates"


class WorkspaceNaming(BaseModel):
    """Naming convention configuration."""

    company_slug: bool = True
    application_pattern: str = "{company}/{position}/{date}"


class WorkspaceDefaults(BaseModel):
    """Default settings for workspace operations."""

    theme: str = "sb2nov"
    profile: str = "premium"


class WorkspaceConfig(BaseModel):
    """Workspace configuration parsed from mkcv.toml."""

    version: str = "0.1.0"
    paths: WorkspacePaths = Field(default_factory=WorkspacePaths)
    naming: WorkspaceNaming = Field(default_factory=WorkspaceNaming)
    defaults: WorkspaceDefaults = Field(default_factory=WorkspaceDefaults)
    voice_guidelines: str = ""
