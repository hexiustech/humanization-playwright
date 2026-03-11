"""Custom exception hierarchy for the crawler module."""


class CrawlerError(Exception):
    """Base exception for all crawler errors."""


class BudgetExhaustedError(CrawlerError):
    """Raised when API usage limits (session or global) are exceeded."""


class ScriptExecutionError(CrawlerError):
    """Raised when a generated extraction script fails to compile or run."""


class ScriptGenerationError(CrawlerError):
    """Raised when the Claude API fails to generate a valid script."""


class SchemaValidationError(CrawlerError):
    """Raised when extracted data does not conform to the expected schema."""
