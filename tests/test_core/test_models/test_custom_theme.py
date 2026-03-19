"""Tests for CustomTheme model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.custom_theme import CustomTheme


class TestCustomThemeValid:
    """Tests for valid CustomTheme creation."""

    def test_valid_custom_theme(self) -> None:
        theme = CustomTheme(
            name="mytheme",
            extends="classic",
            description="My custom theme",
            overrides={"font": "Charter"},
        )
        assert theme.name == "mytheme"
        assert theme.extends == "classic"
        assert theme.overrides["font"] == "Charter"

    def test_extends_defaults_to_classic(self) -> None:
        theme = CustomTheme(name="mytheme")
        assert theme.extends == "classic"

    def test_overrides_is_optional(self) -> None:
        theme = CustomTheme(name="mytheme")
        assert theme.overrides == {}

    def test_applies_to_defaults_to_all(self) -> None:
        theme = CustomTheme(name="mytheme")
        assert theme.applies_to == "all"

    def test_applies_to_accepts_resume(self) -> None:
        theme = CustomTheme(name="mytheme", applies_to="resume")
        assert theme.applies_to == "resume"

    def test_applies_to_accepts_cover_letter(self) -> None:
        theme = CustomTheme(name="mytheme", applies_to="cover_letter")
        assert theme.applies_to == "cover_letter"


class TestCustomThemeNameValidation:
    """Tests for name validation."""

    def test_name_validation_rejects_uppercase(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="MyTheme")

    def test_name_validation_rejects_special_chars(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="my_theme!")

    def test_name_validation_accepts_hyphens(self) -> None:
        theme = CustomTheme(name="my-theme")
        assert theme.name == "my-theme"

    def test_name_must_start_with_letter(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="1theme")

    def test_name_rejects_underscore(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="my_theme")


class TestCustomThemeAppliesToValidation:
    """Tests for applies_to field validation."""

    def test_applies_to_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="mytheme", applies_to="both")  # type: ignore[arg-type]

    def test_applies_to_rejects_pdf(self) -> None:
        with pytest.raises(ValidationError):
            CustomTheme(name="mytheme", applies_to="pdf")  # type: ignore[arg-type]
