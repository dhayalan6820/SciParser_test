"""Tests for the deterministic Booking/Pagination Interaction Agent support
layer (src/services/booking_agent.py): multi-step context detection, step
progress extraction, and stall/escalation tracking.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest

from src.services import booking_agent
from src.services.obstacle_handler import ObstacleInputNeeded, build_input_form, ObstacleMatch


# ── detect_multistep_context ─────────────────────────────────────────────────

def test_detect_multistep_context_true_for_step_indicator():
    assert booking_agent.detect_multistep_context("Step 2 of 5: Choose your seat") is True


def test_detect_multistep_context_true_for_page_indicator():
    assert booking_agent.detect_multistep_context("Page 3 of 10 results") is True


def test_detect_multistep_context_false_on_unrelated_text():
    assert booking_agent.detect_multistep_context("Welcome to our homepage.") is False


def test_detect_multistep_context_false_on_empty():
    assert booking_agent.detect_multistep_context("") is False
    assert booking_agent.detect_multistep_context(None) is False


# ── extract_step_progress ────────────────────────────────────────────────────

def test_extract_step_progress_parses_step_format():
    assert booking_agent.extract_step_progress("Step 2 of 5: Choose your seat") == (2, 5)


def test_extract_step_progress_parses_slash_format():
    assert booking_agent.extract_step_progress("Step 3/5") == (3, 5)


def test_extract_step_progress_parses_page_format():
    assert booking_agent.extract_step_progress("Page 4 of 10") == (4, 10)


def test_extract_step_progress_none_when_absent():
    assert booking_agent.extract_step_progress("Checkout wizard loaded.") is None
    assert booking_agent.extract_step_progress("") is None
    assert booking_agent.extract_step_progress(None) is None


def test_extract_step_progress_prefers_step_over_page():
    text = "Step 2 of 5. Showing page 1 of 3 reviews."
    assert booking_agent.extract_step_progress(text) == (2, 5)


# ── handle_booking_progress_observation ──────────────────────────────────────

def test_handle_booking_progress_injects_progress_guidance_on_advance():
    state = booking_agent.BookingProgressState()
    result = booking_agent.handle_booking_progress_observation(
        "Step 1 of 5: Choose your seat", state, "example.com"
    )
    assert "[BOOKING_FLOW_PROGRESS]" in result
    assert state.last_step == (1, 5)
    assert state.stall_count == 0

    result2 = booking_agent.handle_booking_progress_observation(
        "Step 2 of 5: Add extras", state, "example.com"
    )
    assert "[BOOKING_FLOW_PROGRESS]" in result2
    assert state.last_step == (2, 5)
    assert state.stall_count == 0


def test_handle_booking_progress_stall_then_escalates():
    state = booking_agent.BookingProgressState()
    observation = "Step 2 of 5: Add extras"

    # First observation establishes the baseline step.
    booking_agent.handle_booking_progress_observation(observation, state, "example.com")
    assert state.stall_count == 0

    # Repeated same-step observations accumulate stalls.
    result = booking_agent.handle_booking_progress_observation(observation, state, "example.com")
    assert "[BOOKING_FLOW_STALLED]" in result
    assert state.stall_count == 1

    result2 = booking_agent.handle_booking_progress_observation(observation, state, "example.com")
    assert "[BOOKING_FLOW_STALLED]" in result2
    assert state.stall_count == 2

    with pytest.raises(ObstacleInputNeeded) as exc_info:
        booking_agent.handle_booking_progress_observation(observation, state, "example.com")
    assert exc_info.value.match.category == "booking"
    assert exc_info.value.match.obstacle_type == "stuck_step"
    assert exc_info.value.match.requires_human_input is True


def test_handle_booking_progress_noop_text_when_no_progress_indicator():
    state = booking_agent.BookingProgressState()
    observation = "Checkout wizard loaded, no step indicator here."
    result = booking_agent.handle_booking_progress_observation(observation, state, "example.com")
    assert result == observation
    assert state.last_step is None


def test_handle_booking_progress_injects_spec_guidance_once():
    state = booking_agent.BookingProgressState()
    observation = "Step 1 of 5: Choose your seat"
    result = booking_agent.handle_booking_progress_observation(
        observation, state, "example.com",
        spec_guidance="\n\n[BOOKING_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert "[BOOKING_AGENT_SPEC]" in result
    assert state.spec_injected is True

    result2 = booking_agent.handle_booking_progress_observation(
        "Step 2 of 5: Add extras", state, "example.com",
        spec_guidance="\n\n[BOOKING_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert result2.count("[BOOKING_AGENT_SPEC]") == 0


# ── ObstacleMatch/build_input_form integration for the "booking" category ──

def test_build_input_form_for_booking_asks_open_ended_guidance():
    match = ObstacleMatch(category="booking", obstacle_type="stuck_step", requires_human_input=True)
    form = build_input_form(match, "example.com")
    assert form["title"] == "Booking Flow Stuck"
    field = form["sections"][0]["fields"][0]
    assert field["type"] == "text"
    assert form["obstacle_category"] == "booking"
