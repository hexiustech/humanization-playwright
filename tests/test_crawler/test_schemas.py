"""Tests for schema validation."""

import pytest

from humanization.crawler.schemas import (
    validate_output,
    get_schema,
    register_schema,
    SCHEMAS,
)
from humanization.crawler.exceptions import SchemaValidationError


def test_validate_valid_table_data():
    data = {"headers": ["Name", "Age"], "rows": [["Alice", "30"]]}
    assert validate_output(data, "table_data") is True


def test_validate_valid_product_listing():
    data = {"products": [{"name": "Widget", "price": "$10"}]}
    assert validate_output(data, "product_listing") is True


def test_validate_valid_article_content():
    data = {"title": "Hello", "body": "World"}
    assert validate_output(data, "article_content") is True


def test_validate_valid_link_list():
    data = {"links": [{"href": "https://example.com", "text": "Example"}]}
    assert validate_output(data, "link_list") is True


def test_validate_valid_generic():
    data = {"data": "anything"}
    assert validate_output(data, "generic") is True


def test_validate_none_raises():
    with pytest.raises(SchemaValidationError, match="None"):
        validate_output(None, "table_data")


def test_validate_empty_dict_raises():
    with pytest.raises(SchemaValidationError, match="empty dict"):
        validate_output({}, "table_data")


def test_validate_empty_list_raises():
    with pytest.raises(SchemaValidationError, match="empty list"):
        validate_output([], "table_data")


def test_validate_missing_required_key():
    with pytest.raises(SchemaValidationError, match="Missing required"):
        validate_output({"headers": ["Name"]}, "table_data")


def test_validate_wrong_type():
    with pytest.raises(SchemaValidationError, match="expected type"):
        validate_output({"headers": "not a list", "rows": []}, "table_data")


def test_get_schema_known_pattern():
    schema = get_schema("table_data")
    assert schema["required"] == ["headers", "rows"]


def test_get_schema_unknown_falls_back_to_generic():
    schema = get_schema("nonexistent_pattern")
    assert schema == SCHEMAS["generic"]


def test_register_custom_schema():
    register_schema("job_listing", {
        "type": "object",
        "properties": {"jobs": {"type": "array"}},
        "required": ["jobs"],
    })
    schema = get_schema("job_listing")
    assert "jobs" in schema["properties"]
    # Clean up
    del SCHEMAS["job_listing"]


def test_register_schema_invalid_type():
    with pytest.raises(TypeError):
        register_schema("bad", "not a dict")
