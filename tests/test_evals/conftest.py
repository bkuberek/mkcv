"""Shared fixtures for the eval harness tests.

Every test runs without provider credentials, so nothing can reach a real
provider even by accident (design section 9.10).
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from dynaconf import Dynaconf

import mkcv

_BUNDLED_SETTINGS = Path(mkcv.__file__).resolve().parent / "config" / "settings.toml"
_KEY_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
)

PERSONA_TEXT = "# Alex Example\n\n## Professional Summary\nBackend engineer.\n"
JD_TEXT = "Platform Engineer at Acme Corp\n\nRequires Kubernetes and Go.\n"
CASES_TOML = """
[[cases]]
id = "alpha-match"
persona = "personas/alpha.md"
jd = "jds/alpha-match.md"
expected_keywords = ["Kubernetes", "Go"]

[[cases]]
id = "alpha-probe"
persona = "personas/alpha.md"
jd = "jds/alpha-match.md"
forbidden_claims = ["PyTorch"]
review_probe_defects = ["first-person pronoun in a bullet"]
stages = ["review"]
"""


@pytest.fixture(autouse=True)
def _no_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _KEY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def tmp_fixtures(tmp_path: Path) -> Path:
    """A fixtures directory with a two-case ``cases.toml`` and tiny files."""
    fixtures = tmp_path / "fixtures"
    (fixtures / "personas").mkdir(parents=True)
    (fixtures / "jds").mkdir()
    (fixtures / "personas" / "alpha.md").write_text(PERSONA_TEXT, encoding="utf-8")
    (fixtures / "jds" / "alpha-match.md").write_text(JD_TEXT, encoding="utf-8")
    (fixtures / "cases.toml").write_text(CASES_TOML, encoding="utf-8")
    return fixtures


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Dynaconf]:
    """Build real Dynaconf settings: the bundled defaults plus an optional layer."""

    def _make(user_toml: str = "") -> Dynaconf:
        layers = [str(_BUNDLED_SETTINGS)]
        if user_toml:
            user_file = tmp_path / "user-settings.toml"
            user_file.write_text(user_toml, encoding="utf-8")
            layers.append(str(user_file))
        config = Dynaconf(
            settings_files=layers,
            environments=True,
            default_env="default",
            merge_enabled=True,
        )
        config.set("in_workspace", False)
        config.set("workspace_root", None)
        return config

    return _make
