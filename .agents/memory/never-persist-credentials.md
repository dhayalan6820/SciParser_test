---
name: Never persist credentials, keep in-memory only
description: Pattern for handling account/credential data that a multi-turn agent needs mid-run without ever writing it to a database.
---

## The problem
A multi-step agent flow (e.g. pause for OTP/CAPTCHA input, then resume) often
needs to carry account/credential values across turns. The easy path is to
stash them in whatever session-state blob already gets written to the
database for continuity — but that means secrets end up sitting in the DB
indefinitely (audit logs, session_state columns, etc.).

**Why:** Users expect that saying "use this password" doesn't mean it's now
permanently stored. Any code path that writes `confirmed_inputs`-style dicts
into a durable log or session table can leak credentials without anyone
noticing, since the leak isn't in the obvious "save credentials" feature —
it's a side effect of generic execution/audit logging.

## How to apply
- Redact before every durable write: build a `_redact_x()` helper that keeps
  field names (for observability) but replaces values with a marker before
  anything reaches a DB column or log table. Apply it at every call site that
  logs/persists the structure, not just the "main" one — audit logs, resume
  state, and step-execution logs are all separate write sites.
- Keep the real values in a plain in-process dict on the long-lived
  orchestrator object (e.g. `self.pending_x: Dict[chat_id, ...]`), popped
  (single-use) when consumed. This works because the orchestrator instance
  persists across requests within one server process lifetime.
- If that in-memory cache is gone (process restarted mid-flow), do NOT fall
  back to whatever redacted placeholder is in the DB — treat it as missing
  and re-prompt the user. Silently using a redacted marker as if it were a
  real value is worse than asking again.
