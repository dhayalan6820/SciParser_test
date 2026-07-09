# Never reuse OTP codes; never store sensitive data anywhere

## What & Why
Two related trust/security issues in the obstacle-handling flow (OTP pause/resume, added in Task #114) and the credential-redaction work (Task #116):

1. OTP codes are single-use and expire — each time the agent hits an OTP wall it must ask for and use a **brand-new** code, never retry with a code that was already submitted earlier in the same run or a prior run. Right now the agent can end up retrying a previously-submitted code instead of asking the user for a fresh one, which will always fail since the site already consumed or expired it.
2. Sensitive values (passwords, card details, OTP codes) must never be written to any durable storage — not just `ChatSession.session_state` (already redacted in Task #116), but also `Message.content` (the user's raw form-submission chat message), `ToolExecutionLog.tool_input`/`tool_output`, `AgentExecutionLog` fields not yet covered, `MemoryEpisodic.key_steps`, and any semantic-memory fact extraction. The system should ask the user again whenever it needs one of these values rather than ever reading it back from storage.

## Done looks like
- After a user submits an OTP code and the site rejects it or the obstacle recurs, the agent does not resubmit the same code — it treats the obstacle as unresolved, discards the old code, and prompts the user again for a new one (clearly explaining that codes are single-use/expire).
- Grepping the database after a run that involved a password, card number, or OTP code never turns up the plaintext value in `messages`, `tool_execution_logs`, `agent_execution_logs`, or any `memory_*` table — every persisted record shows a redacted placeholder instead.
- If the app needs a previously-provided secret again later (e.g. after a restart) it explicitly re-asks the user via the existing NEEDS_INPUT form rather than silently reusing a stored value.
- No regression to the legitimate CAPTCHA-skill learning behavior or the account-override behavior from Task #116.

## Out of scope
- Changing what data types are considered "sensitive" beyond OTP codes, passwords, and payment/card details.
- Building a dedicated secrets vault or encryption-at-rest system — the requirement is "don't store it," not "store it securely."

## Steps
1. **Stop OTP code reuse across attempts** — When an obstacle recurs after a submitted OTP code (i.e. the site still shows the OTP/verification prompt after resuming), treat it as a fresh obstacle occurrence rather than replaying the previous answer: clear any cached value for that attempt and issue a new NEEDS_INPUT prompt telling the user the code was invalid/expired and to provide a new one.
2. **Redact sensitive values before they reach any persisted table** — Extend the existing redaction pattern (`_redact_confirmed_inputs`) so it also covers what gets written into chat `Message.content` for form-submission answers, `ToolExecutionLog.tool_input`/`tool_output`, and any `MemoryEpisodic`/semantic-memory record that might capture a typed value. Detect likely secret fields generically (password/otp/card/cvv/security-code style field names or the known obstacle categories) rather than hardcoding one field.
3. **Confirm no silent fallback to stored placeholders** — Audit every place a previously-redacted value could be read back and used as if it were real (e.g. resuming from `session_state` after a restart) and make sure those paths always re-prompt the user instead.
4. **Add regression tests** — Cover: (a) OTP retry-with-stale-code is rejected and a fresh prompt is issued instead of reusing the old value, (b) a full obstacle-pause run leaves no plaintext secret in any table checked directly via the test DB, and (c) existing CAPTCHA/credential-override test suites still pass unchanged.

## Relevant files
- `Backend/src/services/brain.py`
- `Backend/src/services/obstacle_handler.py`
- `Backend/src/services/memory_service.py`
- `Backend/tests/test_obstacle_handler.py`
- `Backend/tests/test_credential_override.py`
