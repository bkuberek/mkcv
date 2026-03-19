"""Tests for TailoredRole model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_role import TailoredRole


def _make_bullet(original: str = "Built platform") -> TailoredBullet:
    return TailoredBullet(
        original=original,
        rewritten="Engineered scalable platform",
        keywords_incorporated=["scalable"],
        confidence="high",
    )


class TestTailoredRole:
    """Tests for TailoredRole model."""

    def test_valid_creation(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        assert role.company == "Acme Corp"

    def test_position_field(self) -> None:
        role = TailoredRole(
            company="DeepL",
            position="ML Engineer",
            start_date="2019-03",
            end_date="2023-12",
            bullets=[_make_bullet()],
        )
        assert role.position == "ML Engineer"

    def test_location_defaults_to_none(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        assert role.location is None

    def test_location_with_value(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            location="San Francisco, CA",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        assert role.location == "San Francisco, CA"

    def test_summary_defaults_to_none(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        assert role.summary is None

    def test_summary_with_value(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-06",
            summary="Led platform engineering team",
            bullets=[_make_bullet()],
        )
        assert role.summary == "Led platform engineering team"

    def test_tech_stack_defaults_to_none(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        assert role.tech_stack is None

    def test_tech_stack_with_value(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
            tech_stack="Python, PostgreSQL, Kubernetes",
        )
        assert role.tech_stack == "Python, PostgreSQL, Kubernetes"

    def test_multiple_bullets(self) -> None:
        bullets = [
            _make_bullet("Built platform"),
            _make_bullet("Led migration"),
            _make_bullet("Improved performance"),
        ]
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=bullets,
        )
        assert len(role.bullets) == 3

    def test_company_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredRole(
                position="Engineer",  # type: ignore[call-arg]
                start_date="2020-01",
                end_date="2024-06",
                bullets=[_make_bullet()],
            )

    def test_bullets_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredRole(
                company="Acme Corp",  # type: ignore[call-arg]
                position="Engineer",
                start_date="2020-01",
                end_date="2024-06",
            )

    def test_model_dump_includes_all_fields(self) -> None:
        role = TailoredRole(
            company="Acme Corp",
            position="Engineer",
            start_date="2020-01",
            end_date="2024-06",
            bullets=[_make_bullet()],
        )
        data = role.model_dump()
        expected_keys = {
            "company",
            "position",
            "location",
            "start_date",
            "end_date",
            "summary",
            "bullets",
            "tech_stack",
        }
        assert set(data.keys()) == expected_keys
