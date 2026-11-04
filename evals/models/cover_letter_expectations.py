"""What a case expects of a cover letter: ``[cases.cover_letter]``."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CoverLetterExpectations(BaseModel):
    """The checks a cover letter written for one case must pass.

    ``company`` and ``role`` default to the ones the case's reference JD
    analysis names. ``must_not_claim`` adds to the case's ``forbidden_claims``,
    which the letter must not claim either. ``should_connect`` lists the
    knowledge base evidence a strong letter ties to the job's top needs; the
    judge sees it as guidance. ``review_defects`` makes the case a cover
    letter review probe: its reference ``cover_letter_content.json`` is
    written by hand with those defects planted in it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    company: str | None = Field(
        default=None, description="The company the letter must name"
    )
    role: str | None = Field(default=None, description="The role the letter must name")
    must_not_claim: list[str] = Field(
        default_factory=list,
        description="Terms or claims absent from the knowledge base",
    )
    should_connect: list[str] = Field(
        default_factory=list,
        description="Knowledge base evidence a strong letter connects to the job",
    )
    min_words: int = Field(default=250, ge=1)
    max_words: int = Field(default=400, ge=1)
    review_defects: list[str] = Field(
        default_factory=list,
        description="Defects planted in the hand-written reference letter",
    )

    @model_validator(mode="after")
    def _word_bounds_in_order(self) -> "CoverLetterExpectations":
        if self.min_words > self.max_words:
            raise ValueError("min_words must not exceed max_words")
        return self
