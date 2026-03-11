# tests/test_core.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from humanization.core import Humanization, HumanizationConfig, ProxyConfig
from playwright.async_api import Page, Locator

@pytest.mark.asyncio
async def test_config_defaults():
    config = HumanizationConfig()
    assert config.fast is True
    assert config.humanize is True
    assert config.stealth_mode is True
    assert config.characters_per_minute == 600

def test_cubic_bezier():
    # Test pure math function
    h = Humanization(None)  # Page can be None for non-browser tests
    p0 = (0, 0)
    p1 = (100, 100)
    p2 = (200, 200)
    p3 = (300, 300)
    # At t=0.5, should be midpoint on linear but curved here
    point = h.cubic_bezier(0.5, p0, p1, p2, p3)
    assert point == (150.0, 150.0)

def test_generate_bezier_points():
    h = Humanization(None)
    p0 = (0, 0)
    p3 = (100, 100)
    points = h.generate_bezier_points(p0, p3, steps=3)
    assert len(points) == 3
    assert points[0] == (0, 0)
    assert points[-1] == (100, 100)
    # Middle point should be between start and end
    mid = points[1]
    assert 0 < mid[0] < 100
    assert 0 < mid[1] < 100

@pytest.fixture
def mock_page():
    page = AsyncMock(spec=Page)
    page.mouse = AsyncMock()
    page.keyboard = AsyncMock()
    page.evaluate = AsyncMock(return_value={"x": 0, "y": 0, "w": 1000, "h": 1000})
    return page

@pytest.fixture
def mock_locator():
    locator = MagicMock(spec=Locator)
    locator.bounding_box = AsyncMock(return_value={"x": 10, "y": 10, "width": 100, "height": 50})
    return locator

@pytest.mark.asyncio
async def test_move_to(mock_page, mock_locator):
    config = HumanizationConfig(fast=True)
    h = Humanization(mock_page, config)
    target = await h.move_to(mock_locator)
    assert isinstance(target, tuple)
    assert len(target) == 2
    # Should have moved the mouse multiple times
    assert mock_page.mouse.move.call_count > 1

@pytest.mark.asyncio
async def test_type_at(mock_page, mock_locator):
    config = HumanizationConfig()
    h = Humanization(mock_page, config)
    await h.type_at(mock_locator, "test")
    # One press per character
    assert mock_page.keyboard.press.call_count == 4

# --- ProxyConfig tests ---

def test_proxy_config_to_playwright_full():
    proxy = ProxyConfig(server="http://proxy:8080", username="user", password="pass", bypass="localhost")
    result = proxy.to_playwright_proxy()
    assert result == {
        "server": "http://proxy:8080",
        "username": "user",
        "password": "pass",
        "bypass": "localhost",
    }


def test_proxy_config_to_playwright_minimal():
    proxy = ProxyConfig(server="socks5://host:1080")
    result = proxy.to_playwright_proxy()
    assert result == {"server": "socks5://host:1080"}
    assert "username" not in result
    assert "password" not in result
    assert "bypass" not in result


def test_proxy_config_tor():
    proxy = ProxyConfig.tor()
    assert proxy.server == "socks5://127.0.0.1:9050"
    assert proxy.username is None


def test_proxy_config_tor_custom_port():
    proxy = ProxyConfig.tor(port=9150)
    assert proxy.server == "socks5://127.0.0.1:9150"


# --- undetected_launch tests (mocked) ---

@pytest.mark.asyncio
async def test_undetected_launch_with_proxy():
    mock_page = AsyncMock(spec=Page)
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_chromium = AsyncMock()
    mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("humanization.core.async_playwright") as mock_apw:
        mock_apw.return_value.start = AsyncMock(return_value=mock_pw)
        proxy = ProxyConfig(server="http://proxy:8080", username="u", password="p")
        h = await Humanization.undetected_launch(
            "/tmp/test", proxy=proxy, user_agent="TestUA/1.0"
        )
        call_kwargs = mock_chromium.launch_persistent_context.call_args[1]
        assert call_kwargs["proxy"] == {"server": "http://proxy:8080", "username": "u", "password": "p"}
        assert call_kwargs["user_agent"] == "TestUA/1.0"
        assert h.page == mock_page
        assert h._playwright == mock_pw
        assert h._context == mock_context


@pytest.mark.asyncio
async def test_undetected_launch_random_user_agent():
    mock_page = AsyncMock(spec=Page)
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_chromium = AsyncMock()
    mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("humanization.core.async_playwright") as mock_apw, \
         patch("humanization.core.user_agents") as mock_ua_mod:
        mock_apw.return_value.start = AsyncMock(return_value=mock_pw)
        mock_ua_mod.get_random.return_value = "RandomUA/1.0"

        h = await Humanization.undetected_launch("/tmp/test")
        call_kwargs = mock_chromium.launch_persistent_context.call_args[1]
        assert call_kwargs["user_agent"] == "RandomUA/1.0"
        mock_ua_mod.get_random.assert_called_once()


@pytest.mark.asyncio
async def test_undetected_launch_no_proxy():
    mock_page = AsyncMock(spec=Page)
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_chromium = AsyncMock()
    mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("humanization.core.async_playwright") as mock_apw:
        mock_apw.return_value.start = AsyncMock(return_value=mock_pw)
        h = await Humanization.undetected_launch("/tmp/test", user_agent="TestUA/1.0")
        call_kwargs = mock_chromium.launch_persistent_context.call_args[1]
        assert "proxy" not in call_kwargs


@pytest.mark.asyncio
async def test_close():
    mock_context = AsyncMock()
    mock_pw = AsyncMock()
    h = Humanization(AsyncMock(spec=Page), _playwright=mock_pw, _context=mock_context)
    await h.close()
    mock_context.close.assert_called_once()
    mock_pw.stop.assert_called_once()
    assert h._context is None
    assert h._playwright is None


@pytest.mark.skip("Requires real browser; run locally")
@pytest.mark.asyncio
async def test_undetected_launch_integration():
    config = HumanizationConfig()
    h = await Humanization.undetected_launch("/tmp/user_data", config)
    assert h.page is not None
    await h.close()
