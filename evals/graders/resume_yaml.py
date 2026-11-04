"""Read a stage 4 ``resume.yaml`` the way the graders need it."""

from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def load_cv(text: str) -> dict[str, Any]:
    """Return the ``cv`` mapping of RenderCV YAML ``text``.

    Dates such as ``2021-03`` load as strings (the safe loader reads only full
    ISO dates as dates).

    Raises:
        ValueError: If the text is not YAML or has no ``cv`` mapping.
    """
    try:
        document = YAML(typ="safe").load(text)
    except YAMLError as error:
        raise ValueError(f"not valid YAML: {_first_line(str(error))}") from error
    if not isinstance(document, dict):
        raise ValueError("the YAML document is not a mapping")
    cv = document.get("cv")
    if not isinstance(cv, dict):
        raise ValueError("the YAML document has no cv mapping")
    return cv


def structure_problems(cv: dict[str, Any]) -> list[str]:
    """Return what is missing from ``cv`` for it to be a usable resume."""
    problems: list[str] = []
    name = cv.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("cv.name must be a non-empty string")
    sections = cv.get("sections")
    if not isinstance(sections, dict) or not sections:
        problems.append("cv.sections must be a non-empty mapping")
    return problems


def _first_line(text: str) -> str:
    stripped = text.strip()
    return stripped.splitlines()[0] if stripped else "empty document"
