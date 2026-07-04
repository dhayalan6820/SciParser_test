---
name: Recovery classifier fallback tracking
description: How to make a deterministic pre-classifier's drift observable without adding new infrastructure
---

When a deterministic pre-classifier (regex/pattern-match) sits in front of an
LLM judgment call as a hint layer, its accuracy erodes silently as new
inputs (new sites, new error text) appear that don't match any known
pattern. Nothing fails loudly — the system just falls back to the LLM path
more often, and that "more often" is invisible unless you look for it.

**Rule:** whenever you add or maintain this kind of pre-classifier, have it
record a per-key (e.g. per-domain) counter of matched-vs-fell-through calls,
and emit a log line on each fall-through. Keep it in-memory/process-lifetime
— do not build persistence or a dashboard unless asked; the log line plus an
in-process snapshot getter is enough to make drift discoverable via grep or
a debug read, and avoids scope creep into a metrics platform.

**Why:** this was the actual ask for Task #156 (adapting
`Backend/src/services/recovery.py`'s `classify_failure()` as new failure
patterns are learned) — the fix wasn't a smarter classifier, it was making
the *existing* classifier's blind spots observable so a human/agent knows
when and where to add a new branch.

**How to apply:** pair the counter/log with a short "process for adding a
new branch" doc (grep logs for the fall-through signal → decide auto vs.
LLM judgment → add pattern → add test → keep docs in sync). Don't try to
auto-generate new branches from the data; the judgment call about whether a
pattern is mechanically detectable vs. needs real reasoning stays manual.
