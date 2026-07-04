---
name: In-place message mutation breaks LLM prefix caching
description: Rebuilding an earlier message's content every LLM call (e.g. to inject growing dynamic context) invalidates provider prefix caching for the whole history that follows it.
---

Injecting growing per-turn context (task summary, running memory) by mutating
an existing, earlier message's content on every LLM call makes that message
byte-different from the previous call's version of it. Providers with
implicit/explicit prefix caching (Gemini, Anthropic, etc.) key on exact
prefix match — once one message in the middle of the history changes, every
message after it in that call is also treated as new, uncached content, even
if those later messages themselves didn't change.

**Why:** Discovered while trying to reduce per-step token/cost in a
LangGraph tool-calling loop (Backend/src/services/brain.py) — the code
re-wrote the last HumanMessage's content each turn to prepend a growing
"TASK CONTEXT" block, which silently defeated the static-system-prompt
caching the code assumed was working end-to-end.

**How to apply:** When injecting per-turn dynamic context into an LLM
message chain, append it as a new trailing message instead of rewriting an
earlier one in place. This keeps everything before the new message a stable,
growing prefix across calls, maximizing cache hits.
