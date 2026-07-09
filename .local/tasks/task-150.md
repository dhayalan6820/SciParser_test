---
title: Reduce agent token usage per tool step
---
# Reduce Agent Token Usage Per Step

## What & Why
The agent's browser/tool loop resends the full conversation history on every step and only compresses it once a single global threshold is crossed. This makes token (and cost) usage per tool step grow faster than necessary during long-running sessions, without any corresponding gain in answer quality. Tighten the summarization and observation-handling logic so token usage drops meaningfully while the agent keeps the context it actually needs to make good decisions.

## Done looks like
- Long-running sessions use noticeably fewer prompt tokens per step (visible in the existing per-step token/cost logging), without a regression in task success/quality.
- History is compressed earlier and more incrementally instead of only once a large global threshold is hit.
- Tool observations (e.g. large HTML/accessibility-tree dumps) are trimmed more intelligently than a flat character cutoff, preserving the meaningful signal.
- No change to user-visible behavior, screenshots/streaming, or the shape of tool outputs returned to the frontend.

## Out of scope
- Changing which LLM/model is used or its pricing.
- Any change to the WebSocket screenshot streaming path (screenshots are already excluded from LLM history).
- New analytics/dashboards for token usage (only the existing per-step logging needs to keep working).

## Steps
1. **Earlier, incremental history summarization** — Lower the point at which history gets summarized and/or summarize incrementally as the conversation grows, instead of waiting for one large global token threshold to be crossed.
2. **Smarter observation compression** — Replace the flat character-count truncation of large tool observations (e.g. page HTML/accessibility trees) with logic that strips redundant/irrelevant content first, so truncation removes low-signal text rather than arbitrarily cutting off useful content.
3. **Trim older tool messages more aggressively** — Keep full detail only for the most recent steps; fold older tool observations into the existing execution-memory summary rather than carrying them verbatim in the message chain.
4. **Extend prompt caching to stable dynamic context** — Where the dynamic context block (task summary, confirmed inputs) stays unchanged between steps, structure it so it benefits from the same prefix caching already used for the static system prompt.
5. **Validate no quality regression** — Confirm token counts drop across a representative multi-step run while task completion and output quality are unaffected, using the existing per-step token/cost logging (no new dashboards needed).

## Relevant files
- `Backend/src/services/brain.py:63`
- `Backend/src/services/brain.py:70`
- `Backend/src/services/brain.py:73`
- `Backend/src/services/brain.py:201`
- `Backend/src/services/brain.py:792`
- `Backend/src/services/brain.py:922-963`
- `Backend/src/services/brain.py:1075`
- `Backend/src/services/brain.py:1233-1288`