---
name: recovery-system
description: >
  Failure detection, classification, and recovery subsystem — includes the
  structured Observer (page-state parser), per-action Verifier, deterministic
  failure pre-classifier, and the LLM Critic that generates revised strategies.
---

## What It Does

When a browser tool call fails or produces an unexpected result, the recovery system:
1. **Observes**: Parses the raw observation into a structured `ObservedState` (loading, modal, login form, error, CAPTCHA, URL)
2. **Verifies**: Checks whether the action's expected effect actually occurred
3. **Pre-classifies**: Deterministically categorizes the failure type (TIMEOUT, BROWSER_CRASH, WRONG_PAGE, etc.) before the LLM sees it
4. **Critiques**: The LLM Critic (`ATAG.run_critic()`) generates a REVISED PROMPT with a different strategy

## Runtime Files

- **Recovery Spec**: [recovery.md](file:///d:/Project/SciParser/Backend/src/agents/specs/recovery.md)
  — Full decision tree documentation, 11 failure types (TRANSIENT_BLOCK, WRONG_PLAN,
  MISSING_INPUT, SITE_UNSUPPORTED, TIMEOUT, BROWSER_CRASH, SESSION_EXPIRED,
  UNEXPECTED_REDIRECT, WRONG_PAGE, PERMISSION_DENIED, MISSING_ELEMENT), process for
  adding new branches.
- **Recovery Protocol in Browser Spec**: [browser.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/browser.agent.md)
  — "Recovery Protocol" section (loaded only during `recover` stage).
- **Observer**: [observer.py](file:///d:/Project/SciParser/Backend/src/services/observer.py)
  — `observe()` → `ObservedState` dataclass with flags: `is_loading`, `has_modal`,
  `has_login_form`, `has_error`, `captcha_type`, `otp_type`, `interstitial_type`, `url`.
- **Verifier**: [verifier.py](file:///d:/Project/SciParser/Backend/src/services/verifier.py)
  — `verify_action()` → `ValidationResult` with `passed`, `reason`, `severity` (INFO/WARNING/BLOCKING).
- **Pre-classifier**: [recovery.py](file:///d:/Project/SciParser/Backend/src/services/recovery.py)
  — `classify_failure()` → returns failure type string or None (falls through to LLM).
  Tracks per-domain classification stats.
- **Obstacle Handler**: [obstacle_handler.py](file:///d:/Project/SciParser/Backend/src/services/obstacle_handler.py)
  — `detect_captcha_type()`, `detect_otp()`, `detect_continue_interstitial()`,
  `detect_obstacle()`, `detect_obstacle_from_observed()`, `ObstacleMatch`,
  `ObstacleInputNeeded`, `build_input_form()`.
- **Critic LLM Call**: [ATAG.py](file:///d:/Project/SciParser/Backend/src/services/ATAG.py)
  — `ATAGProcessor.run_critic()` uses `PROMPT_5_MCP_FALLBACK` with the failure reason.

## How It's Activated

- **Observer**: Runs on EVERY tool observation (first thing in `_call_tool()`)
- **Verifier**: Runs on every tool observation after the observer
- **Pre-classifier**: Runs when a tool fails (observation starts with "Error")
- **Critic**: Runs when brain.py detects a failed action needing recovery

## Key Patterns

- **Single parse**: `observe_state()` runs once per observation — all downstream detectors
  read flags from `ObservedState` instead of re-scanning the raw text.
- **Auto-classified branches**: TIMEOUT, BROWSER_CRASH, SESSION_EXPIRED, WRONG_PAGE,
  PERMISSION_DENIED, MISSING_ELEMENT are detected by regex patterns in `recovery.py`.
- **LLM-only branches**: WRONG_PLAN, MISSING_INPUT, SITE_UNSUPPORTED, UNEXPECTED_REDIRECT
  require judgment and are classified by the LLM Critic.
- **Stats tracking**: `get_classification_stats()` returns per-domain classified/unclassified
  counts for monitoring drift.

## Common Issues

- **False positive obstacles**: Bare keyword matches (e.g., "verification code" in page text)
  can trigger OTP/CAPTCHA detection on normal pages. See `.agents/memory/obstacle-detection-false-positives.md`.
- **Missing element cascades**: A single MISSING_ELEMENT failure can trigger multiple retries
  that all fail the same way if the selector is genuinely gone.
