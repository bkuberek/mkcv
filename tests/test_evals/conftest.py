"""Shared fixtures for the eval harness tests.

Every test runs without provider credentials, so nothing can reach a real
provider even by accident (design section 9.10).
"""

import shutil
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
from dynaconf import Dynaconf
from pydantic import BaseModel

import mkcv
from evals.models.eval_case import REFERENCE_FILES, EvalCase
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.llm import LLMPort

_BUNDLED_SETTINGS = Path(mkcv.__file__).resolve().parent / "config" / "settings.toml"
_KEY_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
)

RECORDED_DIR = (
    Path(__file__).parent / "fixtures" / "recorded" / "backend-platform-match"
)
RESUME_YAML = (RECORDED_DIR / "resume.yaml").read_text(encoding="utf-8")
REVIEW_REPORT = ReviewReport.model_validate(
    {
        "overall_score": 88,
        "bullet_reviews": [
            {"bullet_text": "Cut p99 latency by 40%", "classification": "faithful"}
        ],
        "keyword_coverage": {
            "total_keywords": 6,
            "matched_keywords": 6,
            "coverage_percent": 100.0,
            "missing_keywords": [],
            "suggestions": [],
        },
        "ats_check": {
            "single_column": True,
            "no_tables": True,
            "no_text_boxes": True,
            "standard_headings": True,
            "contact_in_body": True,
            "standard_bullets": True,
            "standard_fonts": True,
            "text_extractable": True,
            "reading_order_correct": True,
            "overall_pass": True,
            "issues": [],
        },
        "tone_consistency": "Consistent.",
        "section_balance": "Balanced.",
        "length_assessment": "One page.",
        "top_suggestions": ["Add a link to a public repository."],
        "low_confidence_items": [],
    }
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


def recorded(model_class: type[BaseModel]) -> BaseModel:
    """Load the recorded stage artifact that ``model_class`` describes."""
    names = {
        JDAnalysis: "stage1_analysis.json",
        ExperienceSelection: "stage2_selection.json",
        TailoredContent: "stage3_content.json",
    }
    text = (RECORDED_DIR / names[model_class]).read_text(encoding="utf-8")
    return model_class.model_validate_json(text)


@pytest.fixture
def canned_stub() -> StubLLMAdapter:
    """A stub that answers every stage with the recorded artifacts."""
    return StubLLMAdapter(
        default_response=RESUME_YAML,
        responses={
            JDAnalysis: recorded(JDAnalysis),
            ExperienceSelection: recorded(ExperienceSelection),
            TailoredContent: recorded(TailoredContent),
            ReviewReport: REVIEW_REPORT,
        },
    )


@pytest.fixture
def install_adapter(monkeypatch: pytest.MonkeyPatch) -> Callable[[LLMPort], LLMPort]:
    """Make the provider registry hand out ``adapter`` for every provider."""

    def _install(adapter: LLMPort) -> LLMPort:
        monkeypatch.setattr(
            ProviderRegistry,
            "create_adapter",
            lambda self, name, *, with_retry=True: adapter,
        )
        return adapter

    return _install


@pytest.fixture
def add_reference() -> Callable[..., None]:
    """Copy the recorded artifacts into a case's reference directory."""

    def _add(
        case: EvalCase, stages: Iterable[StageKey] = tuple(REFERENCE_FILES)
    ) -> None:
        case.reference_dir.mkdir(parents=True, exist_ok=True)
        for stage in stages:
            for name in REFERENCE_FILES[stage]:
                shutil.copy(RECORDED_DIR / name, case.reference_dir / name)

    return _add


class FailingStub(StubLLMAdapter):
    """A stub whose structured calls raise a provider error."""

    async def complete_structured(self, *args: Any, **kwargs: Any) -> BaseModel:
        raise ProviderError("boom")


class UsageStub(StubLLMAdapter):
    """A stub that reports fixed token usage after every call."""

    def get_last_usage(self) -> TokenUsage:
        return TokenUsage(input_tokens=1000, output_tokens=500)
