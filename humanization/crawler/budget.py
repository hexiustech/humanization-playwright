"""API usage tracking with per-session and global budget limits."""

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from .exceptions import BudgetExhaustedError


@dataclass
class SessionBudget:
    """Per-session API usage limits."""

    max_api_calls: int = 5
    max_tokens: int = 50_000
    api_calls_used: int = 0
    tokens_used: int = 0

    def check(self) -> None:
        """Raise BudgetExhaustedError if either limit is exceeded."""
        if self.api_calls_used >= self.max_api_calls:
            raise BudgetExhaustedError(
                f"Session API call limit reached: {self.api_calls_used}/{self.max_api_calls}"
            )
        if self.tokens_used >= self.max_tokens:
            raise BudgetExhaustedError(
                f"Session token limit reached: {self.tokens_used}/{self.max_tokens}"
            )

    def record(self, tokens: int) -> None:
        """Record one API call with the given token count."""
        self.api_calls_used += 1
        self.tokens_used += tokens


@dataclass
class GlobalBudget:
    """Global daily/monthly API usage limits."""

    daily_limit_tokens: int = 500_000
    monthly_limit_tokens: int = 5_000_000
    daily_limit_calls: int = 100
    monthly_limit_calls: int = 2000


class BudgetTracker:
    """Persists global API usage to a JSON file.

    File format:
    {
        "daily": {"2026-03-11": {"tokens": 1234, "calls": 5}},
        "monthly": {"2026-03": {"tokens": 12345, "calls": 50}}
    }

    Uses atomic writes (temp file + os.replace) to prevent corruption.
    Reads fresh on each check()/record() for multi-process safety.
    """

    def __init__(
        self,
        budget_file: Path,
        limits: Optional[GlobalBudget] = None,
    ):
        self.budget_file = budget_file
        self.limits = limits or GlobalBudget()

    def check(self) -> None:
        """Raise BudgetExhaustedError if daily or monthly limits are exceeded."""
        data = self._load()
        today = date.today().isoformat()
        month = date.today().strftime("%Y-%m")

        daily = data.get("daily", {}).get(today, {})
        monthly = data.get("monthly", {}).get(month, {})

        daily_tokens = daily.get("tokens", 0)
        daily_calls = daily.get("calls", 0)
        monthly_tokens = monthly.get("tokens", 0)
        monthly_calls = monthly.get("calls", 0)

        if daily_calls >= self.limits.daily_limit_calls:
            raise BudgetExhaustedError(
                f"Daily API call limit reached: {daily_calls}/{self.limits.daily_limit_calls}"
            )
        if daily_tokens >= self.limits.daily_limit_tokens:
            raise BudgetExhaustedError(
                f"Daily token limit reached: {daily_tokens}/{self.limits.daily_limit_tokens}"
            )
        if monthly_calls >= self.limits.monthly_limit_calls:
            raise BudgetExhaustedError(
                f"Monthly API call limit reached: {monthly_calls}/{self.limits.monthly_limit_calls}"
            )
        if monthly_tokens >= self.limits.monthly_limit_tokens:
            raise BudgetExhaustedError(
                f"Monthly token limit reached: {monthly_tokens}/{self.limits.monthly_limit_tokens}"
            )

    def record(self, tokens: int) -> None:
        """Record usage for today and this month. Persists atomically."""
        data = self._load()
        today = date.today().isoformat()
        month = date.today().strftime("%Y-%m")

        if "daily" not in data:
            data["daily"] = {}
        if "monthly" not in data:
            data["monthly"] = {}

        if today not in data["daily"]:
            data["daily"][today] = {"tokens": 0, "calls": 0}
        if month not in data["monthly"]:
            data["monthly"][month] = {"tokens": 0, "calls": 0}

        data["daily"][today]["tokens"] += tokens
        data["daily"][today]["calls"] += 1
        data["monthly"][month]["tokens"] += tokens
        data["monthly"][month]["calls"] += 1

        # Prune daily entries older than 7 days
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        data["daily"] = {
            k: v for k, v in data["daily"].items() if k >= cutoff
        }

        self._save(data)

    def _load(self) -> Dict[str, Any]:
        """Load the budget file, returning empty dict if not found."""
        if not self.budget_file.exists():
            return {}
        try:
            with open(self.budget_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        """Write data atomically via temp file + os.replace."""
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.budget_file.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(self.budget_file))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
