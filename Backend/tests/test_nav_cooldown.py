"""Tests for per-domain navigation cooldown in Brain."""
import os
import time

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest
from src.services.brain import Brain, _NavigationCooldownSkip


class TestNavCooldown:
    """Unit tests for the navigation failure tracker (no DB / no MCP needed)."""

    @pytest.fixture
    def brain(self):
        return Brain(stream_manager=None)

    def test_extract_domain_parses_url(self, brain: Brain):
        assert brain._extract_domain("https://example.com/path") == "example.com"
        assert brain._extract_domain("http://sub.example.co.uk:8080/") == "sub.example.co.uk:8080"
        assert brain._extract_domain("") == ""

    def test_failure_count_increments(self, brain: Brain):
        brain._record_nav_failure("blocked.com")
        assert brain._nav_failure_tracker["blocked.com"]["count"] == 1
        brain._record_nav_failure("blocked.com")
        assert brain._nav_failure_tracker["blocked.com"]["count"] == 2

    def test_cooldown_activates_after_three_failures(self, brain: Brain):
        brain._record_nav_failure("bad.com")
        brain._record_nav_failure("bad.com")
        assert not brain._is_nav_blocked("bad.com")  # 2 failures → still allowed
        brain._record_nav_failure("bad.com")
        assert brain._is_nav_blocked("bad.com")  # 3 failures → blocked

    def test_cooldown_message_contains_remaining_time(self, brain: Brain):
        brain._record_nav_failure("slow.com")
        brain._record_nav_failure("slow.com")
        brain._record_nav_failure("slow.com")
        msg = brain._nav_cooldown_message("slow.com")
        assert "[Navigation Cooldown]" in msg
        assert "slow.com" in msg
        assert "3" in msg
        assert "60" in msg or "59" in msg  # remaining seconds

    def test_success_resets_tracker(self, brain: Brain):
        brain._record_nav_failure("maybe.com")
        brain._record_nav_failure("maybe.com")
        brain._record_nav_success("maybe.com")
        assert "maybe.com" not in brain._nav_failure_tracker
        assert not brain._is_nav_blocked("maybe.com")

    def test_cooldown_expires_after_60s(self, brain: Brain):
        brain._record_nav_failure("temp.com")
        brain._record_nav_failure("temp.com")
        brain._record_nav_failure("temp.com")
        assert brain._is_nav_blocked("temp.com")
        # Fast-forward time by manipulating the tracker directly
        brain._nav_failure_tracker["temp.com"]["cooldown_until"] = time.time() - 1
        assert not brain._is_nav_blocked("temp.com")
        assert "temp.com" not in brain._nav_failure_tracker  # auto-cleanup

    def test_different_domains_tracked_independently(self, brain: Brain):
        brain._record_nav_failure("a.com")
        brain._record_nav_failure("b.com")
        assert brain._nav_failure_tracker["a.com"]["count"] == 1
        assert brain._nav_failure_tracker["b.com"]["count"] == 1
        brain._record_nav_failure("a.com")
        brain._record_nav_failure("a.com")
        assert brain._is_nav_blocked("a.com")
        assert not brain._is_nav_blocked("b.com")

    def test_navigation_cooldown_skip_is_exception(self):
        """The helper exception is importable and carries no state."""
        exc = _NavigationCooldownSkip()
        assert isinstance(exc, Exception)
