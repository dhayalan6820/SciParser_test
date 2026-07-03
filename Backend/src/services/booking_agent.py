"""
Booking / Pagination Interaction Agent — deterministic support layer around
multi-step flow navigation (checkout wizards, booking flows, paginated
listing/selection screens).

Same pattern as `address_agent.py`: the Browser agent still does the actual
clicking; this module gives it (and Brain's tool-loop) the deterministic
piece a raw LLM should never be trusted to eyeball on its own — whether the
flow is actually making progress, or the agent is clicking "Next"/"Continue"
against the same step over and over without noticing:

  1. `detect_multistep_context` — recognizes, from a tool observation, that
     the current page is part of a multi-step flow (step/page progress
     indicator, wizard, or paginated listing).
  2. `extract_step_progress` — parse the current/total step (or page) number
     out of the observation text.
  3. `build_progress_guidance` — the text injected confirming the step
     actually advanced.
  4. `build_stall_guidance` — one-time nudge when the step number hasn't
     changed since the last observation.

Escalation to the user (the flow is stuck on the same step after repeated
attempts — usually a required field the agent can't identify, or a blocking
validation error) reuses the generic obstacle pause/resume framework in
`obstacle_handler.py` (category="booking"). This module has ZERO dependency
on LangGraph/Brain so the detection logic can be unit-tested in isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# How many consecutive observations may show the SAME step number before
# escalating to the user as "stuck".
MAX_STALLS = 2

_MULTISTEP_WIDGET_HINTS = [
    r"\bstep\s*\d+\s*(?:of|/)\s*\d+\b",
    r"\bpage\s*\d+\s*(?:of|/)\s*\d+\b",
    r"\bprogress\s*(?:bar)?\b",
    r"\bcontinue\b", r"\bnext step\b", r"\bproceed to\b",
    r"\bcheckout\b", r"\bbooking\b", r"\breservation\b", r"\bwizard\b",
]

_STEP_PROGRESS_RE = re.compile(r"\bstep\s*(\d+)\s*(?:of|/)\s*(\d+)\b", re.IGNORECASE)
_PAGE_PROGRESS_RE = re.compile(r"\bpage\s*(\d+)\s*(?:of|/)\s*(\d+)\b", re.IGNORECASE)


def detect_multistep_context(observation_text: str) -> bool:
    """True if the observation looks like part of a multi-step flow (a
    checkout/booking wizard or paginated listing) — i.e. any of the
    step/page/progress/continue signals are present."""
    if not observation_text:
        return False
    t = str(observation_text).lower()
    return any(re.search(p, t) for p in _MULTISTEP_WIDGET_HINTS)


def extract_step_progress(observation_text: str) -> Optional[Tuple[int, int]]:
    """Return (current, total) step/page number if an explicit progress
    indicator is present in the observation, else None. "Step" indicators
    are checked before "page" ones since a page could legitimately contain
    incidental pagination controls unrelated to the flow's own step count."""
    if not observation_text:
        return None
    text = str(observation_text)
    m = _STEP_PROGRESS_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _PAGE_PROGRESS_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def build_progress_guidance(current: int, total: int) -> str:
    return (
        "\n\n[BOOKING_FLOW_PROGRESS]\n"
        f"Currently on step {current} of {total}. Confirm every required field on "
        "this step is filled in and valid BEFORE clicking Next/Continue — clicking "
        "through with an empty required field is what causes the flow to bounce "
        "back to the same step."
    )


def build_stall_guidance(current: int, total: int, stall_count: int) -> str:
    return (
        "\n\n[BOOKING_FLOW_STALLED]\n"
        f"Still on step {current} of {total} after {stall_count} attempt(s) to "
        "advance — the flow is not progressing. Re-inspect the page for a required "
        "field, validation error, or option that was missed (scroll if needed) "
        "before clicking Next/Continue again. If this happens once more, the run "
        "will pause and ask the user how to proceed."
    )


@dataclass
class BookingProgressState:
    """Per-run tracking for the multi-step-flow stall/escalation policy,
    mirroring `AddressAutocompleteState`."""
    last_step: Optional[Tuple[int, int]] = None
    stall_count: int = 0
    spec_injected: bool = False


def handle_booking_progress_observation(
    observation_text: str,
    state: BookingProgressState,
    task_domain: str,
    spec_guidance: Optional[str] = None,
) -> str:
    """Call when `detect_multistep_context` is True for the current
    observation. Tracks the step/page number across turns and either injects
    a progress confirmation, injects a one-time stall nudge, or raises
    `ObstacleInputNeeded(category="booking", obstacle_type="stuck_step")`
    once the stall budget is exhausted.

    No-op (returns the text unchanged, but still tracks state) if no
    explicit step/page number can be found in this observation — many
    multi-step pages don't repeat the indicator on every single sub-action."""
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if spec_guidance and not state.spec_injected:
        text += spec_guidance
        state.spec_injected = True

    progress = extract_step_progress(text)
    if progress is None:
        return text

    current, total = progress
    if state.last_step == progress:
        state.stall_count += 1
        if state.stall_count > MAX_STALLS:
            raise ObstacleInputNeeded(
                ObstacleMatch(
                    category="booking",
                    obstacle_type="stuck_step",
                    requires_human_input=True,
                ),
                task_domain,
            )
        text += build_stall_guidance(current, total, state.stall_count)
    else:
        state.stall_count = 0
        state.last_step = progress
        text += build_progress_guidance(current, total)

    return text
