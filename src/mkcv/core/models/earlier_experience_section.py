"""Earlier experience section wrapper model for structured LLM output."""

from pydantic import BaseModel


class EarlierExperienceSection(BaseModel):
    """Wrapper for earlier experience text, used for structured LLM output.

    The ``complete_structured`` method requires a single ``BaseModel`` class.
    This wrapper provides the required top-level model for the earlier
    experience section, which is a single text string.
    """

    earlier_experience: str
