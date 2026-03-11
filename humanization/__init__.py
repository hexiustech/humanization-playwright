# humanization-playwright/__init__.py
__version__ = "0.1.0"

from .core import Humanization, HumanizationConfig, ProxyConfig
from . import user_agents
from . import crawler

__all__ = [
    "Humanization",
    "HumanizationConfig",
    "ProxyConfig",
    "user_agents",
    "crawler",
]

from loguru import logger
logger.add("humanization.log", rotation="100 MB")