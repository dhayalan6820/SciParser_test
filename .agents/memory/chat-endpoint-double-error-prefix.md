---
name: Chat endpoint double error-code prefix
description: /chat/message wraps its own HTTPException raises in a broad except-BaseException, producing "500: <msg>" style detail text
---

The `POST /chat/message` handler in `Backend/src/main.py` raises `HTTPException(status_code=500, detail=...)` for known process_message failures (e.g. "2 parallel tasks" limit, out-of-credits block), but that raise happens inside a `try` block that also has a catch-all `except BaseException as e` further down. The catch-all re-wraps the HTTPException's `str(e)` (which itself is `"500: <detail>"`), so the JSON error body the frontend sees ends up double-prefixed, e.g. `{"detail": "500: You're out of credits..."}`.

**Why:** Discovered while adding credit-balance enforcement (mirrors the pre-existing parallel-task-limit message, which has the same artifact) — confirmed via direct curl against `/chat/message` that the response body contains the doubled prefix.

**How to apply:** This is cosmetic (frontend strips/display still shows the message, just with a stray "500: " prefix) and pre-existing/consistent across all `process_message` early-return failures, not a regression. Don't "fix" it in isolation for a single new failure message — it would make that one inconsistent with the others. If it's ever worth cleaning up, do it once for the whole try/except structure in that endpoint.
