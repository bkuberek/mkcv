"""Languages section wrapper model for structured LLM output."""

from pydantic import BaseModel


class LanguagesSection(BaseModel):
    """Wrapper for a list of language strings, used for structured LLM output.

    The ``complete_structured`` method requires a single ``BaseModel`` class,
    but the languages section is a ``list[str]``. This wrapper provides
    the required top-level model.
    """

    languages: list[str]
