"""Self-healing web crawler with AI-generated extraction scripts."""

from .crawler import crawl, CrawlerConfig
from .budget import GlobalBudget, SessionBudget
from .schemas import register_schema
from .exceptions import (
    CrawlerError,
    BudgetExhaustedError,
    ScriptExecutionError,
    ScriptGenerationError,
    SchemaValidationError,
)

__all__ = [
    "crawl",
    "CrawlerConfig",
    "GlobalBudget",
    "SessionBudget",
    "register_schema",
    "CrawlerError",
    "BudgetExhaustedError",
    "ScriptExecutionError",
    "ScriptGenerationError",
    "SchemaValidationError",
]
