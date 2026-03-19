"""YAML post-processing for design section injection."""

import logging
from io import StringIO
from typing import Any

from ruamel.yaml import YAML

from mkcv.core.models.resume_design import PAGE_SIZE_MAP, ResumeDesign

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

        data = self._yaml.load(yaml_str)
        if data is None:
            raise ValueError("Empty or invalid YAML")

        # Build the design dict matching RenderCV schema
        design_dict: dict[str, Any] = {"theme": design.theme}

        if design.has_overrides():
            defaults = ResumeDesign()
            if design.font != defaults.font:
                design_dict["font"] = design.font
            if design.font_size != defaults.font_size:
                design_dict["font_size"] = design.font_size
            if design.page_size != defaults.page_size:
                design_dict["page_size"] = PAGE_SIZE_MAP.get(
                    design.page_size, design.page_size
                )
            if design.colors.get("primary") != defaults.colors.get("primary"):
                design_dict["color"] = design.colors.get("primary", "003366")

        data["design"] = design_dict

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
