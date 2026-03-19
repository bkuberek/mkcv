"""Tests for knowledge base validation."""

from mkcv.core.services.kb_validator import validate_kb

# -------------------------------------------------------------------
# Fixtures: realistic KB content
# -------------------------------------------------------------------

VALID_KB = """\
# Jane Doe -- Career Knowledge Base

## Personal Information

| Field    | Value                |
|----------|----------------------|
| Name     | Jane Doe             |
| Email    | jane@example.com     |
| Phone    | 555-0100             |
| Location | San Francisco, CA    |
| LinkedIn | linkedin.com/in/jane |

## Professional Summary

Senior software engineer with 10+ years of experience building
scalable distributed systems and leading cross-functional teams.

## Technical Skills -- Master List

### Programming Languages
- Python, Go, Java, TypeScript

### Databases
- PostgreSQL, Redis, DynamoDB

## Career History -- Complete and Detailed

### Acme Corp -- Senior Software Engineer
**2020-01 to 2024-03** | San Francisco, CA

- Designed and implemented a real-time data pipeline processing 1M events/day
- Led migration from monolith to microservices, reducing deploy time by 70%
- Mentored 4 junior engineers through structured pairing sessions

### Widgets Inc -- Software Engineer
**2016-06 to 2019-12** | New York, NY

- Built REST API serving 50k requests/minute with 99.9% uptime
- Implemented CI/CD pipeline reducing release cycles from weekly to daily

## Education

### B.S. Computer Science -- MIT
**2012-2016**

## Key Achievements

- Promoted twice in 3 years at Acme Corp

## Projects

- Open source contributor to FastAPI

## Certifications

- AWS Solutions Architect Associate (2022)
"""

KB_MISSING_SECTIONS = """\
# John Smith -- Career Knowledge Base

## Professional Summary

Experienced engineer.

## Career History

### Company A -- Engineer
**2020-01 to 2024-01** | Remote

- Built things
- Shipped features
"""

KB_NO_DATES = """\
# No Dates KB

## Personal Information

| Name | Test |

## Summary

Test summary paragraph.

## Experience

### Company -- Role

- Did some work
- Built features

## Skills

- Python, Go

## Education

### B.S. CS -- University
"""

KB_NO_BULLETS = """\
# No Bullets KB

## Personal Information

| Name | Test |

## Summary

Test summary.

## Career History

### Company -- Role
2020-01 to 2024-01

Worked on projects and delivered results across multiple teams.

## Skills

- Python, Go

## Education

### B.S. CS -- University
2012-2016
"""


class TestValidateKBValid:
    """Tests for a well-formed knowledge base."""

    def test_valid_kb_is_valid(self) -> None:
        result = validate_kb(VALID_KB)
        assert result.is_valid is True

    def test_valid_kb_has_no_errors(self) -> None:
        result = validate_kb(VALID_KB)
        assert result.errors == []

    def test_valid_kb_finds_required_sections(self) -> None:
        result = validate_kb(VALID_KB)
        assert "Contact / Personal Info" in result.sections_found
        assert "Summary / Profile" in result.sections_found
        assert "Experience / Work History" in result.sections_found
        assert "Education" in result.sections_found
        assert "Skills" in result.sections_found

    def test_valid_kb_finds_optional_sections(self) -> None:
        result = validate_kb(VALID_KB)
        assert "Projects" in result.sections_found
        assert "Certifications" in result.sections_found

    def test_valid_kb_has_no_missing_sections(self) -> None:
        result = validate_kb(VALID_KB)
        assert result.sections_missing == []


class TestValidateKBEmpty:
    """Tests for empty knowledge base content."""

    def test_empty_kb_is_invalid(self) -> None:
        result = validate_kb("")
        assert result.is_valid is False

    def test_empty_kb_has_error(self) -> None:
        result = validate_kb("")
        assert len(result.errors) == 1
        assert "empty" in result.errors[0].lower()

    def test_whitespace_only_kb_is_invalid(self) -> None:
        result = validate_kb("   \n\n  \t  ")
        assert result.is_valid is False


class TestValidateKBNoHeadings:
    """Tests for KB content with no Markdown headings."""

    def test_no_headings_is_invalid(self) -> None:
        content = "Just some plain text without any headings.\n\nMore text."
        result = validate_kb(content)
        assert result.is_valid is False

    def test_no_headings_reports_error(self) -> None:
        content = "Just some plain text without any headings.\n\nMore text."
        result = validate_kb(content)
        assert any("heading" in e.lower() for e in result.errors)


class TestValidateKBMissingSections:
    """Tests for KB missing recommended sections."""

    def test_missing_sections_still_valid(self) -> None:
        result = validate_kb(KB_MISSING_SECTIONS)
        assert result.is_valid is True

    def test_missing_sections_generates_warnings(self) -> None:
        result = validate_kb(KB_MISSING_SECTIONS)
        assert len(result.warnings) > 0

    def test_missing_sections_listed(self) -> None:
        result = validate_kb(KB_MISSING_SECTIONS)
        assert "Contact / Personal Info" in result.sections_missing
        assert "Skills" in result.sections_missing
        assert "Education" in result.sections_missing

    def test_found_sections_listed(self) -> None:
        result = validate_kb(KB_MISSING_SECTIONS)
        assert "Summary / Profile" in result.sections_found
        assert "Experience / Work History" in result.sections_found


class TestValidateKBExperienceDates:
    """Tests for date detection in experience sections."""

    def test_experience_without_dates_warns(self) -> None:
        result = validate_kb(KB_NO_DATES)
        assert any("year" in w.lower() or "date" in w.lower() for w in result.warnings)

    def test_experience_with_dates_no_date_warning(self) -> None:
        result = validate_kb(VALID_KB)
        assert not any(
            "year" in w.lower() and "experience" in w.lower() for w in result.warnings
        )


class TestValidateKBExperienceBullets:
    """Tests for bullet point detection in experience sections."""

    def test_experience_without_bullets_warns(self) -> None:
        result = validate_kb(KB_NO_BULLETS)
        assert any("bullet" in w.lower() for w in result.warnings)

    def test_experience_with_bullets_no_bullet_warning(self) -> None:
        result = validate_kb(VALID_KB)
        assert not any("bullet" in w.lower() for w in result.warnings)


class TestValidateKBLength:
    """Tests for KB length validation."""

    def test_short_kb_warns(self) -> None:
        content = "# Short KB\n\n## Summary\n\nToo short."
        result = validate_kb(content)
        assert any("short" in w.lower() for w in result.warnings)

    def test_long_kb_warns(self) -> None:
        content = "# Long KB\n\n## Summary\n\n" + ("x" * 60_000)
        result = validate_kb(content)
        assert any("long" in w.lower() for w in result.warnings)

    def test_normal_length_no_length_warning(self) -> None:
        result = validate_kb(VALID_KB)
        assert not any(
            "short" in w.lower() or "long" in w.lower() for w in result.warnings
        )


class TestValidateKBModel:
    """Tests for the KBValidationResult model structure."""

    def test_result_has_all_fields(self) -> None:
        result = validate_kb(VALID_KB)
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.warnings, list)
        assert isinstance(result.errors, list)
        assert isinstance(result.sections_found, list)
        assert isinstance(result.sections_missing, list)

    def test_result_serializes_to_dict(self) -> None:
        result = validate_kb(VALID_KB)
        data = result.model_dump()
        assert "is_valid" in data
        assert "warnings" in data
        assert "errors" in data
        assert "sections_found" in data
        assert "sections_missing" in data
