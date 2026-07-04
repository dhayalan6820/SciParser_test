---
name: Credit deduction timing and source of truth
description: Where/when token-based credit deduction happens for chat runs, and which column holds real usage data.
---

Credit balance checks and deductions for chat/automation usage are centered on `AgentExecutionLog.token_usage` (a JSON blob with input/output/total-style keys), not the unused `Message.token_usage` column. Any future usage/billing feature should read from `AgentExecutionLog`, not `Message`.

Deduction happens exactly once per chat run, in the `finally:` block of the message-processing entrypoint (not at each return/error site), by summing token usage across every `AgentExecutionLog` row written during that run. This guarantees exactly-once billing regardless of whether the run succeeded, errored, or paused on an obstacle (CAPTCHA/OTP).

**Why:** the run can exit through many different code paths (success, exception, obstacle-pause-for-user-input); billing logic scattered across each exit point would be easy to double-charge or miss. Centralizing in `finally` avoids that.

**How to apply:** if you add a new way for a chat/automation run to end early, don't add separate billing logic there — make sure it still flows through the same `finally` block. If you add a new LLM call path that logs usage somewhere other than `AgentExecutionLog`, either route it through that table or explicitly extend the deduction summation logic.

Known gap (not addressed): automation script-generation calls (e.g. a `run_script_generation` step) don't currently expose token usage, so credits aren't deducted for that sub-flow — only the manual/scheduled "run" entrypoints enforce the zero-credit block.
