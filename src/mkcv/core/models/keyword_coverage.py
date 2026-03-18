"""Keyword coverage analysis model."""

from pydantic import BaseModel


class KeywordCoverage(BaseModel):
    """ATS keyword coverage analysis."""

    total_keywords: int
    matched_keywords: int
    coverage_percent: float
    missing_keywords: list[str]
    suggestions: list[str]
