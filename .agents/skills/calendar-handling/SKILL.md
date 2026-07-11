---
name: calendar-handling
description: >
  Calendar/date-picker interaction agent — deterministic handler for date selection
  widgets. Scores visible day cells against the requested date, auto-selects
  confident matches, and escalates ambiguous or unavailable dates to the user.
---

## What It Does

When the browser agent encounters an open calendar/date-picker widget and the task
requires selecting a specific date, this agent ensures the correct day cell is clicked
rather than guessing at the first visible day.

## Runtime Files

- **Agent Spec**: [calendar.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/calendar.agent.md)
  — Decision Tree (navigate to correct month, click detected day cell, verify field value),
  Hard Rules (never click wrong month, never round dates, verify before proceeding).
- **Deterministic Module**: [calendar_agent.py](file:///d:/Project/SciParser/Backend/src/services/calendar_agent.py)
  — `extract_requested_dates()`, `detect_calendar_widget_context()`,
  `handle_calendar_widget_observation()`, `handle_calendar_verification_observation()`,
  `CalendarSelectionState`.
- **Integration Point**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — Lines ~1525-1550 in `_call_tool()`.

## How It's Activated

Only when ALL of these are true:
1. Task `confirmed_inputs` contain date-like fields (check-in, check-out, date, etc.)
2. No CAPTCHA is blocking the page
3. `detect_calendar_widget_context(observation)` returns True

## Key Patterns

- **Month navigation first**: The spec requires navigating to the correct month/year
  before looking for day cells.
- **Confidence blocks**: Appends `[CALENDAR_DATE_DETECTED]` or `[CALENDAR_LOW_CONFIDENCE]`
  to guide the LLM.
- **Verification**: After selecting, the agent re-inspects the field value to confirm
  the selection took effect.
- **Escalation**: After one retry, pauses the run for user input.
