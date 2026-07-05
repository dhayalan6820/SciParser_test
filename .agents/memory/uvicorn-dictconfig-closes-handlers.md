---
name: uvicorn dictConfig closes pre-existing logging handlers
description: Custom logging.Handler subclasses attached before uvicorn.run() get silently killed by uvicorn's own logging setup
---

`uvicorn.Config.configure_logging()` calls `logging.config.dictConfig()`
during startup, which internally calls `logging.shutdown()` on every
handler that already exists at that point (via `_clearExistingHandlers()`)
— including custom handlers attached to app-specific loggers before
`uvicorn.run()` was invoked (e.g. in an app module imported ahead of the
`uvicorn.run()` call).

**Why:** A custom handler with background-thread/worker-loop state (e.g. a
DB-backed log handler batching writes) that stops that worker in `close()`
will process exactly one batch then permanently go silent moments after
startup, with no exception surfaced anywhere — `logging.shutdown()` calls
`handler.close()` and swallows any errors from it.

**How to apply:** If a custom `logging.Handler` owns a background
worker/thread that must survive for the process lifetime, don't tie its
lifecycle to `close()`. Either make `close()` a no-op for stopping the
worker (safe if it's a daemon thread — it'll die with the process anyway),
or attach/configure such handlers only after uvicorn's own logging setup
has run (e.g. inside the FastAPI lifespan startup, not at module import
time).
