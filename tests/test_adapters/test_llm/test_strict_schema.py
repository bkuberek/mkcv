"""Tests for the OpenAI strict JSON-schema transformer (REQ-OAI-11)."""

import copy
import json
from collections.abc import Iterator
from datetime import date
from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field

from mkcv.adapters.llm.strict_schema import (
    drop_nulls_for_defaulted_fields,
    to_strict_json_schema,
)
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.cover_letter_review import CoverLetterReview
from mkcv.core.models.earlier_experience_section import EarlierExperienceSection
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.jd_frontmatter import JDFrontmatter
from mkcv.core.models.languages_section import LanguagesSection
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.skills_section import SkillsSection
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole

# Every model passed as ``response_model`` to ``complete_structured``
# (``rg -n "response_model=" src/mkcv/core/services``).
RESPONSE_MODELS: list[type[BaseModel]] = [
    JDAnalysis,
    ExperienceSelection,
    TailoredContent,
    ReviewReport,
    JDFrontmatter,
    CoverLetter,
    CoverLetterReview,
    MissionStatement,
    SkillsSection,
    TailoredRole,
    EarlierExperienceSection,
    LanguagesSection,
]

ALLOWED_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "anyOf",
    "description",
    "title",
    "pattern",
    "format",
    "multipleOf",
    "maximum",
    "exclusiveMaximum",
    "minimum",
    "exclusiveMinimum",
    "minItems",
    "maxItems",
}
MAX_NESTING_DEPTH = 10
MAX_TOTAL_PROPERTIES = 5000


class Item(BaseModel):
    label: str


class Sample(BaseModel):
    name: str
    note: str = "x"
    count: int | None = None
    items: list[Item] = Field(default_factory=list)


def _children(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield the sub-schemas of a schema node (not property names)."""
    yield from node.get("properties", {}).values()
    items = node.get("items")
    if isinstance(items, dict):
        yield items
    yield from node.get("anyOf", [])


def _nodes(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in _children(node):
        yield from _nodes(child)


def _depth(node: dict[str, Any]) -> int:
    return 1 + max((_depth(child) for child in _children(node)), default=0)


def _property_count(schema: dict[str, Any]) -> int:
    return sum(len(node.get("properties", {})) for node in _nodes(schema))


def _is_object(node: dict[str, Any]) -> bool:
    node_type = node.get("type")
    types = node_type if isinstance(node_type, list) else [node_type]
    return "object" in types or "properties" in node


def _null_branches(node: dict[str, Any]) -> int:
    branches = node.get("anyOf", [node])
    return sum(1 for branch in branches if branch.get("type") == "null")


class TestStrictSchemaOverResponseModels:
    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_no_refs_or_defs_remain(self, model: type[BaseModel]) -> None:
        text = json.dumps(to_strict_json_schema(model))
        assert "$ref" not in text
        assert "$defs" not in text

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_every_object_forbids_extras_and_requires_every_property(
        self, model: type[BaseModel]
    ) -> None:
        schema = to_strict_json_schema(model)
        objects = [node for node in _nodes(schema) if _is_object(node)]
        assert objects
        for node in objects:
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_only_whitelisted_keywords_remain(self, model: type[BaseModel]) -> None:
        schema = to_strict_json_schema(model)
        used = {key for node in _nodes(schema) for key in node}
        assert used <= ALLOWED_KEYS

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_nesting_depth_is_within_the_documented_limit(
        self, model: type[BaseModel]
    ) -> None:
        assert _depth(to_strict_json_schema(model)) <= MAX_NESTING_DEPTH

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_total_property_count_is_within_the_documented_limit(
        self, model: type[BaseModel]
    ) -> None:
        assert _property_count(to_strict_json_schema(model)) <= MAX_TOTAL_PROPERTIES

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_root_is_a_plain_object(self, model: type[BaseModel]) -> None:
        schema = to_strict_json_schema(model)
        assert schema["type"] == "object"
        assert "anyOf" not in schema

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_property_order_follows_declaration_order(
        self, model: type[BaseModel]
    ) -> None:
        schema = to_strict_json_schema(model)
        assert list(schema["properties"]) == list(model.model_fields)

    @pytest.mark.parametrize("model", RESPONSE_MODELS, ids=lambda m: m.__name__)
    def test_schema_is_json_serializable(self, model: type[BaseModel]) -> None:
        assert json.loads(json.dumps(to_strict_json_schema(model)))


class TestOptionalFieldsBecomeNullable:
    def test_defaulted_string_is_nullable_and_required(self) -> None:
        schema = to_strict_json_schema(Sample)
        assert schema["properties"]["note"]["type"] == ["string", "null"]
        assert "note" in schema["required"]

    def test_required_string_stays_a_plain_string(self) -> None:
        assert to_strict_json_schema(Sample)["properties"]["name"]["type"] == "string"

    def test_already_nullable_field_allows_null_exactly_once(self) -> None:
        count = to_strict_json_schema(Sample)["properties"]["count"]
        assert _null_branches(count) == 1

    def test_defaulted_list_becomes_a_nullable_array(self) -> None:
        items = to_strict_json_schema(Sample)["properties"]["items"]
        assert items["type"] == ["array", "null"]

    def test_defaulted_list_items_are_still_strict_objects(self) -> None:
        items = to_strict_json_schema(Sample)["properties"]["items"]["items"]
        assert items["additionalProperties"] is False
        assert items["required"] == ["label"]

    def test_defaulted_nested_model_stays_a_strict_object(self) -> None:
        class Inner(BaseModel):
            value: str

        class Outer(BaseModel):
            inner: Inner = Inner(value="v")

        inner = to_strict_json_schema(Outer)["properties"]["inner"]
        assert inner["type"] == ["object", "null"]
        assert inner["additionalProperties"] is False
        assert inner["required"] == ["value"]

    def test_defaulted_enum_gains_a_null_value(self) -> None:
        class WithEnum(BaseModel):
            level: Literal["low", "high"] = "low"

        level = to_strict_json_schema(WithEnum)["properties"]["level"]
        assert level["type"] == ["string", "null"]
        assert level["enum"] == ["low", "high", None]

    def test_required_enum_is_left_alone(self) -> None:
        class WithEnum(BaseModel):
            level: Literal["low", "high"]

        level = to_strict_json_schema(WithEnum)["properties"]["level"]
        assert level["enum"] == ["low", "high"]

    def test_optional_union_with_defaulted_branch_keeps_one_null(self) -> None:
        class WithDate(BaseModel):
            posted: date | None = None

        posted = to_strict_json_schema(WithDate)["properties"]["posted"]
        assert _null_branches(posted) == 1


class TestKeywordHandling:
    def test_min_length_is_dropped(self) -> None:
        class Constrained(BaseModel):
            name: str = Field(min_length=3)

        assert (
            "minLength" not in to_strict_json_schema(Constrained)["properties"]["name"]
        )

    def test_max_length_is_dropped(self) -> None:
        class Constrained(BaseModel):
            name: str = Field(max_length=3)

        assert (
            "maxLength" not in to_strict_json_schema(Constrained)["properties"]["name"]
        )

    def test_default_values_are_dropped(self) -> None:
        assert "default" not in to_strict_json_schema(Sample)["properties"]["note"]

    @pytest.mark.parametrize(
        ("field", "keyword"),
        [
            (Field(ge=1), "minimum"),
            (Field(le=5), "maximum"),
            (Field(gt=0), "exclusiveMinimum"),
            (Field(lt=9), "exclusiveMaximum"),
            (Field(multiple_of=2), "multipleOf"),
        ],
    )
    def test_numeric_bounds_are_kept(self, field: Any, keyword: str) -> None:
        class Bounded(BaseModel):
            value: int = field

        assert keyword in to_strict_json_schema(Bounded)["properties"]["value"]

    def test_pattern_is_kept(self) -> None:
        class Patterned(BaseModel):
            code: str = Field(pattern=r"^[A-Z]+$")

        assert to_strict_json_schema(Patterned)["properties"]["code"]["pattern"]

    def test_array_size_bounds_are_kept(self) -> None:
        class Sized(BaseModel):
            tags: list[str] = Field(min_length=1, max_length=3)

        tags = to_strict_json_schema(Sized)["properties"]["tags"]
        assert (tags["minItems"], tags["maxItems"]) == (1, 3)

    def test_description_and_title_are_kept(self) -> None:
        class Described(BaseModel):
            name: str = Field(description="The name")

        name = to_strict_json_schema(Described)["properties"]["name"]
        assert name["description"] == "The name"
        assert name["title"] == "Name"

    def test_supported_format_is_kept(self) -> None:
        class Dated(BaseModel):
            day: date

        assert to_strict_json_schema(Dated)["properties"]["day"]["format"] == "date"

    def test_unsupported_format_is_dropped(self) -> None:
        class Linked(BaseModel):
            link: str = Field(json_schema_extra={"format": "uri"})

        assert "format" not in to_strict_json_schema(Linked)["properties"]["link"]

    def test_properties_named_like_keywords_are_not_filtered(self) -> None:
        class Tricky(BaseModel):
            title: str
            default: str
            format: str
            examples: list[str]

        properties = to_strict_json_schema(Tricky)["properties"]
        assert list(properties) == ["title", "default", "format", "examples"]

    def test_property_named_like_keyword_still_gets_strict_rules(self) -> None:
        class Tricky(BaseModel):
            default: str = "d"

        schema = to_strict_json_schema(Tricky)
        assert schema["required"] == ["default"]
        assert schema["properties"]["default"]["type"] == ["string", "null"]


class TestSchemaIsNotShared:
    def test_repeated_calls_return_equal_independent_schemas(self) -> None:
        first = to_strict_json_schema(Sample)
        second = to_strict_json_schema(Sample)
        first["properties"].clear()
        assert second == to_strict_json_schema(Sample)

    def test_model_schema_is_not_mutated(self) -> None:
        before = copy.deepcopy(Sample.model_json_schema())
        to_strict_json_schema(Sample)
        assert Sample.model_json_schema() == before


class Child(BaseModel):
    label: str
    flag: bool = True


class Parent(BaseModel):
    name: str
    nickname: str = "none"
    maybe: str | None = None
    child: Child = Child(label="c")
    maybe_child: Child | None = None
    children: list[Child] = Field(default_factory=list)


class TestDropNullsForDefaultedFields:
    def test_null_for_a_defaulted_field_is_dropped(self) -> None:
        cleaned = drop_nulls_for_defaulted_fields(
            {"name": "n", "nickname": None}, Parent
        )
        assert cleaned == {"name": "n"}

    def test_null_for_an_optional_field_is_kept(self) -> None:
        cleaned = drop_nulls_for_defaulted_fields({"name": "n", "maybe": None}, Parent)
        assert cleaned == {"name": "n", "maybe": None}

    def test_null_for_a_required_field_is_kept(self) -> None:
        cleaned = drop_nulls_for_defaulted_fields({"name": None}, Parent)
        assert cleaned == {"name": None}

    def test_non_null_values_are_kept(self) -> None:
        data = {"name": "n", "nickname": "nick"}
        assert drop_nulls_for_defaulted_fields(data, Parent) == data

    def test_unknown_keys_pass_through(self) -> None:
        cleaned = drop_nulls_for_defaulted_fields({"name": "n", "extra": None}, Parent)
        assert cleaned == {"name": "n", "extra": None}

    def test_nested_model_is_cleaned(self) -> None:
        data = {"name": "n", "child": {"label": "c", "flag": None}}
        assert drop_nulls_for_defaulted_fields(data, Parent)["child"] == {"label": "c"}

    def test_optional_nested_model_is_cleaned(self) -> None:
        data = {"name": "n", "maybe_child": {"label": "c", "flag": None}}
        cleaned = drop_nulls_for_defaulted_fields(data, Parent)
        assert cleaned["maybe_child"] == {"label": "c"}

    def test_null_optional_nested_model_stays_null(self) -> None:
        cleaned = drop_nulls_for_defaulted_fields(
            {"name": "n", "maybe_child": None}, Parent
        )
        assert cleaned["maybe_child"] is None

    def test_list_of_models_is_cleaned_item_by_item(self) -> None:
        data = {
            "name": "n",
            "children": [{"label": "a", "flag": None}, {"label": "b", "flag": False}],
        }
        cleaned = drop_nulls_for_defaulted_fields(data, Parent)
        assert cleaned["children"] == [{"label": "a"}, {"label": "b", "flag": False}]

    def test_input_is_not_mutated(self) -> None:
        data = {"name": "n", "nickname": None, "child": {"label": "c", "flag": None}}
        snapshot = copy.deepcopy(data)
        drop_nulls_for_defaulted_fields(data, Parent)
        assert data == snapshot

    def test_cleaned_data_validates_with_defaults_applied(self) -> None:
        data = {"name": "n", "nickname": None, "children": None}
        parent = Parent.model_validate(drop_nulls_for_defaulted_fields(data, Parent))
        assert (parent.nickname, parent.children) == ("none", [])
