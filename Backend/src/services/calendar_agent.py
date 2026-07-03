"""
Calendar Interaction Agent — deterministic support layer around date-picker /
calendar widgets (check-in/check-out, appointment dates, single-date pickers).

Same pattern as `address_agent.py`: the Browser agent still does the actual
clicking; this module gives it (and Brain's tool-loop) the deterministic
pieces a raw LLM should never be trusted to eyeball on its own:

  1. `detect_calendar_widget_context` — recognizes, from a tool observation,
     that a date field with an open calendar/date-picker widget is on screen.
  2. `extract_requested_dates` / `has_requested_date` — pull the date(s) the
     user actually asked for out of `confirmed_inputs` (a single date, or a
     check-in/check-out range).
  3. `extract_calendar_cells` — parse the visible day-cell strings out of the
     observation text.
  4. `score_cell` / `score_cells` — numeric confidence that a given cell
     matches one of the requested dates.
  5. `verify_selected_value` — after a selection, confirm the field's final
     value actually reflects the chosen date.
  6. `build_calendar_guidance` — the text injected into the next turn's
     observation (mirrors the address-agent injection pattern in brain.py).

Escalation to the user (low confidence, or the requested date not being
offered at all) reuses the generic obstacle pause/resume framework in
`obstacle_handler.py` (category="calendar"). This module has ZERO dependency
on LangGraph/Brain so the scoring/detection logic can be unit-tested in
isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Cell auto-selected without asking the user only above this score.
HIGH_CONFIDENCE_THRESHOLD = 0.75

# Max automatic retries (re-opening/re-navigating the calendar) before escalating.
MAX_RETRIES = 1

# Keys in confirmed_inputs that hold a single requested date.
_SINGLE_DATE_KEYS = [
    "date", "appointment_date", "booking_date", "event_date",
    "reservation_date", "visit_date", "target_date", "selected_date",
]

# Keys that hold the start/end of a requested date range.
_RANGE_START_KEYS = [
    "check_in", "check_in_date", "checkin", "checkin_date",
    "arrival_date", "start_date",
]
_RANGE_END_KEYS = [
    "check_out", "check_out_date", "checkout", "checkout_date",
    "departure_date", "end_date",
]

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _month_from_name(name: str) -> Optional[int]:
    key = name.strip().lower()[:3]
    return _MONTHS.get(key)


def _parse_date_string(text: str) -> Optional[Dict[str, int]]:
    """Best-effort parse of a date out of free text into
    {"year": int?, "month": int?, "day": int}. Returns None if no day can be
    confidently identified. This is intentionally lightweight — good enough
    for scoring calendar cells, not a full date-parsing library."""
    if not text:
        return None
    t = text.strip()

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        return {"year": int(m.group(1)), "month": int(m.group(2)), "day": int(m.group(3))}

    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
    if m:
        return {"year": int(m.group(3)), "month": int(m.group(1)), "day": int(m.group(2))}

    m = re.search(r"\b([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?\b", t)
    if m:
        month = _month_from_name(m.group(1))
        if month:
            result = {"month": month, "day": int(m.group(2))}
            if m.group(3):
                result["year"] = int(m.group(3))
            return result

    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s*(\d{4})?\b", t)
    if m:
        month = _month_from_name(m.group(2))
        if month:
            result = {"month": month, "day": int(m.group(1))}
            if m.group(3):
                result["year"] = int(m.group(3))
            return result

    # Bare day number (typical of a plain calendar-grid cell, e.g. "15")
    m = re.match(r"^\s*(\d{1,2})\s*$", t)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            return {"day": day}

    return None


def has_requested_date(confirmed_inputs: Optional[Dict[str, Any]]) -> bool:
    """True if `confirmed_inputs` contains anything resembling a requested
    date (single date or a check-in/check-out range)."""
    if not confirmed_inputs:
        return False
    for key in _SINGLE_DATE_KEYS + _RANGE_START_KEYS + _RANGE_END_KEYS:
        val = confirmed_inputs.get(key)
        if isinstance(val, str) and val.strip():
            return True
    return False


def extract_requested_dates(confirmed_inputs: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Return a dict of parsed requested dates, keyed "date" for a single
    date, or "check_in"/"check_out" for a range. Only keys that parsed
    successfully are included."""
    if not confirmed_inputs:
        return {}

    result: Dict[str, Dict[str, int]] = {}
    for key in _SINGLE_DATE_KEYS:
        val = confirmed_inputs.get(key)
        if isinstance(val, str) and val.strip():
            parsed = _parse_date_string(val)
            if parsed:
                result["date"] = parsed
                break

    for key in _RANGE_START_KEYS:
        val = confirmed_inputs.get(key)
        if isinstance(val, str) and val.strip():
            parsed = _parse_date_string(val)
            if parsed:
                result["check_in"] = parsed
                break

    for key in _RANGE_END_KEYS:
        val = confirmed_inputs.get(key)
        if isinstance(val, str) and val.strip():
            parsed = _parse_date_string(val)
            if parsed:
                result["check_out"] = parsed
                break

    return result


# ── Calendar-widget context detection ───────────────────────────────────────

_CALENDAR_WIDGET_HINTS = [
    r"role=[\"']?grid\b", r"role=[\"']?gridcell", r"\bdatepicker\b", r"\bdate[- ]picker\b",
    r"\bcalendar\b", r"\bselect (?:a |the )?date\b", r"\bchoose (?:a |the )?date\b",
    r"\bpick (?:a |the )?date\b", r"\bavailable dates?\b", r"\bnext month\b", r"\bprevious month\b",
]

_CALENDAR_FIELD_HINTS = [
    r"\bdate\b", r"\bcheck-?in\b", r"\bcheck-?out\b", r"\barrival\b", r"\bdeparture\b",
    r"\bappointment\b", r"\bbooking\b", r"\breservation\b", r"\bschedule\b",
]


def detect_calendar_widget_context(observation_text: str) -> bool:
    """True if the observation shows a date field with an open calendar /
    date-picker widget. Requires BOTH a calendar-widget signal AND a
    date-related field signal so we don't fire on unrelated grids."""
    if not observation_text:
        return False
    t = str(observation_text).lower()
    has_widget = any(re.search(p, t) for p in _CALENDAR_WIDGET_HINTS)
    has_field = any(re.search(p, t) for p in _CALENDAR_FIELD_HINTS)
    return has_widget and has_field


# ── Day-cell extraction ──────────────────────────────────────────────────────

_CELL_LINE_RE = re.compile(
    r'''(?:gridcell|button|option)\s+["']([^"'\n]{1,60})["']''',
    re.IGNORECASE,
)

_NAV_NOISE_RE = re.compile(
    r"\b(next|previous|prev|close|clear|cancel|apply|today|month|year)\b", re.IGNORECASE
)


def extract_calendar_cells(observation_text: str) -> List[str]:
    """Pull candidate day-cell strings out of an observation. Best-effort:
    skips nav-control buttons (next/previous month, close, etc.) and cells
    that don't parse to a day number."""
    if not observation_text:
        return []
    text = str(observation_text)
    candidates: List[str] = []
    for match in _CELL_LINE_RE.finditer(text):
        candidate = match.group(1).strip()
        if not candidate:
            continue
        if _NAV_NOISE_RE.search(candidate) and not re.search(r"\d{1,2}.{0,10}\d{4}", candidate):
            continue
        if _parse_date_string(candidate) is None:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


# ── Scoring ──────────────────────────────────────────────────────────────────

def _score_against_one(parsed_cell: Dict[str, int], requested: Dict[str, int]) -> float:
    """Score a parsed cell against a single requested date, weighting only
    the components present in BOTH (a bare day-number cell can't be
    penalized for missing month/year, which the visible calendar page
    implies but individual cells rarely repeat)."""
    if "day" not in parsed_cell or "day" not in requested:
        return 0.0
    if parsed_cell["day"] != requested["day"]:
        return 0.0
    score = 0.6  # day matches
    comparable = 0.6
    if "month" in parsed_cell and "month" in requested:
        comparable += 0.3
        if parsed_cell["month"] == requested["month"]:
            score += 0.3
    if "year" in parsed_cell and "year" in requested:
        comparable += 0.1
        if parsed_cell["year"] == requested["year"]:
            score += 0.1
    return round(score / comparable, 4) if comparable else 0.0


def score_cell(cell_text: str, requested_dates: Dict[str, Dict[str, int]]) -> Tuple[float, Optional[str]]:
    """Confidence (0.0-1.0) that `cell_text` matches one of the requested
    dates, and WHICH requested slot ("date" | "check_in" | "check_out") it
    best matches."""
    parsed = _parse_date_string(cell_text)
    if not parsed or not requested_dates:
        return 0.0, None
    best_score, best_slot = 0.0, None
    for slot, requested in requested_dates.items():
        s = _score_against_one(parsed, requested)
        if s > best_score:
            best_score, best_slot = s, slot
    return best_score, best_slot


def score_cells(
    cells: List[str], requested_dates: Dict[str, Dict[str, int]]
) -> List[Tuple[str, float, Optional[str]]]:
    """Score every cell, returned sorted highest-confidence first."""
    scored = [(c, *score_cell(c, requested_dates)) for c in cells]
    scored.sort(key=lambda triple: triple[1], reverse=True)
    return scored


# ── Post-selection verification ─────────────────────────────────────────────

_DATE_FIELD_VALUE_RE = re.compile(
    r'''(?:date|check-?in|check-?out)[^\n]{0,40}?(?:value|:)\s*[:=]?\s*["']([^"'\n]{4,60})["']''',
    re.IGNORECASE,
)


def extract_date_field_value(observation_text: str) -> Optional[str]:
    """Best-effort extraction of the CURRENT VALUE of the date input field
    from a tool observation. Returns None when it cannot be confidently
    located — callers must treat that as "cannot verify"."""
    if not observation_text:
        return None
    match = _DATE_FIELD_VALUE_RE.search(str(observation_text))
    if match:
        return match.group(1).strip()
    return None


def verify_selected_value(field_value: Optional[str], chosen_cell: str) -> bool:
    """True if the date field's own current value reflects the day that was
    clicked (fuzzy — a field may reformat to a full date string)."""
    if not field_value or not chosen_cell:
        return False
    parsed_field = _parse_date_string(field_value)
    parsed_chosen = _parse_date_string(chosen_cell)
    if not parsed_field or not parsed_chosen:
        return False
    return parsed_field.get("day") == parsed_chosen.get("day")


# ── Guidance injected into the tool-loop ─────────────────────────────────────

def build_calendar_guidance(
    top_choice: str, score: float, slot: Optional[str], candidates: List[Tuple[str, float, Optional[str]]]
) -> str:
    ranked = "\n".join(f"  {i+1}. \"{c}\" (confidence {s:.2f})" for i, (c, s, _) in enumerate(candidates[:6]))
    slot_label = {"date": "the requested date", "check_in": "check-in", "check_out": "check-out"}.get(slot or "", "the requested date")
    return (
        "\n\n[CALENDAR_DATE_DETECTED]\n"
        f"Best-matching day cell for {slot_label} (confidence {score:.2f}, above the "
        f"{HIGH_CONFIDENCE_THRESHOLD:.2f} auto-select threshold):\n"
        f"  \"{top_choice}\"\n\n"
        f"All candidates considered:\n{ranked}\n\n"
        "Click exactly this day cell. After clicking it, re-inspect the date field's "
        "value and confirm it reflects this date before moving on. Never click a "
        "different day than the one named here, even if it looks close."
    )


def build_calendar_retry_guidance(requested_dates: Dict[str, Dict[str, int]], candidates: List[Tuple[str, float, Optional[str]]]) -> str:
    ranked = "\n".join(f"  - \"{c}\" (confidence {s:.2f})" for c, s, _ in candidates[:6])
    requested_str = ", ".join(f"{slot}={vals}" for slot, vals in requested_dates.items())
    return (
        "\n\n[CALENDAR_LOW_CONFIDENCE]\n"
        f"None of the visible day cells confidently match the requested date(s) "
        f"({requested_str}):\n{ranked}\n\n"
        "Do NOT click any of these. Navigate the calendar (next/previous month) to "
        "the month that actually contains the requested date and re-inspect. This "
        "is your last automatic retry before the user will be asked to confirm the date."
    )


@dataclass
class CalendarSelectionState:
    """Per-run tracking for the calendar-widget escalation policy, mirroring
    `AddressAutocompleteState`."""
    retries: int = 0
    candidates: List[Tuple[str, float, Optional[str]]] = field(default_factory=list)
    pending_selection: Optional[str] = None
    spec_injected: bool = False


# ── Orchestration: the two decision points Brain's tool-loop calls into ─────

def handle_calendar_widget_observation(
    observation_text: str,
    requested_dates: Dict[str, Dict[str, int]],
    state: CalendarSelectionState,
    task_domain: str,
    spec_guidance: Optional[str] = None,
) -> str:
    """Call when `detect_calendar_widget_context` is True for the current
    observation. Extracts + scores day cells and either injects
    high-confidence auto-select guidance, injects one-time retry guidance, or
    raises `ObstacleInputNeeded(category="calendar",
    obstacle_type="low_confidence_selection")` once the retry budget is
    exhausted."""
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if spec_guidance and not state.spec_injected:
        text += spec_guidance
        state.spec_injected = True

    cells = extract_calendar_cells(text)
    if not cells:
        return text

    scored = score_cells(cells, requested_dates)
    top_choice, top_score, top_slot = scored[0]
    if top_score >= HIGH_CONFIDENCE_THRESHOLD:
        text += build_calendar_guidance(top_choice, top_score, top_slot, scored)
        state.pending_selection = top_choice
        state.candidates = scored
    elif state.retries < MAX_RETRIES:
        text += build_calendar_retry_guidance(requested_dates, scored)
        state.retries += 1
        state.candidates = scored
    else:
        raise ObstacleInputNeeded(
            ObstacleMatch(
                category="calendar",
                obstacle_type="low_confidence_selection",
                requires_human_input=True,
                candidates=[c for c, _, _ in scored[:5]],
            ),
            task_domain,
        )
    return text


def handle_calendar_verification_observation(
    observation_text: str,
    state: CalendarSelectionState,
    task_domain: str,
) -> str:
    """Call on the turn after an auto-selected day has closed the calendar
    widget. Verifies the date field's own value reflects the selection;
    either clears `pending_selection`, injects a one-time retry note, or
    raises `ObstacleInputNeeded(category="calendar",
    obstacle_type="verification_failed")` once the retry budget is exhausted.

    No-op if there is nothing pending to verify."""
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if not state.pending_selection:
        return text

    field_value = extract_date_field_value(text)
    verified = verify_selected_value(field_value, state.pending_selection)
    if verified:
        state.pending_selection = None
    elif state.retries < MAX_RETRIES:
        text += (
            "\n\n[CALENDAR_VERIFICATION_FAILED]\n"
            f"The date field does not appear to reflect the selected day "
            f"\"{state.pending_selection}\". Re-open the calendar and re-select "
            "the correct date."
        )
        state.retries += 1
        state.pending_selection = None
    else:
        raise ObstacleInputNeeded(
            ObstacleMatch(
                category="calendar",
                obstacle_type="verification_failed",
                requires_human_input=True,
                candidates=[c for c, _, _ in state.candidates[:5]],
            ),
            task_domain,
        )
    return text
