"""Shared validators for layout and design models."""

import re

DIMENSION_PATTERN = re.compile(r"^\d+(\.\d+)?(in|cm|mm|pt|em)$")


def validate_dimension(value: str | None) -> str | None:
    """Validate a Typst/RenderCV dimension string.

    Accepts values like "0.5in", "1cm", "10pt", "0.7em".
    Returns None unchanged (meaning "use theme default").

    Raises:
        ValueError: If the value doesn't match the dimension pattern.
    """
    if value is None:
        return None
    if not DIMENSION_PATTERN.match(value):
        raise ValueError(
            f"Invalid dimension '{value}'. "
            f"Must match pattern like '0.5in', '1cm', '10pt', '0.7em'."
        )
    return value
