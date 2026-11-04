"""What the deterministic faithfulness check found in one reference artifact."""

from typing import Any

from pydantic import BaseModel, Field


class ReferenceFinding(BaseModel):
    """One reference file of one case, and the claims the KB does not support.

    ``probe`` marks a hand-written probe file, whose defects are planted on
    purpose.
    """

    case_id: str
    artifact: str
    violations: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    probe: bool = False

    @property
    def flagged(self) -> bool:
        """True when the file needs a person's attention before it is committed."""
        return not self.probe and (bool(self.violations) or self.error is not None)
