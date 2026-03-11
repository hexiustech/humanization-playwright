"""Tests for budget tracking."""

import json
from datetime import date

import pytest

from humanization.crawler.budget import SessionBudget, GlobalBudget, BudgetTracker
from humanization.crawler.exceptions import BudgetExhaustedError


class TestSessionBudget:
    def test_within_limits(self):
        budget = SessionBudget(max_api_calls=5, max_tokens=50_000)
        budget.record(1000)
        budget.check()  # Should not raise

    def test_calls_exceeded(self):
        budget = SessionBudget(max_api_calls=2, max_tokens=50_000)
        budget.record(100)
        budget.record(100)
        with pytest.raises(BudgetExhaustedError, match="call limit"):
            budget.check()

    def test_tokens_exceeded(self):
        budget = SessionBudget(max_api_calls=10, max_tokens=500)
        budget.record(600)
        with pytest.raises(BudgetExhaustedError, match="token limit"):
            budget.check()

    def test_record_increments(self):
        budget = SessionBudget()
        budget.record(1000)
        budget.record(2000)
        assert budget.api_calls_used == 2
        assert budget.tokens_used == 3000


class TestBudgetTracker:
    def test_check_empty_file(self, tmp_path):
        tracker = BudgetTracker(tmp_path / "budget.json")
        tracker.check()  # Should not raise

    def test_record_creates_file(self, tmp_path):
        budget_file = tmp_path / "budget.json"
        tracker = BudgetTracker(budget_file)
        tracker.record(1000)

        assert budget_file.exists()
        data = json.loads(budget_file.read_text())
        today = date.today().isoformat()
        assert data["daily"][today]["tokens"] == 1000
        assert data["daily"][today]["calls"] == 1

    def test_record_accumulates(self, tmp_path):
        tracker = BudgetTracker(tmp_path / "budget.json")
        tracker.record(1000)
        tracker.record(2000)

        data = json.loads((tmp_path / "budget.json").read_text())
        today = date.today().isoformat()
        assert data["daily"][today]["tokens"] == 3000
        assert data["daily"][today]["calls"] == 2

    def test_monthly_tracking(self, tmp_path):
        tracker = BudgetTracker(tmp_path / "budget.json")
        tracker.record(5000)

        data = json.loads((tmp_path / "budget.json").read_text())
        month = date.today().strftime("%Y-%m")
        assert data["monthly"][month]["tokens"] == 5000
        assert data["monthly"][month]["calls"] == 1

    def test_daily_limit_exceeded(self, tmp_path):
        budget_file = tmp_path / "budget.json"
        limits = GlobalBudget(daily_limit_calls=2)
        tracker = BudgetTracker(budget_file, limits)
        tracker.record(100)
        tracker.record(100)
        with pytest.raises(BudgetExhaustedError, match="Daily API call limit"):
            tracker.check()

    def test_daily_token_limit_exceeded(self, tmp_path):
        limits = GlobalBudget(daily_limit_tokens=500)
        tracker = BudgetTracker(tmp_path / "budget.json", limits)
        tracker.record(600)
        with pytest.raises(BudgetExhaustedError, match="Daily token limit"):
            tracker.check()

    def test_monthly_limit_exceeded(self, tmp_path):
        limits = GlobalBudget(monthly_limit_calls=1)
        tracker = BudgetTracker(tmp_path / "budget.json", limits)
        tracker.record(100)
        with pytest.raises(BudgetExhaustedError, match="Monthly API call limit"):
            tracker.check()

    def test_monthly_token_limit_exceeded(self, tmp_path):
        limits = GlobalBudget(monthly_limit_tokens=500)
        tracker = BudgetTracker(tmp_path / "budget.json", limits)
        tracker.record(600)
        with pytest.raises(BudgetExhaustedError, match="Monthly token limit"):
            tracker.check()

    def test_creates_parent_dirs(self, tmp_path):
        budget_file = tmp_path / "deep" / "nested" / "budget.json"
        tracker = BudgetTracker(budget_file)
        tracker.record(100)
        assert budget_file.exists()

    def test_handles_corrupted_file(self, tmp_path):
        budget_file = tmp_path / "budget.json"
        budget_file.write_text("not json")
        tracker = BudgetTracker(budget_file)
        tracker.check()  # Should not raise, treats as empty
        tracker.record(100)  # Should overwrite with valid data
