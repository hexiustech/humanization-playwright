"""Integration-level tests for the crawler (all external deps mocked)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from humanization.crawler.crawler import crawl, CrawlerConfig, _CrawlerSession
from humanization.crawler.budget import GlobalBudget
from humanization.crawler.exceptions import (
    CrawlerError,
    BudgetExhaustedError,
)


@pytest.fixture
def mock_browser():
    """Mock Humanization browser instance."""
    browser = AsyncMock()
    browser.page = AsyncMock()
    browser.page.goto = AsyncMock()
    browser.page.content = AsyncMock(
        return_value="<html><body><table><tr><td>Data</td></tr></table></body></html>"
    )
    browser.human_wait = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_anthropic_response():
    """Mock Claude API response with a valid extract function."""
    response = MagicMock()
    response.content = [
        MagicMock(text='async def extract(page):\n    return {"data": "extracted"}')
    ]
    response.usage.input_tokens = 1000
    response.usage.output_tokens = 500
    return response


@pytest.fixture
def crawler_config(tmp_path):
    return CrawlerConfig(
        scripts_dir=tmp_path / "scripts",
        budget_file=tmp_path / "budget.json",
        session_max_api_calls=5,
        session_max_tokens=50_000,
    )


class TestCrawlerSession:
    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_generates_new_script(
        self, mock_humanization_cls, mock_browser, mock_anthropic_response, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        session = _CrawlerSession(crawler_config)
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        session._client = mock_client

        result = await session.run(
            "https://example.com",
            "some data",
            proxy=None,
            user_data_dir=None,
            humanization_config=None,
        )

        assert result == {"data": "extracted"}
        mock_client.messages.create.assert_called()

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_uses_cached_pattern_script(
        self, mock_humanization_cls, mock_browser, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        # Pre-cache a script
        from humanization.crawler.registry import ScriptRegistry
        registry = ScriptRegistry(crawler_config.scripts_dir)
        script_code = 'async def extract(page):\n    return {"data": "cached"}'
        registry.save_script(script_code, "generic", "example.com")

        session = _CrawlerSession(crawler_config)
        # Don't set up anthropic client — it shouldn't be needed
        result = await session.run(
            "https://example.com/page",
            "some random data",
            proxy=None,
            user_data_dir=None,
            humanization_config=None,
        )

        assert result == {"data": "cached"}

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_heals_failing_script(
        self, mock_humanization_cls, mock_browser, mock_anthropic_response, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        # Pre-cache a broken script
        from humanization.crawler.registry import ScriptRegistry
        registry = ScriptRegistry(crawler_config.scripts_dir)
        broken_code = 'async def extract(page):\n    raise ValueError("broken")'
        registry.save_script(broken_code, "generic", "example.com")

        session = _CrawlerSession(crawler_config)
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        session._client = mock_client

        result = await session.run(
            "https://example.com",
            "some data",
            proxy=None,
            user_data_dir=None,
            humanization_config=None,
        )

        # Should have healed and returned the API-generated result
        assert result == {"data": "extracted"}
        mock_client.messages.create.assert_called()

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_budget_exhausted(
        self, mock_humanization_cls, mock_browser, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)
        crawler_config.session_max_api_calls = 0  # Exhaust immediately

        session = _CrawlerSession(crawler_config)

        with pytest.raises(BudgetExhaustedError):
            await session.run(
                "https://example.com",
                "some data",
                proxy=None,
                user_data_dir=None,
                humanization_config=None,
            )

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_all_attempts_fail(
        self, mock_humanization_cls, mock_browser, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)
        crawler_config.max_heal_attempts = 1

        # API always returns a script that fails
        fail_response = MagicMock()
        fail_response.content = [
            MagicMock(text='async def extract(page):\n    raise RuntimeError("always fails")')
        ]
        fail_response.usage.input_tokens = 100
        fail_response.usage.output_tokens = 50

        session = _CrawlerSession(crawler_config)
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = fail_response
        session._client = mock_client

        with pytest.raises(CrawlerError, match="Failed to extract"):
            await session.run(
                "https://example.com",
                "some data",
                proxy=None,
                user_data_dir=None,
                humanization_config=None,
            )

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_falls_back_to_domain_script(
        self, mock_humanization_cls, mock_browser, mock_anthropic_response, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        # Pre-cache a domain script (no pattern script)
        from humanization.crawler.registry import ScriptRegistry
        registry = ScriptRegistry(crawler_config.scripts_dir)
        domain_code = 'async def extract(page):\n    return {"data": "domain_result"}'
        registry.save_script(domain_code, "generic", "example.com", is_domain_specific=True)

        session = _CrawlerSession(crawler_config)
        result = await session.run(
            "https://example.com/page",
            "some random data",
            proxy=None,
            user_data_dir=None,
            humanization_config=None,
        )

        assert result == {"data": "domain_result"}

    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_classifies_pattern(
        self, mock_humanization_cls, mock_browser, mock_anthropic_response, crawler_config
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        # Pre-cache a product_listing pattern script
        from humanization.crawler.registry import ScriptRegistry
        registry = ScriptRegistry(crawler_config.scripts_dir)
        code = 'async def extract(page):\n    return {"products": [{"name": "Widget"}]}'
        registry.save_script(code, "product_listing", "shop.com")

        session = _CrawlerSession(crawler_config)
        result = await session.run(
            "https://shop.com/catalog",
            "all product names and prices",  # Should classify as product_listing
            proxy=None,
            user_data_dir=None,
            humanization_config=None,
        )

        assert result["products"][0]["name"] == "Widget"


class TestCrawlFunction:
    @pytest.mark.asyncio
    @patch("humanization.crawler.crawler.Humanization")
    async def test_crawl_convenience_function(
        self, mock_humanization_cls, mock_browser, mock_anthropic_response, tmp_path
    ):
        mock_humanization_cls.undetected_launch = AsyncMock(return_value=mock_browser)

        config = CrawlerConfig(
            scripts_dir=tmp_path / "scripts",
            budget_file=tmp_path / "budget.json",
        )

        with patch("humanization.crawler.crawler._CrawlerSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.run.return_value = {"data": "result"}
            mock_session_cls.return_value = mock_session

            result = await crawl(
                "https://example.com",
                "some data",
                config=config,
            )

            assert result == {"data": "result"}
            mock_session.run.assert_called_once()
