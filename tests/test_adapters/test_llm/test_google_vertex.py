"""Tests for the Google provider in Vertex AI mode (ADC)."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dynaconf import Dynaconf
from google.auth.exceptions import DefaultCredentialsError

from mkcv.adapters.llm.google import GoogleGeminiAdapter
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.core.exceptions.configuration import ConfigurationError

_ENVIRONMENT = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
)

VERTEX_CONFIG = """
[default.providers.google]
vertexai = true
project = "cfg-project"
location = "europe-west4"
"""

_ADC = "google.auth.default"
_LOAD = "google.auth.load_credentials_from_file"
_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

FILE_CONFIG = """
[default.providers.google]
vertexai = true
location = "global"
credentials_file = "~/.config/gcloud-mkcv/adc.json"
"""


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)


def _registry(tmp_path: Path, config_text: str = "") -> ProviderRegistry:
    path = tmp_path / "layer.toml"
    path.write_text(config_text)
    config = Dynaconf(
        settings_files=[str(path)],
        environments=True,
        default_env="default",
        merge_enabled=True,
    )
    return ProviderRegistry.from_config(config, load_model_catalog(config))


def _client_kwargs(registry: ProviderRegistry) -> dict[str, object]:
    with patch("mkcv.adapters.llm.google.genai.Client") as client:
        registry.create_adapter("google", with_retry=False)
    return dict(client.call_args.kwargs)


class TestEnablingVertexMode:
    def test_it_is_off_by_default(self, tmp_path: Path) -> None:
        assert _registry(tmp_path).uses_vertex("google") is False

    def test_config_turns_it_on(self, tmp_path: Path) -> None:
        assert _registry(tmp_path, VERTEX_CONFIG).uses_vertex("google") is True

    @pytest.mark.parametrize("value", ["true", "TRUE", "True", "1"])
    def test_a_truthy_environment_variable_turns_it_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", value)
        assert _registry(tmp_path).uses_vertex("google") is True

    @pytest.mark.parametrize("value", ["false", "0", "", "yes"])
    def test_other_environment_values_leave_it_off(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", value)
        assert _registry(tmp_path).uses_vertex("google") is False

    def test_config_false_beats_a_truthy_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
        config = "[default.providers.google]\nvertexai = false\n"
        assert _registry(tmp_path, config).uses_vertex("google") is False

    def test_config_true_beats_a_falsy_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")
        assert _registry(tmp_path, VERTEX_CONFIG).uses_vertex("google") is True

    def test_other_providers_never_use_vertex(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
        assert _registry(tmp_path).uses_vertex("openai") is False

    def test_vertexai_must_be_a_boolean(self, tmp_path: Path) -> None:
        config = '[default.providers.google]\nvertexai = "yes"\n'
        with pytest.raises(ConfigurationError, match="vertexai"):
            _registry(tmp_path, config)

    def test_vertex_keys_are_not_reported_as_unknown(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            _registry(tmp_path, VERTEX_CONFIG)
        assert "Ignoring unknown key" not in caplog.text


class TestClientConstruction:
    def test_the_client_gets_vertex_project_and_location_but_no_key(
        self, tmp_path: Path
    ) -> None:
        with patch(_ADC, return_value=(MagicMock(), "adc-project")):
            kwargs = _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        assert kwargs["vertexai"] is True
        assert kwargs["project"] == "cfg-project"
        assert kwargs["location"] == "europe-west4"
        assert "api_key" not in kwargs

    def test_an_api_key_is_ignored_in_vertex_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        with patch(_ADC, return_value=(MagicMock(), "adc-project")):
            kwargs = _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        assert kwargs["vertexai"] is True
        assert "api_key" not in kwargs

    def test_vertex_wins_over_an_api_key_and_says_so(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        with (
            patch(_ADC, return_value=(MagicMock(), "p")),
            caplog.at_level(logging.DEBUG),
        ):
            _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        assert "Vertex AI" in caplog.text
        assert "secret" not in caplog.text

    def test_base_url_still_reaches_the_client(self, tmp_path: Path) -> None:
        config = VERTEX_CONFIG + 'base_url = "https://proxy.example.com"\n'
        with patch(_ADC, return_value=(MagicMock(), "p")):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["http_options"].base_url == "https://proxy.example.com"  # type: ignore[attr-defined]

    def test_the_adapter_is_a_google_adapter(self, tmp_path: Path) -> None:
        with (
            patch(_ADC, return_value=(MagicMock(), "p")),
            patch("mkcv.adapters.llm.google.genai.Client"),
        ):
            adapter = _registry(tmp_path, VERTEX_CONFIG).create_adapter(
                "google", with_retry=False
            )
        assert isinstance(adapter, GoogleGeminiAdapter)


class TestProjectAndLocationResolution:
    def test_config_project_beats_environment_and_adc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        with patch(_ADC, return_value=(MagicMock(), "adc-project")):
            kwargs = _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        assert kwargs["project"] == "cfg-project"

    def test_environment_project_beats_adc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        config = "[default.providers.google]\nvertexai = true\n"
        with patch(_ADC, return_value=(MagicMock(), "adc-project")):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["project"] == "env-project"

    def test_adc_project_is_the_last_resort(self, tmp_path: Path) -> None:
        config = "[default.providers.google]\nvertexai = true\n"
        with patch(_ADC, return_value=(MagicMock(), "adc-project")):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["project"] == "adc-project"

    def test_no_project_anywhere_is_a_configuration_error(self, tmp_path: Path) -> None:
        config = "[default.providers.google]\nvertexai = true\n"
        with (
            patch(_ADC, return_value=(MagicMock(), None)),
            pytest.raises(ConfigurationError) as caught,
        ):
            _registry(tmp_path, config).create_adapter("google")
        assert "GOOGLE_CLOUD_PROJECT" in str(caught.value)
        assert "project" in str(caught.value)

    def test_config_location_beats_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        with patch(_ADC, return_value=(MagicMock(), "p")):
            kwargs = _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        assert kwargs["location"] == "europe-west4"

    def test_environment_location_beats_the_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        config = '[default.providers.google]\nvertexai = true\nproject = "p"\n'
        with patch(_ADC, return_value=(MagicMock(), None)):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["location"] == "us-central1"

    def test_location_defaults_to_global(self, tmp_path: Path) -> None:
        config = '[default.providers.google]\nvertexai = true\nproject = "p"\n'
        with patch(_ADC, return_value=(MagicMock(), None)):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["location"] == "global"

    def test_the_environment_alone_can_drive_vertex_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        with patch(_ADC, return_value=(MagicMock(), None)):
            kwargs = _client_kwargs(_registry(tmp_path))
        assert kwargs["vertexai"] is True
        assert kwargs["project"] == "env-project"
        assert kwargs["location"] == "global"


class TestMissingApplicationDefaultCredentials:
    def test_create_adapter_explains_how_to_log_in(self, tmp_path: Path) -> None:
        with (
            patch(_ADC, side_effect=DefaultCredentialsError("not found")),
            pytest.raises(ConfigurationError) as caught,
        ):
            _registry(tmp_path, VERTEX_CONFIG).create_adapter("google")
        message = str(caught.value)
        assert "gcloud auth application-default login" in message
        assert "Application Default Credentials" in message
        assert "GOOGLE_CLOUD_PROJECT" in message

    def test_the_error_is_a_configuration_error_with_exit_code_3(
        self, tmp_path: Path
    ) -> None:
        with (
            patch(_ADC, side_effect=DefaultCredentialsError("nope")),
            pytest.raises(ConfigurationError) as caught,
        ):
            _registry(tmp_path, VERTEX_CONFIG).create_adapter("google")
        assert caught.value.exit_code == 3


class TestCredentialCheck:
    def test_true_when_adc_resolves(self, tmp_path: Path) -> None:
        with patch(_ADC, return_value=(MagicMock(), None)):
            assert _registry(tmp_path, VERTEX_CONFIG).has_credentials("google")

    def test_false_when_adc_is_missing(self, tmp_path: Path) -> None:
        with patch(_ADC, side_effect=DefaultCredentialsError("nope")):
            assert not _registry(tmp_path, VERTEX_CONFIG).has_credentials("google")

    def test_an_api_key_does_not_count_in_vertex_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        with patch(_ADC, side_effect=DefaultCredentialsError("nope")):
            assert not _registry(tmp_path, VERTEX_CONFIG).has_credentials("google")

    def test_adc_is_not_consulted_in_api_key_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        with patch(_ADC) as default:
            assert _registry(tmp_path).has_credentials("google")
        default.assert_not_called()


class TestApiKeyModeIsUnchanged:
    def test_the_client_gets_the_key_and_no_vertex_arguments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        kwargs = _client_kwargs(_registry(tmp_path))
        assert kwargs["api_key"] == "secret"
        assert "vertexai" not in kwargs
        assert "project" not in kwargs

    def test_a_missing_key_still_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="No API key for provider"):
            _registry(tmp_path).create_adapter("google")

    def test_the_missing_key_message_mentions_the_adc_alternative(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as caught:
            _registry(tmp_path).create_adapter("google")
        assert "Application Default Credentials" in str(caught.value)
        assert "vertexai" in str(caught.value)


class TestAdapterConstruction:
    def test_credentials_reach_the_client(self) -> None:
        from mkcv.adapters.llm.vertex_target import VertexTarget

        credentials = MagicMock()
        target = VertexTarget(project="p", location="global", credentials=credentials)
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            GoogleGeminiAdapter(vertex=target)
        assert client.call_args.kwargs["credentials"] is credentials

    def test_vertex_target_builds_a_vertex_client(self) -> None:
        from mkcv.adapters.llm.vertex_target import VertexTarget

        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            GoogleGeminiAdapter(vertex=VertexTarget(project="p", location="global"))
        assert client.call_args.kwargs["vertexai"] is True
        assert client.call_args.kwargs["project"] == "p"
        assert client.call_args.kwargs["location"] == "global"
        assert "api_key" not in client.call_args.kwargs


class TestCredentialsFile:
    def test_the_file_is_loaded_with_the_cloud_scope_and_home_expanded(
        self, tmp_path: Path
    ) -> None:
        credentials = MagicMock()
        with (
            patch(_LOAD, return_value=(credentials, "file-project")) as load,
            patch(_ADC) as default,
        ):
            kwargs = _client_kwargs(_registry(tmp_path, FILE_CONFIG))
        path = load.call_args.args[0]
        assert path == str(Path("~/.config/gcloud-mkcv/adc.json").expanduser())
        assert "~" not in path
        assert load.call_args.kwargs["scopes"] == [_SCOPE]
        default.assert_not_called()
        assert kwargs["credentials"] is credentials
        assert "api_key" not in kwargs

    def test_its_project_is_the_fallback_after_config_and_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with patch(_LOAD, return_value=(MagicMock(), "file-project")):
            kwargs = _client_kwargs(_registry(tmp_path, FILE_CONFIG))
        assert kwargs["project"] == "file-project"

        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        with patch(_LOAD, return_value=(MagicMock(), "file-project")):
            kwargs = _client_kwargs(_registry(tmp_path, FILE_CONFIG))
        assert kwargs["project"] == "env-project"

        config = FILE_CONFIG + 'project = "cfg-project"\n'
        with patch(_LOAD, return_value=(MagicMock(), "file-project")):
            kwargs = _client_kwargs(_registry(tmp_path, config))
        assert kwargs["project"] == "cfg-project"

    def test_a_missing_file_is_a_configuration_error_naming_the_path(
        self, tmp_path: Path
    ) -> None:
        with (
            patch(_LOAD, side_effect=FileNotFoundError("nope")),
            pytest.raises(ConfigurationError) as caught,
        ):
            _registry(tmp_path, FILE_CONFIG).create_adapter("google")
        assert "adc.json" in str(caught.value)
        assert "credentials_file" in str(caught.value)

    def test_an_unreadable_file_is_a_configuration_error_naming_the_path(
        self, tmp_path: Path
    ) -> None:
        with (
            patch(_LOAD, side_effect=DefaultCredentialsError("bad json")),
            pytest.raises(ConfigurationError, match=r"adc\.json"),
        ):
            _registry(tmp_path, FILE_CONFIG).create_adapter("google")

    def test_has_credentials_follows_the_file(self, tmp_path: Path) -> None:
        registry = _registry(tmp_path, FILE_CONFIG)
        with patch(_LOAD, return_value=(MagicMock(), None)), patch(_ADC) as default:
            assert registry.has_credentials("google")
        default.assert_not_called()
        with (
            patch(_LOAD, side_effect=FileNotFoundError("x")),
            patch(_ADC, return_value=(MagicMock(), "p")),
        ):
            assert not registry.has_credentials("google")

    def test_without_the_key_default_credentials_are_used(self, tmp_path: Path) -> None:
        with patch(_LOAD) as load, patch(_ADC, return_value=(MagicMock(), "p")):
            kwargs = _client_kwargs(_registry(tmp_path, VERTEX_CONFIG))
        load.assert_not_called()
        assert "credentials" not in kwargs

    def test_credentials_file_must_be_a_string(self, tmp_path: Path) -> None:
        config = "[default.providers.google]\ncredentials_file = 3\n"
        with pytest.raises(ConfigurationError, match="credentials_file"):
            _registry(tmp_path, config)

    def test_the_key_is_not_reported_as_unknown(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            _registry(tmp_path, FILE_CONFIG)
        assert "Ignoring unknown key" not in caplog.text

    def test_the_missing_credentials_hint_stays_the_login_command(
        self, tmp_path: Path
    ) -> None:
        assert "gcloud auth application-default login" in _registry(
            tmp_path, FILE_CONFIG
        ).credential_hint("google")
