---
name: login-handling
description: >
  Login/signup form interaction agent — deterministic handler for credential
  field disambiguation. Maps credential values to the correct form fields,
  detects login rejections, and escalates after one retry instead of looping.
---

## What It Does

When the browser agent encounters a login or signup form and the task supplied
credentials, this agent maps each credential value to the correct field (email vs.
username, password vs. confirm-password) so the LLM doesn't guess wrong.

## Runtime Files

- **Agent Spec**: [login.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/login.agent.md)
  — Decision Tree (identify fields, type into mapped fields only, detect rejections),
  Hard Rules (never click Forgot Password, never try alternate credentials).
- **Deterministic Module**: [login_agent.py](file:///d:/Project/SciParser/Backend/src/services/login_agent.py)
  — `extract_requested_credentials()`, `detect_login_form_context()`,
  `handle_login_form_observation()`, `LoginFormState`.
- **Integration Point**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — Lines ~1552-1570 in `_call_tool()`.

## How It's Activated

Only when ALL of these are true:
1. Task `confirmed_inputs` contain credential-like fields (email, username, password)
2. No CAPTCHA is blocking the page
3. `detect_login_form_context(observation)` returns True

## Key Patterns

- **Field mapping**: Appends `[LOGIN_FORM_DETECTED]` block naming exactly which field
  should receive which credential.
- **Rejection detection**: Appends `[LOGIN_REJECTED: ...]` when the site shows an
  explicit error after submission.
- **One retry policy**: Resubmit once after re-checking field mapping. If rejected again,
  the system pauses and asks the user.
- **Mode detection**: Checks if the form is Sign In vs. Create Account and instructs
  the agent to switch if needed.
