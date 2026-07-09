# Separate Task Data from Learned Site Lessons

## What & Why
The agent's per-domain memory system (episodic/semantic/procedural/reflection) is meant to let the agent get better at handling a site over time — e.g. learning bot-detection timing quirks or working selectors. In practice, the "Known Facts" (semantic) layer stores whatever an LLM pass extracts from a run's steps with no distinction between a durable, reusable site fact and a value that was only specific to that one task (e.g. a particular input used in that run). It's also injected into a new task regardless of whether the run that produced it actually succeeded. The result: a failed or one-off run can leak task-specific data into a completely unrelated later task on the same domain, instead of the agent only carrying forward general lessons (like how to avoid bot detection there).

## Done looks like
- Only durable, reusable site knowledge (selectors, timing/bot-detection behavior, general navigation facts) is stored and reused as "Known Facts" for a domain — not values that were specific to a particular past task's input or request.
- Semantic facts and procedural skills are only written from episodes that actually succeeded; a failed run's assumptions are never injected into a later task as trusted knowledge.
- Existing reflections/procedural-skill behavior (the "lessons learned" and confidence-scored skills) continues to work as-is — this task narrows what counts as a durable fact, it doesn't remove the memory system.
- Full backend test suite passes, with new tests demonstrating that task-specific values are excluded from stored facts and that facts from a failed episode are not surfaced in a later run's context.

## Out of scope
- Changing the episodic, procedural, or reflection memory layers' existing logic/decay behavior.
- Adding a user-facing UI to view or clear memory (may be a separate follow-up).
- Changing how memory is keyed (still per user+domain).

## Steps
1. **Tighten fact extraction** — Update the semantic-fact extraction so both the rule-based and LLM-assisted paths only capture durable, task-agnostic knowledge about a domain (site mechanics, bot-detection notes, stable selectors/URLs), explicitly excluding values that come from the specific task's inputs/parameters.
2. **Gate storage on success** — Confirm (and enforce, if any gap exists) that semantic facts and procedural skill updates are only written when the source episode outcome was a success, never from a failed run.
3. **Verification** — Add tests covering: a run using clearly task-specific input data does not produce a reusable fact from that data; a failed episode does not contribute new semantic facts or a positive procedural update; existing durable-fact extraction (selectors, timing/bot-detection notes) still works as before. Run the full backend suite to confirm no regression.

## Relevant files
- `Backend/src/services/memory_service.py`
- `Backend/tests/test_observer_verifier_recovery.py`
