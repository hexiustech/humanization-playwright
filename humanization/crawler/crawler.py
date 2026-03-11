"""Main crawler orchestrator: the crawl() entry point and internal session logic."""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from loguru import logger

from humanization.core import Humanization, HumanizationConfig, ProxyConfig
from .registry import ScriptRegistry
from .budget import BudgetTracker, SessionBudget, GlobalBudget
from .schemas import validate_output, get_schema
from .classifier import classify_target
from .codegen import generate_script, sample_html
from .executor import execute_script
from .exceptions import (
    CrawlerError,
    BudgetExhaustedError,
    ScriptExecutionError,
    SchemaValidationError,
)


@dataclass
class CrawlerConfig:
    """Configuration for the crawler."""

    scripts_dir: Path = field(
        default_factory=lambda: Path.home() / ".humanization" / "scripts"
    )
    budget_file: Path = field(
        default_factory=lambda: Path.home() / ".humanization" / "budget.json"
    )
    session_max_api_calls: int = 5
    session_max_tokens: int = 50_000
    global_budget: Optional[GlobalBudget] = None
    max_heal_attempts: int = 3
    html_sample_max_chars: int = 15_000
    anthropic_api_key: Optional[str] = None  # Falls back to ANTHROPIC_API_KEY env var


async def crawl(
    url: str,
    target: str,
    proxy: Optional[ProxyConfig] = None,
    user_data_dir: Optional[str] = None,
    config: Optional[CrawlerConfig] = None,
    humanization_config: Optional[HumanizationConfig] = None,
) -> Dict[str, Any]:
    """Extract structured data from a URL using a stealth browser and AI-generated scripts.

    Args:
        url: The page to crawl.
        target: Description of what to extract (e.g., "all product prices and names")
                or an HTML tag pattern (e.g., "table.results").
        proxy: Optional proxy configuration for stealth browsing.
        user_data_dir: Browser profile directory. Defaults to a temp dir.
        config: Crawler configuration (budgets, paths, limits).
        humanization_config: Browser humanization settings.

    Returns:
        Dict conforming to the matched pattern's JSON schema.

    Raises:
        BudgetExhaustedError: API limits exceeded.
        CrawlerError: Extraction failed after all attempts.
    """
    session = _CrawlerSession(config or CrawlerConfig())
    return await session.run(url, target, proxy, user_data_dir, humanization_config)


class _CrawlerSession:
    """Internal session managing one crawl operation."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.registry = ScriptRegistry(config.scripts_dir)
        self.budget_tracker = BudgetTracker(config.budget_file, config.global_budget)
        self.session_budget = SessionBudget(
            max_api_calls=config.session_max_api_calls,
            max_tokens=config.session_max_tokens,
        )
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError(
                    "The 'anthropic' package is required for the crawler module. "
                    "Install it with: pip install humanization-playwright[crawler]"
                )
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.anthropic_api_key
            )
        return self._client

    async def run(
        self,
        url: str,
        target: str,
        proxy: Optional[ProxyConfig],
        user_data_dir: Optional[str],
        humanization_config: Optional[HumanizationConfig],
    ) -> Dict[str, Any]:
        """Full crawl flow."""
        pattern = classify_target(target)
        domain = urlparse(url).netloc
        logger.info(f"Crawling {url} | target='{target}' | pattern={pattern}")

        browser = await self._launch_browser(proxy, user_data_dir, humanization_config)
        try:
            await browser.page.goto(url, wait_until="domcontentloaded")
            await browser.human_wait(1.0, 2.0)

            # Phase 1: Try pattern script from registry
            result = await self._try_pattern_script(browser.page, pattern, domain, target)
            if result is not None:
                logger.info(f"Pattern script succeeded for '{pattern}' on {domain}")
                return result

            # Phase 2: Try domain-specific script
            result = await self._try_domain_script(browser.page, pattern, domain, target)
            if result is not None:
                logger.info(f"Domain script succeeded for {domain}")
                return result

            # Phase 3: Generate new script via Claude API
            logger.info(f"No cached script found, generating via API")
            return await self._generate_and_run(
                browser.page, pattern, domain, target, is_domain_specific=False
            )
        finally:
            await browser.close()

    async def _try_pattern_script(
        self, page: Any, pattern: str, domain: str, target: str
    ) -> Optional[Dict[str, Any]]:
        """Try running a cached pattern script."""
        script_file = self.registry.find_pattern_script(pattern)
        if script_file is None:
            return None

        logger.debug(f"Found pattern script: {script_file}")
        script_code = self.registry.load_script(script_file)
        return await self._run_with_healing(
            page, script_code, pattern, domain, target, is_domain_specific=False
        )

    async def _try_domain_script(
        self, page: Any, pattern: str, domain: str, target: str
    ) -> Optional[Dict[str, Any]]:
        """Try running a cached domain-specific script."""
        script_file = self.registry.find_domain_script(domain)
        if script_file is None:
            return None

        logger.debug(f"Found domain script: {script_file}")
        script_code = self.registry.load_script(script_file)
        return await self._run_with_healing(
            page, script_code, pattern, domain, target, is_domain_specific=True
        )

    async def _run_with_healing(
        self,
        page: Any,
        script_code: str,
        pattern: str,
        domain: str,
        target: str,
        is_domain_specific: bool,
    ) -> Optional[Dict[str, Any]]:
        """Run a script; if it fails, ask Claude to heal it (up to max_heal_attempts).

        Returns validated data, or None if all attempts fail.
        """
        last_error = None
        current_code = script_code

        for attempt in range(self.config.max_heal_attempts + 1):
            try:
                result = await execute_script(current_code, page)
                validate_output(result, pattern)
                self.registry.record_success(pattern, domain)
                return result
            except (ScriptExecutionError, SchemaValidationError) as e:
                last_error = str(e)
                logger.warning(
                    f"Script attempt {attempt + 1}/{self.config.max_heal_attempts + 1} "
                    f"failed: {last_error}"
                )

                if attempt < self.config.max_heal_attempts:
                    try:
                        self.session_budget.check()
                        self.budget_tracker.check()
                    except BudgetExhaustedError:
                        logger.warning("Budget exhausted during healing")
                        break

                    html = await sample_html(page, self.config.html_sample_max_chars)
                    schema = get_schema(pattern)
                    current_code, tokens = await generate_script(
                        self.client, target, pattern, schema, html,
                        previous_error=last_error,
                    )
                    self.session_budget.record(tokens)
                    self.budget_tracker.record(tokens)
                    logger.debug(f"Healed script (tokens: {tokens})")

        self.registry.record_failure(pattern, domain)
        return None

    async def _generate_and_run(
        self,
        page: Any,
        pattern: str,
        domain: str,
        target: str,
        is_domain_specific: bool,
    ) -> Dict[str, Any]:
        """Generate a brand-new script via Claude API and run it."""
        self.session_budget.check()
        self.budget_tracker.check()

        html = await sample_html(page, self.config.html_sample_max_chars)
        schema = get_schema(pattern)
        script_code, tokens = await generate_script(
            self.client, target, pattern, schema, html
        )
        self.session_budget.record(tokens)
        self.budget_tracker.record(tokens)
        logger.info(f"Generated new script (tokens: {tokens})")

        result = await self._run_with_healing(
            page, script_code, pattern, domain, target, is_domain_specific
        )

        if result is not None:
            self.registry.save_script(script_code, pattern, domain, is_domain_specific)
            return result

        # Pattern script failed → try domain-specific generation
        if not is_domain_specific:
            logger.info(f"Pattern script failed, trying domain-specific for {domain}")
            return await self._generate_and_run(
                page, pattern, domain, target, is_domain_specific=True
            )

        raise CrawlerError(
            f"Failed to extract '{target}' from {domain} after all attempts. "
            f"Pattern: {pattern}"
        )

    async def _launch_browser(
        self,
        proxy: Optional[ProxyConfig],
        user_data_dir: Optional[str],
        humanization_config: Optional[HumanizationConfig],
    ) -> Humanization:
        """Launch a stealth browser instance."""
        if user_data_dir is None:
            user_data_dir = tempfile.mkdtemp(prefix="humanization_crawler_")

        return await Humanization.undetected_launch(
            user_data_dir=user_data_dir,
            config=humanization_config,
            proxy=proxy,
            headless=True,
        )
