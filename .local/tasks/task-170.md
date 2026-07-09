---
title: Store application logs in database
---
# Store application logs in the database instead of a single log file

## Context
Currently, `Backend/src/utils/logger.py` configures Python's standard `sciparser` logger with:
- A console handler (stdout)
- A `RotatingFileHandler` writing to `Backend/logs/sciparser-log` (5MB rotation, 5 backups)

This is separate from the existing structured DB logging tables already used for
execution tracking (`AgentExecutionLog`, `ToolExecutionLog`, `LoginEvent`,
`ScheduleRun` in `Backend/src/database/chat_db.py`). Those tables capture
domain-specific events (agent runs, tool calls, logins, scheduled jobs), not
general application/system log lines (info/warning/error messages emitted via
`logger.info(...)`, `logger.error(...)`, etc. throughout the codebase).

The user wants general application logs (the ones currently going to the
rotating file) to be persisted in the database instead of a single file, so
they can be queried/inspected without SSHing into the file system, and are
consistent with the rest of the app's DB-centric structure.

## Goal
Replace (or supplement, TBD with user during implementation) the
`RotatingFileHandler` in `Backend/src/utils/logger.py` with a custom logging
handler that writes log records into a new database table, while keeping the
console handler for live workflow visibility.

## Scope
- Add a new SQLAlchemy model (e.g. `AppLog`) in `Backend/src/database/chat_db.py`
  with fields like: timestamp, level, logger name, message, module/function
  (optional), and any relevant context.
- Implement a custom `logging.Handler` subclass that writes each log record to
  this table (batched/async-safe — must not block the event loop or fail hard
  if the DB is briefly unavailable; failures in the log handler itself must
  never crash the app).
- Wire this handler into `Backend/src/utils/logger.py` alongside (or replacing)
  the existing file handler.
- Add basic retention/cleanup consideration (e.g. periodic purge of old rows,
  or a cap) so the table doesn't grow unbounded — mirror any existing patterns
  used for other log tables if present.
- Do not touch the existing console handler behavior (needed for workflow logs
  in the Replit UI) or the existing structured tables
  (`AgentExecutionLog`/`ToolExecutionLog`/`LoginEvent`/`ScheduleRun`).
- If there's an admin UI for viewing activity/logs already, consider (but do
  not require) surfacing these new general logs there — confirm with user if
  in scope before building UI.

## Out of scope
- Changing how `AgentExecutionLog`, `ToolExecutionLog`, `LoginEvent`, or
  `ScheduleRun` work — those already persist to DB correctly.
- Building a full admin log viewer UI unless explicitly requested.

## Acceptance criteria
- Application log messages (info/warning/error emitted via the `sciparser`
  logger) are persisted to a database table.
- The rotating file handler is removed (or clearly justified if kept
  alongside, per user preference).
- Console/workflow log output is unaffected.
- Existing test suite (292 tests) continues to pass; add basic tests for the
  new DB log handler if practical.
- The app must not crash or hang if a DB write for logging fails (e.g. DB
  briefly down) — log handler failures must be silently caught.

## Relevant files
- `Backend/src/utils/logger.py`
- `Backend/src/database/chat_db.py`
- `Backend/start.sh`, `Backend/run.py` (startup wiring, if needed)