---
name: Verifying prompt-bloat / step-count risk without a live LLM run
description: How to reproduce and measure per-step agent-loop overhead offline when a live LLM run isn't available
---

When asked to confirm that a per-tool-call hardening step (observer/verifier/
recovery classifier, etc.) doesn't regress token usage or step count on
longer multi-step agent runs, but a live end-to-end run isn't available
(quota, missing browser infra, cost), don't just read the code and assert
it's fine — reproduce the *exact* function-call sequence the production loop
runs per tool result (e.g. `observe()` -> `verify_action()` ->
`_compress_observation_for_llm()`) over a synthetic multi-step sequence with
a realistic mix of success/failure/blocked steps, and measure directly:

- wall-clock time per step (confirms no LLM/network call snuck in)
- character/token delta added vs. the pre-hardening baseline (raw
  observation with no note), and whether that delta is bounded to
  failing/warning steps only or compounds per step regardless of outcome
- whether the addition survives existing truncation/summarization budgets
  (e.g. a short EXECUTION MEMORY excerpt) or bypasses them

**Why:** This is testable without any LLM call because these hardening
steps are pure deterministic string/regex logic — the actual token-cost
risk lives in whether their output text growth is bounded per occurrence or
compounds with run length, which a synthetic harness proves cheaply and
precisely.

**How to apply:** Write it as a permanent pytest test (not a throwaway
script) asserting the bound (e.g. "delta < 2% of baseline", "note length <
200 chars", "second-half average step time not >> first-half average"), so
future changes to the same pipeline stay honest about this property. Always
flag that a live confirmation run is still a recommended follow-up when
this technique is used as a substitute.
