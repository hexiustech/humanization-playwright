import json
import random
from pathlib import Path
from typing import List
from loguru import logger


DEFAULT_USER_AGENTS: List[str] = [
    # Chrome - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome - Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Firefox - Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Edge - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Safari - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]

_pool: List[str] = list(DEFAULT_USER_AGENTS)


def get_random() -> str:
    """Return a random user agent from the pool."""
    if not _pool:
        raise ValueError("User agent pool is empty")
    ua = random.choice(_pool)
    logger.debug(f"Selected random user agent: {ua[:60]}...")
    return ua


def list_agents() -> List[str]:
    """Return a copy of the current pool."""
    return list(_pool)


def add(user_agent: str) -> None:
    """Add a user agent to the pool. Skips duplicates."""
    if user_agent in _pool:
        logger.debug(f"User agent already in pool: {user_agent[:60]}...")
        return
    _pool.append(user_agent)
    logger.info(f"Added user agent to pool: {user_agent[:60]}...")


def remove(user_agent: str) -> None:
    """Remove a user agent from the pool."""
    try:
        _pool.remove(user_agent)
        logger.info(f"Removed user agent from pool: {user_agent[:60]}...")
    except ValueError:
        raise ValueError(f"User agent not found in pool: {user_agent[:60]}...")


def clear() -> None:
    """Empty the pool."""
    _pool.clear()
    logger.info("Cleared user agent pool")


def reset() -> None:
    """Reset the pool to built-in defaults."""
    _pool.clear()
    _pool.extend(DEFAULT_USER_AGENTS)
    logger.info("Reset user agent pool to defaults")


def save(filepath: str = "user_agents.json") -> None:
    """Persist the current pool to a JSON file."""
    data = {"user_agents": list(_pool)}
    Path(filepath).write_text(json.dumps(data, indent=2))
    logger.info(f"Saved {len(_pool)} user agents to {filepath}")


def load(filepath: str = "user_agents.json") -> None:
    """Load the pool from a JSON file, replacing the current pool."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"User agent file not found: {filepath}")
    data = json.loads(path.read_text())
    agents = data.get("user_agents", [])
    _pool.clear()
    _pool.extend(agents)
    logger.info(f"Loaded {len(_pool)} user agents from {filepath}")
