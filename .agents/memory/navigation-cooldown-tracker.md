---
name: Navigation Cooldown Tracker
description: Per-domain failure counter for browser_navigate with automatic 60s cooldown after 3 consecutive failures.
---

## Rule
After 3 consecutive `browser_navigate` failures on the same domain, block further navigation attempts to that domain for 60 seconds. Return a cooldown message to the LLM instead of executing the tool, so the agent can try a different strategy (search, alternative URL, etc.) rather than burning tokens hammering a blocked site.

## Implementation
The tracker lives as an in-memory dict on the `Brain` instance:

```python
self._nav_failure_tracker: Dict[str, Dict[str, Any]] = {}
# domain -> {"count": int, "last_fail_ts": float, "cooldown_until": float}
```

Key methods:
- `_extract_domain(url)`: parses host via `urllib.parse.urlparse`
- `_record_nav_failure(domain)`: increments count; if count >= 3, sets `cooldown_until = now + 60`
- `_record_nav_success(domain)`: deletes the entry, resetting the tracker
- `_is_nav_blocked(domain)`: returns `True` only if `cooldown_until > 0` and `now < cooldown_until`
- `_nav_cooldown_message(domain)`: returns the message injected into the LLM observation

## Where it fires
Inside `_call_tool()` in `brain.py`:
1. **Pre-execution**: if `browser_navigate` target domain is blocked, raise `_NavigationCooldownSkip()` and skip the actual `ainvoke()`
2. **Post-execution**: inspect the observation. If `status == SUCCESS` with no error markers, call `_record_nav_success()`. Otherwise, call `_record_nav_failure()`.

## Critical gotcha (fixed during implementation)
The original `_is_nav_blocked` check was `if now > entry.get("cooldown_until", 0)`, which is always true when `cooldown_until == 0` (i.e. before 3 failures). Any code that polled `_is_nav_blocked` after the 1st or 2nd failure would silently wipe the tracker, so the counter never reached 3. The fix: only block when `cooldown_until > 0`, and only delete when `cooldown_until > 0 and now > cooldown_until`.

## Why 3 strikes / 60 seconds
These are tunable class constants (`MAX_NAV_FAILURES = 3`, `NAV_COOLDOWN_SECONDS = 60`). Chosen empirically:
- 3 failures is enough to distinguish a genuine transient error from a site that is actively blocking the bot
- 60 seconds gives the site time to rotate any rate-limit counters without being overly punitive

## Testing
Dedicated unit tests in `Backend/tests/test_nav_cooldown.py` cover domain parsing, failure counting, cooldown activation, expiration, success reset, and per-domain isolation. No MCP or DB needed — pure Brain instance tests.