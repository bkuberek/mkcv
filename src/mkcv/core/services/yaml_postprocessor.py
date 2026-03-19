"""YAML post-processing for design section injection."""

import logging
from io import StringIO
from typing import Any

from ruamel.yaml import YAML

from mkcv.core.models.resume_design import ResumeDesign

logger = logging.getLogger(__name__)


class YamlPostProcessor:
    """Post-processes LLM-generated YAML to inject/replace the design section.

    Uses ruamel.yaml for round-trip parsing to preserve comments and
    formatting in the cv: section while replacing the design: section
    with validated values.
    """

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def inject_design(
        self,
        yaml_str: str,
        design: ResumeDesign,
    ) -> str:
        """Replace or insert the design section in resume YAML.

        Delegates to ``ResumeDesign.to_rendercv_dict()`` which produces
        a RenderCV-compatible nested design dict, emitting only non-default
        values so that theme defaults are respected.

        Args:
            yaml_str: Raw YAML string from LLM or file.
            design: Validated design configuration to inject.

        Returns:
            Modified YAML string with the design section updated.

        Raises:
            ValueError: If yaml_str is not valid YAML.
        """
        if not yaml_str or not yaml_str.strip():
            raise ValueError("Empty or invalid YAML")

        data: dict[str, Any] | None = self._yaml.load(yaml_str)
        if data is None:
            raise ValueError("Empty or invalid YAML")

        data["design"] = design.to_rendercv_dict()

        stream = StringIO()
        self._yaml.dump(data, stream)
        return stream.getvalue()

    def inject_theme(
        self,
        yaml_str: str,
        theme: str,
    ) -> str:
        """Replace only the design.theme value, preserving other design fields.

        Convenience method for Phase 1 when only theme needs to be set.

        Args:
            yaml_str: Raw YAML string.
            theme: Theme name to inject.

        Returns:
            Modified YAML string.

        Raises:
            ValueError: If yaml_str is not valid YAML.
        """
        if not yaml_str or not yaml_str.strip():
            raise ValueError("Empty or invalid YAML")

        data = self._yaml.load(yaml_str)
        if data is None:
            raise ValueError("Empty or invalid YAML")

        if "design" not in data:
            data["design"] = {}
        data["design"]["theme"] = theme

        stream = StringIO()
        self._yaml.dump(data, stream)
        return stream.getvalue()
