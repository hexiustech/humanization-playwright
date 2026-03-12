"""Output JSON schemas and lightweight validation for extraction patterns."""

from typing import Any, Dict

from .exceptions import SchemaValidationError


SCHEMAS: Dict[str, dict] = {
    "table_data": {
        "type": "object",
        "properties": {
            "headers": {"type": "array", "items": {"type": "string"}},
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            },
        },
        "required": ["headers", "rows"],
    },
    "product_listing": {
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "string"},
                        "url": {"type": "string"},
                        "image_url": {"type": "string"},
                    },
                    "required": ["name"],
                },
            }
        },
        "required": ["products"],
    },
    "article_content": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "author": {"type": "string"},
            "date": {"type": "string"},
            "body": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "body"],
    },
    "link_list": {
        "type": "object",
        "properties": {
            "links": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "href": {"type": "string"},
                    },
                    "required": ["href"],
                },
            }
        },
        "required": ["links"],
    },
    "generic": {
        "type": "object",
        "properties": {
            "data": {},
        },
        "required": ["data"],
    },
}

# JSON type string → Python types mapping
_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def get_schema(pattern: str) -> dict:
    """Return the schema for a pattern, falling back to 'generic'."""
    return SCHEMAS.get(pattern, SCHEMAS["generic"])


def register_schema(pattern: str, schema: dict) -> None:
    """Register a custom schema for a new extraction pattern."""
    if not isinstance(schema, dict):
        raise TypeError("Schema must be a dict")
    SCHEMAS[pattern] = schema


def validate_output(data: Any, pattern: str) -> bool:
    """Validate extracted data against the pattern's schema.

    Checks: not None, not empty, required keys present, top-level types match.
    Returns True if valid, raises SchemaValidationError otherwise.
    """
    if data is None:
        raise SchemaValidationError("Extracted data is None")

    schema = get_schema(pattern)

    if isinstance(data, dict) and not data:
        raise SchemaValidationError("Extracted data is an empty dict")
    if isinstance(data, list) and not data:
        raise SchemaValidationError("Extracted data is an empty list")

    # Check required keys
    required = schema.get("required", [])
    if isinstance(data, dict):
        missing = [k for k in required if k not in data]
        if missing:
            raise SchemaValidationError(
                f"Missing required keys: {missing}"
            )

    # Check top-level property types
    properties = schema.get("properties", {})
    if isinstance(data, dict):
        for key, prop_schema in properties.items():
            if key not in data:
                continue
            expected_type_str = prop_schema.get("type")
            if expected_type_str and expected_type_str in _TYPE_MAP:
                expected = _TYPE_MAP[expected_type_str]
                if not isinstance(data[key], expected):
                    raise SchemaValidationError(
                        f"Key '{key}' expected type '{expected_type_str}', "
                        f"got {type(data[key]).__name__}"
                    )

    return True
