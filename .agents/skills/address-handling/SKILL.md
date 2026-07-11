---
name: address-handling
description: >
  Address autocomplete interaction agent — deterministic handler for address
  suggestion dropdowns. Scores suggestions against requested address components,
  auto-selects high-confidence matches, and escalates ambiguous cases to the user.
---

## What It Does

When the browser agent encounters an address autocomplete dropdown (like Google Places
or similar widgets), this agent takes over to ensure the correct suggestion is selected
instead of blindly clicking the first one.

## Runtime Files

- **Agent Spec**: [address.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/address.agent.md)
  — Decision Tree (character-by-character typing, instant selection on confident match),
  Hard Rules (never assume first suggestion, never invent address components).
- **Deterministic Module**: [address_agent.py](file:///d:/Project/SciParser/Backend/src/services/address_agent.py)
  — `extract_requested_address_components()`, `detect_address_autocomplete_context()`,
  `handle_address_dropdown_observation()`, `handle_address_verification_observation()`,
  `AddressAutocompleteState`.
- **Integration Point**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — Lines ~1498-1523 in `_call_tool()`.

## How It's Activated

Only when ALL of these are true:
1. Task `confirmed_inputs` contain address-like fields
2. No CAPTCHA is blocking the page (`_captcha_type` is falsy)
3. `detect_address_autocomplete_context(observation)` returns True

## Key Patterns

- **Character-by-character typing**: The spec instructs the LLM to type one character
  at a time and check for suggestions after each keystroke.
- **Confidence scoring**: `handle_address_dropdown_observation()` scores each suggestion
  against the requested components and appends `[ADDRESS_AUTOCOMPLETE_DETECTED]` or
  `[ADDRESS_AUTOCOMPLETE_LOW_CONFIDENCE]` blocks.
- **Escalation**: After one retry on low confidence, the system pauses the run and asks
  the user to pick the correct address.
- **Suppress on resume**: When resuming after user confirmation, `suppress_address_agent=True`
  skips re-running the scoring logic.
