"""Tests for the generic "click to continue" interstitial detector.

This obstacle is site-agnostic by design (see obstacle_handler.
detect_continue_interstitial) — it must recognize ANY page using the
imperative "click/tap/press ... to continue" phrasing (Amazon's "Click the
button below to continue shopping" being one example), while NOT
false-triggering on ordinary multi-step "Continue" buttons that are part of
legitimate content (checkout flows, post-add-to-cart confirmations).
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

from src.services.obstacle_handler import (
    detect_continue_interstitial,
    detect_obstacle,
    detect_obstacle_from_observed,
    ObstacleMatch,
)
from src.services.observer import observe


# ── detect_continue_interstitial: positive cases (site-agnostic wording) ────

def test_detects_amazon_style_continue_wall():
    text = "Click the button below to continue shopping. [Continue shopping]"
    assert detect_continue_interstitial(text) is True


def test_detects_generic_click_here_to_continue():
    text = "Click here to continue."
    assert detect_continue_interstitial(text) is True


def test_detects_tap_below_to_continue():
    text = "Tap the button below to continue."
    assert detect_continue_interstitial(text) is True


def test_detects_press_to_continue():
    text = "Please press the button below to continue."
    assert detect_continue_interstitial(text) is True


def test_detects_select_continue_below():
    text = "Please select Continue below to proceed."
    assert detect_continue_interstitial(text) is True


def test_detects_on_non_amazon_site():
    """The detector must generalize beyond the specific site it was reported on."""
    text = "Welcome to ExampleShop. Click here to continue to checkout."
    assert detect_continue_interstitial(text) is True


# ── detect_continue_interstitial: negative cases (legit flows must pass) ────

def test_does_not_flag_plain_continue_button_label():
    """A bare 'Continue shopping' button next to real cart content is normal
    UX, not a blocking wall -- must not falsely trigger."""
    text = "Item added to your cart. [Continue shopping] [Go to checkout]"
    assert detect_continue_interstitial(text) is False


def test_does_not_flag_checkout_continue_to_payment():
    text = "Shipping address saved. Click Continue to Payment to proceed with your order."
    assert detect_continue_interstitial(text) is False


def test_does_not_flag_unrelated_page():
    text = "Search results for 'wireless mouse'. 24 items found."
    assert detect_continue_interstitial(text) is False


def test_empty_text_returns_false():
    assert detect_continue_interstitial("") is False
    assert detect_continue_interstitial(None) is False


# ── detect_obstacle wiring ───────────────────────────────────────────────────

def test_detect_obstacle_returns_interstitial_match():
    match = detect_obstacle("Click the button below to continue shopping.")
    assert isinstance(match, ObstacleMatch)
    assert match.category == "interstitial"
    assert match.obstacle_type == "continue_wall"
    assert match.requires_human_input is False  # agent should self-bypass, not ask the user


def test_detect_obstacle_captcha_takes_priority_over_interstitial():
    """If a page somehow matches both, CAPTCHA must win (agent has a
    dedicated bypass path for it)."""
    text = "Please complete the recaptcha to continue."
    match = detect_obstacle(text)
    assert match.category == "captcha"


# ── ObservedState wiring ─────────────────────────────────────────────────────

def test_observe_sets_interstitial_type():
    state = observe("Click the button below to continue shopping.")
    assert state.interstitial_type == "continue_wall"
    assert state.is_blocked is True


def test_observe_no_interstitial_on_normal_page():
    state = observe("Search results for 'wireless mouse'. 24 items found.")
    assert state.interstitial_type is None


def test_detect_obstacle_from_observed_reads_interstitial_flag():
    state = observe("Click here to continue.")
    match = detect_obstacle_from_observed(state)
    assert match.category == "interstitial"
    assert match.requires_human_input is False
