"""Tests for the deterministic Calendar Interaction Agent support layer
(src/services/calendar_agent.py): context detection, requested-date
extraction, day-cell extraction/scoring, and post-selection verification.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest

from src.services import calendar_agent
from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch, build_input_form


# ── has_requested_date / extract_requested_dates ────────────────────────────

def test_has_requested_date_true_for_single_date_key():
    assert calendar_agent.has_requested_date({"date": "2026-03-15"}) is True


def test_has_requested_date_true_for_range_keys():
    assert calendar_agent.has_requested_date({"check_in": "2026-03-15", "check_out": "2026-03-20"}) is True


def test_has_requested_date_false_when_absent():
    assert calendar_agent.has_requested_date({"destination": "Paris"}) is False
    assert calendar_agent.has_requested_date({}) is False
    assert calendar_agent.has_requested_date(None) is False


def test_extract_requested_dates_parses_iso_single_date():
    dates = calendar_agent.extract_requested_dates({"date": "2026-03-15"})
    assert dates["date"] == {"year": 2026, "month": 3, "day": 15}


def test_extract_requested_dates_parses_range():
    dates = calendar_agent.extract_requested_dates(
        {"check_in_date": "March 15, 2026", "check_out_date": "March 20, 2026"}
    )
    assert dates["check_in"] == {"month": 3, "day": 15, "year": 2026}
    assert dates["check_out"] == {"month": 3, "day": 20, "year": 2026}


def test_extract_requested_dates_empty_when_absent():
    assert calendar_agent.extract_requested_dates({}) == {}
    assert calendar_agent.extract_requested_dates(None) == {}


# ── detect_calendar_widget_context ──────────────────────────────────────────

def test_detect_calendar_widget_context_true_when_grid_and_date_field_present():
    text = 'Check-in date field open. Calendar widget: role="grid" with day cells below.'
    assert calendar_agent.detect_calendar_widget_context(text) is True


def test_detect_calendar_widget_context_false_without_widget():
    text = "Check-in date: 2026-03-15. Form submitted successfully."
    assert calendar_agent.detect_calendar_widget_context(text) is False


def test_detect_calendar_widget_context_false_without_date_field():
    text = 'Country dropdown role="grid" open.'
    assert calendar_agent.detect_calendar_widget_context(text) is False


def test_detect_calendar_widget_context_false_on_empty():
    assert calendar_agent.detect_calendar_widget_context("") is False
    assert calendar_agent.detect_calendar_widget_context(None) is False


# ── extract_calendar_cells ───────────────────────────────────────────────────

def test_extract_calendar_cells_parses_day_cells():
    observation = (
        "Calendar open, March 2026:\n"
        'gridcell "13"\n'
        'gridcell "14"\n'
        'gridcell "15"\n'
        'button "Next month"\n'
    )
    cells = calendar_agent.extract_calendar_cells(observation)
    assert "13" in cells
    assert "14" in cells
    assert "15" in cells
    assert "Next month" not in cells


def test_extract_calendar_cells_returns_empty_for_no_matches():
    assert calendar_agent.extract_calendar_cells("Nothing relevant here.") == []
    assert calendar_agent.extract_calendar_cells("") == []


# ── score_cell / score_cells ─────────────────────────────────────────────────

def test_score_cell_high_for_exact_day_match():
    requested = {"date": {"year": 2026, "month": 3, "day": 15}}
    score, slot = calendar_agent.score_cell("March 15, 2026", requested)
    assert score >= calendar_agent.HIGH_CONFIDENCE_THRESHOLD
    assert slot == "date"


def test_score_cell_bare_day_number_matches_requested_day():
    requested = {"date": {"year": 2026, "month": 3, "day": 15}}
    score, slot = calendar_agent.score_cell("15", requested)
    assert score >= calendar_agent.HIGH_CONFIDENCE_THRESHOLD
    assert slot == "date"


def test_score_cell_zero_for_wrong_day():
    requested = {"date": {"year": 2026, "month": 3, "day": 15}}
    score, slot = calendar_agent.score_cell("16", requested)
    assert score == 0.0
    assert slot is None


def test_score_cell_zero_for_empty_inputs():
    assert calendar_agent.score_cell("", {"date": {"day": 15}}) == (0.0, None)
    assert calendar_agent.score_cell("15", {}) == (0.0, None)


def test_score_cells_sorted_descending():
    requested = {"date": {"year": 2026, "month": 3, "day": 15}}
    cells = ["16", "March 15, 2026"]
    scored = calendar_agent.score_cells(cells, requested)
    assert scored[0][0] == "March 15, 2026"
    assert scored[0][1] >= scored[1][1]


# ── verify_selected_value / extract_date_field_value ────────────────────────

def test_verify_selected_value_true_for_matching_day():
    assert calendar_agent.verify_selected_value("March 15, 2026", "15") is True


def test_verify_selected_value_false_for_mismatched_day():
    assert calendar_agent.verify_selected_value("March 16, 2026", "15") is False


def test_verify_selected_value_false_for_empty_inputs():
    assert calendar_agent.verify_selected_value("", "15") is False
    assert calendar_agent.verify_selected_value("March 15, 2026", "") is False


def test_extract_date_field_value_from_quoted_value_attribute():
    text = 'textbox "Check-in date" value="March 15, 2026"'
    assert calendar_agent.extract_date_field_value(text) == "March 15, 2026"


def test_extract_date_field_value_none_when_absent():
    text = "Page loaded. Submit button visible. No date information here."
    assert calendar_agent.extract_date_field_value(text) is None


# ── handle_calendar_widget_observation / handle_calendar_verification_observation ──

_NO_MATCH_OBSERVATION = (
    'Calendar widget open: role="grid" with day cells below.\n'
    'gridcell "1"\n'
    'gridcell "2"\n'
)


def test_handle_calendar_widget_high_confidence_injects_guidance_and_sets_pending():
    state = calendar_agent.CalendarSelectionState()
    observation = (
        'Calendar widget open: role="grid" with day cells below.\n'
        'gridcell "March 15, 2026"\n'
    )
    result = calendar_agent.handle_calendar_widget_observation(
        observation,
        {"date": {"year": 2026, "month": 3, "day": 15}},
        state,
        "example.com",
    )
    assert "[CALENDAR_DATE_DETECTED]" in result
    assert state.pending_selection == "March 15, 2026"
    assert state.retries == 0


def test_handle_calendar_widget_low_confidence_retries_once_then_escalates():
    state = calendar_agent.CalendarSelectionState()
    requested = {"date": {"year": 2026, "month": 3, "day": 15}}

    result = calendar_agent.handle_calendar_widget_observation(
        _NO_MATCH_OBSERVATION, requested, state, "example.com"
    )
    assert "[CALENDAR_LOW_CONFIDENCE]" in result
    assert state.retries == 1

    with pytest.raises(ObstacleInputNeeded) as exc_info:
        calendar_agent.handle_calendar_widget_observation(
            _NO_MATCH_OBSERVATION, requested, state, "example.com"
        )
    assert exc_info.value.match.category == "calendar"
    assert exc_info.value.match.obstacle_type == "low_confidence_selection"
    assert exc_info.value.match.requires_human_input is True


def test_handle_calendar_widget_injects_spec_guidance_once():
    state = calendar_agent.CalendarSelectionState()
    observation = (
        'Calendar widget open: role="grid" with day cells below.\n'
        'gridcell "March 15, 2026"\n'
    )
    result = calendar_agent.handle_calendar_widget_observation(
        observation,
        {"date": {"year": 2026, "month": 3, "day": 15}},
        state,
        "example.com",
        spec_guidance="\n\n[CALENDAR_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert "[CALENDAR_AGENT_SPEC]" in result
    assert state.spec_injected is True

    result2 = calendar_agent.handle_calendar_widget_observation(
        observation,
        {"date": {"year": 2026, "month": 3, "day": 15}},
        state,
        "example.com",
        spec_guidance="\n\n[CALENDAR_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert result2.count("[CALENDAR_AGENT_SPEC]") == 0


def test_handle_calendar_verification_success_clears_pending_selection():
    state = calendar_agent.CalendarSelectionState(pending_selection="March 15, 2026")
    observation = 'textbox "Date" value="March 15, 2026"'
    result = calendar_agent.handle_calendar_verification_observation(observation, state, "example.com")
    assert state.pending_selection is None
    assert "[CALENDAR_VERIFICATION_FAILED]" not in result


def test_handle_calendar_verification_failure_retries_once_then_escalates():
    state = calendar_agent.CalendarSelectionState(
        pending_selection="March 15, 2026",
        candidates=[("March 15, 2026", 0.9, "date")],
    )
    bad_observation = 'textbox "Date" value="March 16, 2026"'

    result = calendar_agent.handle_calendar_verification_observation(bad_observation, state, "example.com")
    assert "[CALENDAR_VERIFICATION_FAILED]" in result
    assert state.retries == 1
    assert state.pending_selection is None

    state.pending_selection = "March 15, 2026"
    with pytest.raises(ObstacleInputNeeded) as exc_info:
        calendar_agent.handle_calendar_verification_observation(bad_observation, state, "example.com")
    assert exc_info.value.match.category == "calendar"
    assert exc_info.value.match.obstacle_type == "verification_failed"


def test_handle_calendar_verification_noop_when_nothing_pending():
    state = calendar_agent.CalendarSelectionState()
    observation = 'textbox "Date" value="March 15, 2026"'
    result = calendar_agent.handle_calendar_verification_observation(observation, state, "example.com")
    assert result == observation


# ── ObstacleMatch/build_input_form integration for the "calendar" category ──

def test_build_input_form_for_calendar_lists_candidates_as_select_options():
    match = ObstacleMatch(
        category="calendar", obstacle_type="low_confidence_selection",
        requires_human_input=True, candidates=["March 15, 2026", "March 16, 2026"],
    )
    form = build_input_form(match, "example.com")
    assert form["title"] == "Confirm Date"
    field = form["sections"][0]["fields"][0]
    assert field["type"] == "select"
    values = [opt["value"] for opt in field["options"]]
    assert "March 15, 2026" in values
    assert "__none__" in values


def test_build_input_form_for_calendar_without_candidates_asks_for_text():
    match = ObstacleMatch(
        category="calendar", obstacle_type="date_unavailable",
        requires_human_input=True, candidates=None,
    )
    form = build_input_form(match, "example.com")
    assert form["title"] == "Date Unavailable"
    field = form["sections"][0]["fields"][0]
    assert field["type"] == "text"
