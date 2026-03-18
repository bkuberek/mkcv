"""Tests for mkcv exception hierarchy."""

import pytest

from mkcv.core.exceptions import (
    AuthenticationError,
    ContextLengthError,
    MkcvError,
    PipelineStageError,
    ProviderError,
    RateLimitError,
    RenderError,
    TemplateError,
    ValidationError,
    WorkspaceError,
    WorkspaceExistsError,
    WorkspaceNotFoundError,
)


class TestMkcvError:
    """Tests for the base MkcvError exception."""

    def test_default_exit_code_is_one(self) -> None:
        err = MkcvError("something went wrong")
        assert err.exit_code == 1

    def test_message_is_preserved(self) -> None:
        err = MkcvError("something went wrong")
        assert str(err) == "something went wrong"

    def test_custom_exit_code(self) -> None:
        err = MkcvError("oops", exit_code=42)
        assert err.exit_code == 42

    def test_is_exception(self) -> None:
        assert issubclass(MkcvError, Exception)


class TestProviderError:
    """Tests for ProviderError and its subclasses."""

    def test_exit_code_is_four(self) -> None:
        err = ProviderError("provider failed")
        assert err.exit_code == 4

    def test_provider_field_is_stored(self) -> None:
        err = ProviderError("provider failed", provider="anthropic")
        assert err.provider == "anthropic"

    def test_provider_field_defaults_to_empty(self) -> None:
        err = ProviderError("provider failed")
        assert err.provider == ""

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(ProviderError, MkcvError)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_inherits_from_provider_error(self) -> None:
        assert issubclass(RateLimitError, ProviderError)

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(RateLimitError, MkcvError)

    def test_exit_code_is_four(self) -> None:
        err = RateLimitError("rate limited", provider="openai")
        assert err.exit_code == 4


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_inherits_from_provider_error(self) -> None:
        assert issubclass(AuthenticationError, ProviderError)

    def test_exit_code_is_four(self) -> None:
        err = AuthenticationError("bad key", provider="anthropic")
        assert err.exit_code == 4


class TestContextLengthError:
    """Tests for ContextLengthError."""

    def test_inherits_from_provider_error(self) -> None:
        assert issubclass(ContextLengthError, ProviderError)

    def test_exit_code_is_four(self) -> None:
        err = ContextLengthError("too long", provider="openai")
        assert err.exit_code == 4


class TestPipelineStageError:
    """Tests for PipelineStageError."""

    def test_exit_code_is_five(self) -> None:
        err = PipelineStageError("stage failed")
        assert err.exit_code == 5

    def test_stores_stage_info(self) -> None:
        err = PipelineStageError("stage failed", stage="analyze", stage_number=1)
        assert err.stage == "analyze"
        assert err.stage_number == 1

    def test_stage_defaults(self) -> None:
        err = PipelineStageError("stage failed")
        assert err.stage == ""
        assert err.stage_number == 0

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(PipelineStageError, MkcvError)

    def test_message_is_preserved(self) -> None:
        err = PipelineStageError("analysis blew up", stage="analyze")
        assert str(err) == "analysis blew up"


class TestWorkspaceError:
    """Tests for WorkspaceError and subclasses."""

    def test_exit_code_is_seven(self) -> None:
        err = WorkspaceError("workspace broken")
        assert err.exit_code == 7

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(WorkspaceError, MkcvError)


class TestWorkspaceNotFoundError:
    """Tests for WorkspaceNotFoundError."""

    def test_inherits_from_workspace_error(self) -> None:
        assert issubclass(WorkspaceNotFoundError, WorkspaceError)

    def test_exit_code_is_seven(self) -> None:
        err = WorkspaceNotFoundError("not found")
        assert err.exit_code == 7


class TestWorkspaceExistsError:
    """Tests for WorkspaceExistsError."""

    def test_inherits_from_workspace_error(self) -> None:
        assert issubclass(WorkspaceExistsError, WorkspaceError)

    def test_exit_code_is_seven(self) -> None:
        err = WorkspaceExistsError("already exists")
        assert err.exit_code == 7


class TestTemplateError:
    """Tests for TemplateError."""

    def test_exit_code_is_six(self) -> None:
        err = TemplateError("bad template", template_name="foo.j2")
        assert err.exit_code == 6

    def test_stores_template_name(self) -> None:
        err = TemplateError("bad template", template_name="foo.j2")
        assert err.template_name == "foo.j2"

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(TemplateError, MkcvError)


class TestRenderError:
    """Tests for RenderError."""

    def test_exit_code_is_six(self) -> None:
        err = RenderError("render failed")
        assert err.exit_code == 6

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(RenderError, MkcvError)


class TestValidationError:
    """Tests for ValidationError."""

    def test_exit_code_is_five(self) -> None:
        err = ValidationError("invalid output")
        assert err.exit_code == 5

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(ValidationError, MkcvError)


class TestAllExceptionsInheritFromMkcvError:
    """Verify all public exceptions inherit from MkcvError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            ProviderError,
            RateLimitError,
            AuthenticationError,
            ContextLengthError,
            PipelineStageError,
            WorkspaceError,
            WorkspaceNotFoundError,
            WorkspaceExistsError,
            TemplateError,
            RenderError,
            ValidationError,
        ],
    )
    def test_inherits_from_mkcv_error(self, exc_class: type[MkcvError]) -> None:
        assert issubclass(exc_class, MkcvError)
