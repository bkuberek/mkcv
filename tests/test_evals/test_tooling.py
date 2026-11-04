"""The eval harness stays out of the wheel and inside the quality gates (REQ-EV-1)."""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
CI_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
    encoding="utf-8"
)
GITIGNORE = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_the_wheel_packages_only_mkcv() -> None:
    wheel = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/mkcv"]


def test_pytest_can_import_the_evals_package() -> None:
    assert "." in PYPROJECT["tool"]["pytest"]["ini_options"]["pythonpath"]


def test_evals_is_first_party_for_import_sorting() -> None:
    isort = PYPROJECT["tool"]["ruff"]["lint"]["isort"]
    assert "evals" in isort["known-first-party"]


def test_mypy_checks_evals_by_default() -> None:
    assert "evals" in PYPROJECT["tool"]["mypy"]["files"]


def test_ci_lints_evals() -> None:
    assert "uv run ruff check src/ tests/ evals/" in CI_WORKFLOW


def test_ci_checks_evals_formatting() -> None:
    assert "uv run ruff format --check src/ tests/ evals/" in CI_WORKFLOW


def test_ci_type_checks_evals() -> None:
    assert "uv run mypy src/ evals/" in CI_WORKFLOW


def test_results_are_ignored_except_published_ones() -> None:
    assert "evals/results/*" in GITIGNORE
    assert "!evals/results/published/" in GITIGNORE
