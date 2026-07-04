---
name: Domain-keyed episodic memory confounds A/B runs
description: Why comparing agent behavior/token usage across two code versions on the same target domain can give misleading results unless memory is cleared between runs.
---

The browser agent's long-term memory (episodic + semantic, in `MemoryService` /
`MemoryEpisodic` / `MemorySemantic` tables) is keyed by `domain`, not by
`chat_id` or run id. Every completed run on a domain stores an episode and
extracted facts that get injected into the prompt ("[Memory] Injecting N
chars for domain ...") on the *next* run against that same domain, regardless
of which chat/session/user triggered it.

**Why:** This makes naive before/after comparisons (e.g. measuring token usage
or step count for a code change by running "old code" then "new code" against
the same test site) unreliable — the second run isn't seeing a cold start, it's
seeing memory left over from the first run (and any earlier runs), which can
change the agent's path, number of LLM calls, and obstacle-handling behavior
independently of the code change being measured. A run with roughly 2x the
LLM calls of another isn't necessarily a regression — it may just have hit an
obstacle-handling detour (e.g. false-positive CAPTCHA detection) enabled by
stale memory/context from a prior run.

**How to apply:** Before running paired/A-B comparisons that touch a shared
target domain, delete the relevant `memory_episodic` and `memory_semantic`
rows for that domain first (there's no built-in "clear domain" helper — do it
directly via SQL, e.g. `DELETE FROM memory_episodic WHERE domain = '...'`).
Run each side of the comparison back-to-back with memory cleared immediately
before it, and confirm both runs saw the same LLM call count as a sanity
check that the comparison is actually apples-to-apples.
