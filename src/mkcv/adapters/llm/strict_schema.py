"""Strict JSON schemas for OpenAI-style structured outputs.

OpenAI's ``strict: true`` mode accepts only a subset of JSON Schema: every
object must forbid extra properties and list all of its properties as
required, and optional fields are expressed as a union with ``null``.
``to_strict_json_schema`` rewrites a Pydantic model's schema to satisfy those
rules, and ``drop_nulls_for_defaulted_fields`` undoes the ``null`` the model
sends for fields that have a Pydantic default.
"""

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from mkcv.adapters.llm._utils import resolve_schema_refs

_ALLOWED_KEYWORDS = frozenset(
    {
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
)

_ALLOWED_FORMATS = frozenset(
    {
        "date-time",
        "time",
        "date",
        "duration",
        "email",
        "hostname",
        "ipv4",
        "ipv6",
        "uuid",
    }
)

_NULL_SCHEMA: dict[str, Any] = {"type": "null"}


def to_strict_json_schema(response_model: type[BaseModel]) -> dict[str, Any]:
    """Return ``response_model``'s JSON schema in OpenAI strict form.

    References are inlined, keywords outside the supported subset are
    dropped, every object forbids extra properties and requires all of its
    properties, and properties that were optional become nullable.
    """
    schema = resolve_schema_refs(response_model.model_json_schema())
    return _strictify(schema)


def drop_nulls_for_defaulted_fields(
    data: dict[str, Any], model: type[BaseModel]
) -> dict[str, Any]:
    """Return a copy of ``data`` without ``null`` values for defaulted fields.

    The strict schema makes every field nullable, so a model may send
    ``null`` for a field whose annotation does not allow it. Dropping those
    keys lets Pydantic apply the field default. Nested models and lists of
    models are cleaned recursively; ``null`` for a required field or for a
    field that allows ``None`` is left alone.
    """
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        field = model.model_fields.get(key)
        if field is None:
            cleaned[key] = value
        elif value is None and not field.is_required():
            if _allows_none(field.annotation):
                cleaned[key] = value
        else:
            cleaned[key] = _clean_value(value, field.annotation)
    return cleaned


def _strictify(node: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for keyword, value in node.items():
        if keyword not in _ALLOWED_KEYWORDS:
            continue
        if keyword == "format" and value not in _ALLOWED_FORMATS:
            continue
        result[keyword] = _strictify_value(keyword, value)

    if _is_object(result):
        _apply_object_rules(result, optional_names=_optional_names(node))
    return result


def _strictify_value(keyword: str, value: Any) -> Any:
    if keyword == "properties":
        return {name: _strictify(schema) for name, schema in value.items()}
    if keyword == "items" and isinstance(value, dict):
        return _strictify(value)
    if keyword == "anyOf":
        return [_strictify(branch) for branch in value]
    return value


def _is_object(node: dict[str, Any]) -> bool:
    node_type = node.get("type")
    types_ = node_type if isinstance(node_type, list) else [node_type]
    return "object" in types_ or "properties" in node


def _optional_names(node: dict[str, Any]) -> set[str]:
    required = set(node.get("required", ()))
    return {name for name in node.get("properties", {}) if name not in required}


def _apply_object_rules(node: dict[str, Any], *, optional_names: set[str]) -> None:
    properties: dict[str, Any] = node.setdefault("properties", {})
    node["properties"] = {
        name: _make_nullable(schema) if name in optional_names else schema
        for name, schema in properties.items()
    }
    node["required"] = list(node["properties"])
    node["additionalProperties"] = False


def _make_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if _allows_null(schema):
        return schema

    nullable = dict(schema)
    if isinstance(schema.get("type"), str):
        nullable["type"] = [schema["type"], "null"]
    elif isinstance(schema.get("type"), list):
        nullable["type"] = [*schema["type"], "null"]
    elif "anyOf" in schema:
        nullable["anyOf"] = [*schema["anyOf"], _NULL_SCHEMA]
    else:
        return {"anyOf": [schema, _NULL_SCHEMA]}

    if "enum" in nullable:
        nullable["enum"] = [*nullable["enum"], None]
    return nullable


def _allows_null(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    return any(_allows_null(branch) for branch in schema.get("anyOf", ()))


def _clean_value(value: Any, annotation: Any) -> Any:
    nested_model = _model_class(annotation)
    if nested_model is not None and isinstance(value, dict):
        return drop_nulls_for_defaulted_fields(value, nested_model)

    item_model = _list_item_model(annotation)
    if item_model is not None and isinstance(value, list):
        return [
            drop_nulls_for_defaulted_fields(item, item_model)
            if isinstance(item, dict)
            else item
            for item in value
        ]
    return value


def _allows_none(annotation: Any) -> bool:
    if annotation is None or annotation is type(None):
        return True
    return type(None) in _union_members(annotation)


def _union_members(annotation: Any) -> tuple[Any, ...]:
    if get_origin(annotation) in (Union, types.UnionType):
        return get_args(annotation)
    return ()


def _unwrap_optional(annotation: Any) -> Any:
    members = [m for m in _union_members(annotation) if m is not type(None)]
    return members[0] if len(members) == 1 else annotation


def _model_class(annotation: Any) -> type[BaseModel] | None:
    inner = _unwrap_optional(annotation)
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return inner
    return None


def _list_item_model(annotation: Any) -> type[BaseModel] | None:
    inner = _unwrap_optional(annotation)
    if get_origin(inner) is not list:
        return None
    arguments = get_args(inner)
    return _model_class(arguments[0]) if arguments else None
