"""Tests for the bundled settings.toml and hidden-default guards (REQ-SR-8)."""

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

import mkcv
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.stage_key import StageKey

PACKAGE_ROOT = Path(mkcv.__file__).resolve().parent
SETTINGS_PATH = PACKAGE_ROOT / "config" / "settings.toml"
FACTORY_PATH = PACKAGE_ROOT / "adapters" / "factory.py"
RESOLVER_PATH = PACKAGE_ROOT / "adapters" / "llm" / "stage_resolver.py"

_PROVIDER_OR_MODEL_KEY = re.compile(r"^\s*(provider|model)\s*=", re.MULTILINE)
_HIDDEN_DEFAULT = re.compile(r"\"anthropic\"|claude-")


@pytest.fixture(scope="module")
def defaults() -> dict[str, Any]:
    document = tomllib.loads(SETTINGS_PATH.read_text())
    section: dict[str, Any] = document["default"]
    return section


def _section(defaults: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    node: Any = defaults
    for part in dotted_path.split("."):
        node = node[part]
    assert isinstance(node, dict)
    return node


class TestTemperatures:
    @pytest.mark.parametrize("stage", list(StageKey))
    def test_bundled_temperature_equals_the_stage_requirement(
        self, defaults: dict[str, Any], stage: StageKey
    ) -> None:
        requirement = STAGE_REQUIREMENTS[stage]
        section = _section(defaults, requirement.config_path)
        assert section["temperature"] == requirement.default_temperature


class TestNoHiddenModelDefaults:
    def test_settings_do_not_set_provider_or_model_outside_comments(self) -> None:
        assert _PROVIDER_OR_MODEL_KEY.findall(SETTINGS_PATH.read_text()) == []

    @pytest.mark.parametrize("stage", list(StageKey))
    def test_no_stage_section_names_a_provider_or_model(
        self, defaults: dict[str, Any], stage: StageKey
    ) -> None:
        section = _section(defaults, STAGE_REQUIREMENTS[stage].config_path)
        assert {"provider", "model"}.isdisjoint(section)

    def test_factory_has_no_provider_or_model_literals(self) -> None:
        assert _HIDDEN_DEFAULT.findall(FACTORY_PATH.read_text()) == []

    def test_default_provider_is_defined_only_in_the_stage_resolver(self) -> None:
        definitions = [
            path
            for path in PACKAGE_ROOT.rglob("*.py")
            if re.search(r"^DEFAULT_PROVIDER\s*[:=]", path.read_text(), re.MULTILINE)
        ]
        assert definitions == [RESOLVER_PATH]


class TestSettingsKeepTheirOtherKeys:
    def test_kb_keeps_its_limits(self, defaults: dict[str, Any]) -> None:
        kb = _section(defaults, "kb")
        assert (kb["max_tokens"], kb["chunk_threshold"]) == (8192, 100000)

    def test_pipeline_keeps_its_flags(self, defaults: dict[str, Any]) -> None:
        pipeline = _section(defaults, "pipeline")
        assert (
            pipeline["from_stage"],
            pipeline["auto_render"],
            pipeline["interactive"],
        ) == (1, True, False)

    def test_model_warnings_are_on_by_default(self, defaults: dict[str, Any]) -> None:
        assert _section(defaults, "pipeline")["model_warnings"] is True

    def test_cover_letter_keeps_auto_render(self, defaults: dict[str, Any]) -> None:
        assert _section(defaults, "cover_letter")["auto_render"] is True

    def test_validate_section_exists(self, defaults: dict[str, Any]) -> None:
        assert _section(defaults, "validate") == {"temperature": 0.3}

    def test_profile_and_provider_keys_are_only_documented_in_comments(self) -> None:
        text = SETTINGS_PATH.read_text()
        assert "# provider = " in text
        assert "# model_profile = " in text
