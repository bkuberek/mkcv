"""Tests for JD-related models (Compensation, JDFrontmatter, JDDocument)."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from mkcv.core.models.compensation import Compensation
from mkcv.core.models.jd_document import JDDocument
from mkcv.core.models.jd_frontmatter import JDFrontmatter


class TestCompensation:
    """Tests for the Compensation model."""

    def test_compensation_all_none_defaults(self) -> None:
        comp = Compensation()
        assert comp.base is None
        assert comp.equity is None
        assert comp.bonus is None
        assert comp.total is None

    def test_compensation_with_all_fields(self) -> None:
        comp = Compensation(
            base="$150k-$200k",
            equity="0.5%",
            bonus="15%",
            total="$250k",
        )
        assert comp.base == "$150k-$200k"
        assert comp.equity == "0.5%"
        assert comp.bonus == "15%"
        assert comp.total == "$250k"

    def test_compensation_partial_fields(self) -> None:
        comp = Compensation(base="$150k")
        assert comp.base == "$150k"
        assert comp.equity is None
        assert comp.bonus is None
        assert comp.total is None


class TestJDFrontmatter:
    """Tests for the JDFrontmatter model."""

    def test_all_defaults_are_none(self) -> None:
        fm = JDFrontmatter()
        assert fm.company is None
        assert fm.position is None
        assert fm.url is None
        assert fm.location is None
        assert fm.workplace is None
        assert fm.compensation is None
        assert fm.posted_date is None
        assert fm.source is None

    def test_with_all_fields(self) -> None:
        fm = JDFrontmatter(
            company="Acme Corp",
            position="Senior Engineer",
            url="https://acme.com/jobs/123",
            location="San Francisco, CA",
            workplace="remote",
            compensation=Compensation(base="$200k"),
            posted_date=date(2026, 3, 15),
            source="linkedin",
            tags=["python", "backend"],
        )
        assert fm.company == "Acme Corp"
        assert fm.position == "Senior Engineer"
        assert fm.workplace == "remote"
        assert fm.tags == ["python", "backend"]

    def test_unknown_fields_silently_ignored(self) -> None:
        fm = JDFrontmatter(company="Acme", unknown_field="x")  # type: ignore[call-arg]
        assert fm.company == "Acme"
        assert not hasattr(fm, "unknown_field")

    def test_invalid_workplace_set_to_none(self) -> None:
        fm = JDFrontmatter(workplace="office")
        assert fm.workplace is None

    def test_valid_workplace_values(self) -> None:
        for val in ("remote", "hybrid", "onsite"):
            fm = JDFrontmatter(workplace=val)
            assert fm.workplace == val

    def test_workplace_case_insensitive(self) -> None:
        fm = JDFrontmatter(workplace="Remote")
        assert fm.workplace == "remote"

    def test_tags_default_to_empty_list(self) -> None:
        fm = JDFrontmatter()
        assert fm.tags == []


class TestJDDocument:
    """Tests for the JDDocument model."""

    def test_body_only(self) -> None:
        doc = JDDocument(body="Senior Engineer at Acme Corp")
        assert doc.body == "Senior Engineer at Acme Corp"
        assert doc.metadata is None
        assert doc.source_path is None

    def test_body_with_metadata(self) -> None:
        fm = JDFrontmatter(company="Acme")
        doc = JDDocument(metadata=fm, body="Job description text")
        assert doc.metadata is not None
        assert doc.metadata.company == "Acme"
        assert doc.body == "Job description text"

    def test_empty_body_rejected(self) -> None:
        with pytest.raises(ValidationError, match="body must not be empty"):
            JDDocument(body="")

    def test_whitespace_body_rejected(self) -> None:
        with pytest.raises(ValidationError, match="body must not be empty"):
            JDDocument(body="  \n  ")

    def test_source_path_optional(self) -> None:
        doc = JDDocument(body="test", source_path=Path("/tmp/jd.txt"))
        assert doc.source_path == Path("/tmp/jd.txt")
