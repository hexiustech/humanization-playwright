"""Tests for code generation and HTML sampling."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from humanization.crawler.codegen import (
    build_generation_prompt,
    _clean_code,
    sample_html,
    generate_script,
    SYSTEM_PROMPT,
)
from humanization.crawler.exceptions import ScriptGenerationError


class TestBuildGenerationPrompt:
    def test_includes_target(self):
        prompt = build_generation_prompt(
            "product prices", "product_listing", {"type": "object"}, "<html></html>"
        )
        assert "product prices" in prompt

    def test_includes_pattern(self):
        prompt = build_generation_prompt(
            "data", "table_data", {"type": "object"}, "<html></html>"
        )
        assert "table_data" in prompt

    def test_includes_schema(self):
        schema = {"type": "object", "required": ["items"]}
        prompt = build_generation_prompt("data", "generic", schema, "<html></html>")
        assert '"required"' in prompt
        assert '"items"' in prompt

    def test_includes_html_sample(self):
        html = "<div class='product'>Widget</div>"
        prompt = build_generation_prompt("data", "generic", {}, html)
        assert "Widget" in prompt

    def test_includes_error_on_heal(self):
        prompt = build_generation_prompt(
            "data", "generic", {}, "<html></html>",
            previous_error="KeyError: 'name'",
        )
        assert "KeyError" in prompt
        assert "fix the script" in prompt.lower()

    def test_no_error_section_when_none(self):
        prompt = build_generation_prompt("data", "generic", {}, "<html></html>")
        assert "previous" not in prompt.lower()


class TestCleanCode:
    def test_strips_markdown_fences(self):
        raw = "```python\nasync def extract(page):\n    pass\n```"
        assert _clean_code(raw) == "async def extract(page):\n    pass"

    def test_strips_plain_fences(self):
        raw = "```\nasync def extract(page):\n    pass\n```"
        assert _clean_code(raw) == "async def extract(page):\n    pass"

    def test_no_fences_passthrough(self):
        raw = "async def extract(page):\n    pass"
        assert _clean_code(raw) == raw

    def test_strips_whitespace(self):
        raw = "\n\n  async def extract(page):\n    pass  \n\n"
        assert _clean_code(raw) == "async def extract(page):\n    pass"


class TestSampleHtml:
    @pytest.mark.asyncio
    async def test_short_html_returned_as_is(self):
        page = AsyncMock()
        page.content.return_value = "<html><body><p>Hello</p></body></html>"
        result = await sample_html(page, max_chars=1000)
        assert "<p>Hello</p>" in result

    @pytest.mark.asyncio
    async def test_strips_script_tags(self):
        page = AsyncMock()
        page.content.return_value = (
            "<html><body><script>var x=1;</script><p>Content</p></body></html>"
        )
        result = await sample_html(page, max_chars=1000)
        assert "var x=1" not in result
        assert "Content" in result

    @pytest.mark.asyncio
    async def test_strips_style_tags(self):
        page = AsyncMock()
        page.content.return_value = (
            "<html><body><style>.foo{color:red}</style><p>Text</p></body></html>"
        )
        result = await sample_html(page, max_chars=1000)
        assert "color:red" not in result
        assert "Text" in result

    @pytest.mark.asyncio
    async def test_truncates_long_html(self):
        page = AsyncMock()
        page.content.return_value = (
            "<html><head><title>Test</title></head><body>" + "x" * 20000 + "</body></html>"
        )
        result = await sample_html(page, max_chars=5000)
        assert len(result) <= 5500  # Allow some overhead from title extraction

    @pytest.mark.asyncio
    async def test_handles_page_error(self):
        page = AsyncMock()
        page.content.side_effect = Exception("Page crashed")
        result = await sample_html(page)
        assert "Failed to retrieve" in result


class TestGenerateScript:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text="async def extract(page):\n    return {'data': 'ok'}")]
        response.usage.input_tokens = 1000
        response.usage.output_tokens = 500
        client.messages.create.return_value = response

        code, tokens = await generate_script(
            client, "test data", "generic", {"type": "object"}, "<html></html>"
        )
        assert "async def extract" in code
        assert tokens == 1500

    @pytest.mark.asyncio
    async def test_uses_haiku_model(self):
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text="async def extract(page):\n    pass")]
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        client.messages.create.return_value = response

        await generate_script(client, "data", "generic", {}, "<html></html>")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    async def test_includes_system_prompt(self):
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text="async def extract(page):\n    pass")]
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        client.messages.create.return_value = response

        await generate_script(client, "data", "generic", {}, "<html></html>")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        client = AsyncMock()
        client.messages.create.side_effect = RuntimeError("API down")

        with pytest.raises(ScriptGenerationError, match="API call failed"):
            await generate_script(client, "data", "generic", {}, "<html></html>")

    @pytest.mark.asyncio
    async def test_empty_response_raises(self):
        client = AsyncMock()
        response = MagicMock()
        response.content = []
        client.messages.create.return_value = response

        with pytest.raises(ScriptGenerationError, match="empty response"):
            await generate_script(client, "data", "generic", {}, "<html></html>")

    @pytest.mark.asyncio
    async def test_no_extract_function_raises(self):
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text="def not_extract(): pass")]
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        client.messages.create.return_value = response

        with pytest.raises(ScriptGenerationError, match="does not contain"):
            await generate_script(client, "data", "generic", {}, "<html></html>")
