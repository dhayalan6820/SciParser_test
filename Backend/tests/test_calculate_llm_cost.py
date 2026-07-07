"""Tests for calculate_llm_cost warning behaviour.

Verifies that:
- Calling with an unknown model emits a WARNING (only once per model).
- When the default pricing is 0.0/0.0 the warning specifically mentions zero-cost billing.
- When the default pricing is non-zero the warning mentions the fallback rates.
- Known models produce no warning.
- The returned cost from a zero-default call is 0.0, distinguishable from
  intentionally-priced calls via the warning in logs.
"""
import importlib
import logging
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import src.config as _cfg

_ORIGINAL_INPUT = _cfg.LLM_INPUT_COST_PER_MILLION
_ORIGINAL_OUTPUT = _cfg.LLM_OUTPUT_COST_PER_MILLION


def _reload_atag_with_defaults(input_cost: float, output_cost: float):
    """Re-import ATAG after patching the config values so LLM_PRICING['default']
    picks up fresh numbers and the per-model warn-set is reset."""
    _cfg.LLM_INPUT_COST_PER_MILLION = input_cost
    _cfg.LLM_OUTPUT_COST_PER_MILLION = output_cost

    import src.services.ATAG as atag_mod
    importlib.reload(atag_mod)
    return atag_mod


# Use a model that is hardcoded in LLM_PRICING (not config-dependent) so the
# test is immune to config patching done by other tests.
_KNOWN_MODEL = "moonshotai/kimi-k2.7-code"
_KNOWN_INPUT = 0.5
_KNOWN_OUTPUT = 1.5


class TestCalculateLlmCostWarnings:
    def setup_method(self):
        """Reload with original defaults before each test to get a clean warned-set."""
        self.atag = _reload_atag_with_defaults(_ORIGINAL_INPUT, _ORIGINAL_OUTPUT)

    def teardown_method(self):
        """Restore original config values so other test modules aren't affected."""
        _cfg.LLM_INPUT_COST_PER_MILLION = _ORIGINAL_INPUT
        _cfg.LLM_OUTPUT_COST_PER_MILLION = _ORIGINAL_OUTPUT
        import src.services.ATAG as atag_mod
        importlib.reload(atag_mod)

    def test_known_model_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            cost = self.atag.calculate_llm_cost(_KNOWN_MODEL, 1_000_000, 1_000_000)
        assert cost > 0
        assert caplog.records == [], "No warning expected for a known model"

    def test_known_model_cost_calculation(self):
        cost = self.atag.calculate_llm_cost(_KNOWN_MODEL, 1_000_000, 1_000_000)
        expected = round(_KNOWN_INPUT + _KNOWN_OUTPUT, 6)
        assert cost == expected

    def test_unknown_model_warns_once(self, caplog):
        model = "unknown/mystery-model-xyz"
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            self.atag.calculate_llm_cost(model, 500_000, 500_000)
            self.atag.calculate_llm_cost(model, 500_000, 500_000)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "Warning should fire exactly once per model"
        assert model in warnings[0].message

    def test_unknown_model_different_models_each_warn_once(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            self.atag.calculate_llm_cost("vendor/model-a", 1_000, 1_000)
            self.atag.calculate_llm_cost("vendor/model-b", 1_000, 1_000)
            self.atag.calculate_llm_cost("vendor/model-a", 1_000, 1_000)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 2

    def test_zero_default_warning_mentions_zero_cost(self, caplog):
        atag = _reload_atag_with_defaults(0.0, 0.0)
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            cost = atag.calculate_llm_cost("some/free-looking-model", 1_000_000, 1_000_000)

        assert cost == 0.0
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "$0.00" in warnings[0].message
        assert "LLM_INPUT_COST_PER_MILLION" in warnings[0].message

    def test_nonzero_default_warning_mentions_fallback_rates(self, caplog):
        atag = _reload_atag_with_defaults(0.15, 0.60)
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            atag.calculate_llm_cost("new/vendor-not-in-table", 1_000_000, 1_000_000)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "falling back to default" in warnings[0].message.lower()

    def test_zero_default_known_model_still_silent(self, caplog):
        """Even when defaults are 0.0, a hardcoded known model must not warn."""
        atag = _reload_atag_with_defaults(0.0, 0.0)
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            atag.calculate_llm_cost(_KNOWN_MODEL, 1_000_000, 1_000_000)
        assert caplog.records == [], "Known model should never warn regardless of defaults"

    def test_zero_cost_is_distinguishable_via_logs(self, caplog):
        """A zero-cost result from unknown model with zero defaults should have a log
        warning that makes it distinguishable from an intentionally priced call."""
        atag = _reload_atag_with_defaults(0.0, 0.0)
        with caplog.at_level(logging.WARNING, logger="src.services.ATAG"):
            cost = atag.calculate_llm_cost("mystery/model", 1_000_000, 1_000_000)

        assert cost == 0.0
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "Zero-cost from unknown model must produce a warning"
