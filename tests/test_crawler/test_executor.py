"""Tests for the script executor."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from humanization.crawler.executor import execute_script
from humanization.crawler.exceptions import ScriptExecutionError


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.query_selector_all.return_value = []
    page.query_selector.return_value = None
    page.evaluate.return_value = None
    page.inner_text.return_value = ""
    return page


class TestExecuteScript:
    @pytest.mark.asyncio
    async def test_valid_script(self, mock_page):
        code = """
async def extract(page):
    return {"data": "hello"}
"""
        result = await execute_script(code, mock_page)
        assert result == {"data": "hello"}

    @pytest.mark.asyncio
    async def test_script_using_page(self, mock_page):
        mock_page.inner_text.return_value = "Test Title"
        code = """
async def extract(page):
    title = await page.inner_text("h1")
    return {"data": title}
"""
        result = await execute_script(code, mock_page)
        assert result == {"data": "Test Title"}

    @pytest.mark.asyncio
    async def test_script_with_builtins(self, mock_page):
        code = """
async def extract(page):
    items = list(range(5))
    return {"data": len(items)}
"""
        result = await execute_script(code, mock_page)
        assert result == {"data": 5}

    @pytest.mark.asyncio
    async def test_no_extract_function(self, mock_page):
        code = "x = 42"
        with pytest.raises(ScriptExecutionError, match="does not define"):
            await execute_script(code, mock_page)

    @pytest.mark.asyncio
    async def test_syntax_error(self, mock_page):
        code = "def extract(page)\n    return {}"  # Missing colon
        with pytest.raises(ScriptExecutionError, match="syntax error"):
            await execute_script(code, mock_page)

    @pytest.mark.asyncio
    async def test_runtime_error(self, mock_page):
        code = """
async def extract(page):
    return 1 / 0
"""
        with pytest.raises(ScriptExecutionError, match="ZeroDivisionError"):
            await execute_script(code, mock_page)

    @pytest.mark.asyncio
    async def test_import_blocked(self, mock_page):
        code = """
import os
async def extract(page):
    return {"data": os.getcwd()}
"""
        with pytest.raises(ScriptExecutionError):
            await execute_script(code, mock_page)

    @pytest.mark.asyncio
    async def test_returns_list(self, mock_page):
        code = """
async def extract(page):
    return [{"name": "a"}, {"name": "b"}]
"""
        result = await execute_script(code, mock_page)
        assert len(result) == 2
        assert result[0]["name"] == "a"

    @pytest.mark.asyncio
    async def test_extract_not_callable(self, mock_page):
        code = "extract = 42"
        with pytest.raises(ScriptExecutionError, match="does not define"):
            await execute_script(code, mock_page)
