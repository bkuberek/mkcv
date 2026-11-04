"""Load eval cases and the model matrix from disk."""

import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evals.models.eval_case import EvalCase
from evals.models.matrix_config import MatrixConfig

CASES_FILE = "cases.toml"
ALL_CASES = "*"


def load_cases(fixtures_dir: Path) -> list[EvalCase]:
    """Return the cases defined in ``fixtures_dir/cases.toml``.

    Raises:
        FileNotFoundError: If ``cases.toml`` or a case's persona or job
            description file is missing.
        ValueError: If a case is invalid, a file is empty, or an ID repeats.
    """
    cases_file = fixtures_dir / CASES_FILE
    entries = _read_toml(cases_file).get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{CASES_FILE} must define at least one [[cases]] table")

    cases: list[EvalCase] = []
    for number, entry in enumerate(entries, start=1):
        case = _parse_case(number, entry, fixtures_dir)
        if any(existing.id == case.id for existing in cases):
            raise ValueError(f"Duplicate case id '{case.id}' in {CASES_FILE}")
        _require_text(case, "persona", case.persona_path)
        _require_text(case, "job description", case.jd_path)
        cases.append(case)
    return cases


def select_cases(cases: Sequence[EvalCase], selection: Sequence[str]) -> list[EvalCase]:
    """Return the cases named in ``selection`` (``"*"`` selects every case).

    Raises:
        ValueError: If a name matches no case.
    """
    if ALL_CASES in selection:
        return list(cases)

    by_id = {case.id: case for case in cases}
    unknown = [name for name in selection if name not in by_id]
    if unknown:
        known = ", ".join(by_id)
        raise ValueError(f"Unknown case(s): {', '.join(unknown)}. Known cases: {known}")
    return [by_id[name] for name in selection]


def load_matrix(path: Path) -> MatrixConfig:
    """Return the matrix defined in the TOML file at ``path``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not valid TOML or not a valid matrix.
    """
    raw = _read_toml(path)
    try:
        matrix = MatrixConfig.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"Invalid matrix {path.name}: {error}") from error
    if not matrix.models:
        raise ValueError(f"{path.name} must define at least one [[models]] table")
    return matrix


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path.name} is not valid TOML: {error}") from error


def _parse_case(number: int, entry: object, fixtures_dir: Path) -> EvalCase:
    if not isinstance(entry, dict):
        raise ValueError(f"Case #{number} in {CASES_FILE} must be a table")
    try:
        return EvalCase.model_validate({**entry, "fixtures_dir": fixtures_dir})
    except ValidationError as error:
        raise ValueError(f"Invalid case #{number} in {CASES_FILE}: {error}") from error


def _require_text(case: EvalCase, label: str, path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Case '{case.id}': {label} file not found: {path}")
    if not path.read_text(encoding="utf-8").strip():
        raise ValueError(f"Case '{case.id}': {label} file is empty: {path}")
