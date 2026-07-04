# Recovery Decision Tree

This document is the human-readable reference for the browser agent's
recovery decision tree. The text actually loaded into the Critic's prompt at
runtime lives in the **"Recovery Protocol (used by the Critic on failure)"**
section of `browser.agent.md` (loaded via `spec_loader.load_spec("browser")`
in `ATAG.run_critic`) — this file documents the same tree for readability
and must be kept in sync whenever that section changes.

A cheap, deterministic pre-classifier (`src/services/recovery.py:
classify_failure`) runs before the LLM critic call and supplies a
`FAILURE_TYPE` hint for the mechanically-detectable branches below (marked
**[auto]**). The LLM critic always makes the final call — the hint only
saves it from re-deriving what pattern-matching already answered
confidently. Branches without **[auto]** require judgment about intent and
are classified by the LLM alone.

## Branches

1. **`TRANSIENT_BLOCK`** — a temporary bot-detection wall, rate limit, or
   slow load. **Action:** retry the same mission with a fresh browser
   identity (new user-agent, reset session).
2. **`WRONG_PLAN`** — the mission/strategy doesn't fit this site's actual
   flow. **Action:** Planner regenerates the mission; do not retry the same
   instructions verbatim.
3. **`MISSING_INPUT`** — execution revealed a required piece of information
   never collected from the user. **Action:** stop and ask, don't keep
   retrying.
4. **`SITE_UNSUPPORTED`** — a hard blocker no retry can fix (login wall with
   no credentials, CAPTCHA with no bypass, page permanently unreachable).
   **Action:** stop and report clearly instead of consuming retries.
5. **`TIMEOUT`** **[auto]** — an action or navigation exceeded its wait
   budget (spinner never resolved, element never appeared, network call
   never returned). **Action:** retry once with a longer explicit wait /
   re-check for a loading indicator before the next attempt; escalate to
   `TRANSIENT_BLOCK` handling if it times out twice in a row.
6. **`BROWSER_CRASH`** **[auto]** — the browser process/tab/context closed
   or disconnected mid-run (target closed, WebSocket closed, execution
   context destroyed). **Action:** close and fully re-launch the session
   (not just retry the tool call) before resuming the mission from the last
   confirmed state.
7. **`SESSION_EXPIRED`** **[auto]** — an authenticated session that was
   valid earlier in the run is no longer valid (logged out, "please sign in
   again", auth cookie rejected). **Action:** re-run login if credentials
   are available in CONFIRMED INPUTS; otherwise treat as `MISSING_INPUT`
   (ask the user to re-authenticate) rather than retrying blindly.
8. **`UNEXPECTED_REDIRECT`** — a navigation or submission landed on a URL
   the mission did not intend (host/path differs from the requested
   target, with no error text explaining why). **Action:** re-inspect
   what page was actually reached; if it's a legitimate intermediate step
   (e.g. an SSO hop) continue, otherwise navigate back to the intended URL
   before retrying the original action.
9. **`WRONG_PAGE`** **[auto]** — landed on a 404/error page or a page that
   doesn't match the mission's expected content (search yielded nothing,
   product page shows a different item). **Action:** navigate back and
   retry the previous step with a corrected selector/URL/query, not the
   exact same input.
10. **`PERMISSION_DENIED`** **[auto]** — an explicit 401/403/"access
    denied"/"you don't have permission" response. **Action:** treat as
    `SITE_UNSUPPORTED` unless a plausible fix exists (e.g. missing
    credentials the user can supply), in which case treat as
    `MISSING_INPUT`.
11. **`MISSING_ELEMENT`** **[auto]** — a selector/element the plan expected
    could not be found ("no such element", "could not find button/field").
    **Action:** re-inspect the current page for a renamed/moved
    equivalent (synonym label, parent container) before concluding the
    site's layout changed; if still not found after one retry, treat as
    `WRONG_PLAN`.

## Output format (unchanged)

```
THINKING: <root cause + visual clues from the page state>
FAILURE_TYPE: <one of the eleven types above>
REVISED PROMPT: <the complete, updated execution instructions, or — for
MISSING_INPUT/SITE_UNSUPPORTED — an explanation of what to tell the user>
```
