---
name: booking-handling
description: >
  Booking/pagination flow agent — deterministic handler for multi-step wizards
  and checkout flows. Tracks step progress, detects stalled flows, and escalates
  when Next/Continue clicks don't advance the step indicator.
---

## What It Does

When the browser agent is navigating a multi-step booking, checkout, or wizard flow,
this agent tracks which step is currently active and detects when the flow stalls
(clicking Next but staying on the same step).

## Runtime Files

- **Agent Spec**: [booking.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/booking.agent.md)
  — Decision Tree (inspect before clicking Next, verify step advanced, handle stalls),
  Hard Rules (never skip required fields, never assume default options).
- **Deterministic Module**: [booking_agent.py](file:///d:/Project/SciParser/Backend/src/services/booking_agent.py)
  — `detect_multistep_context()`, `handle_booking_progress_observation()`,
  `BookingProgressState`.
- **Integration Point**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — Lines ~1572-1587 in `_call_tool()`.

## How It's Activated

Not gated on `confirmed_inputs` — activates for ANY task when:
1. No CAPTCHA is blocking the page
2. `detect_multistep_context(observation)` returns True (detects "Step X of Y",
   progress bars, checkout wizards)

## Key Patterns

- **Step tracking**: `BookingProgressState` remembers the last seen step number.
- **Stall detection**: If the step number doesn't change after a click, appends
  `[BOOKING_FLOW_STALLED]` block.
- **Escalation**: After one retry on a stalled step, the system pauses and asks the user.
- **Broad activation**: Unlike other agents, this isn't gated on specific confirmed_inputs — any multi-step flow triggers it.
