"""What happened when one case's reference artifacts were produced."""

from typing import Literal

from pydantic import BaseModel


class ReferenceOutcome(BaseModel):
    """The result of bootstrapping one case: written, skipped, or failed."""

    case_id: str
    status: Literal["written", "skipped", "error"]
    detail: str = ""
