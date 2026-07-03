---
name: Chat-history precedence in LLM prompts
description: When raw chat history/session state is injected into an LLM prompt for extraction tasks, the model may silently reuse old values instead of a user's new explicit input unless told otherwise.
---

## The problem
Steps that build an LLM prompt from `history_context` (recent chat turns, prior
session state, etc.) alongside the current user message can cause the model to
pull an older value (e.g. a credential, account, or other confirmed input)
back in even when the user just gave a new one — because nothing in the
prompt says which source should win when they conflict.

**Why:** LLMs treat all prompt content as equally authoritative by default.
Without an explicit precedence instruction, "recent chat history" and "current
request" are just more context to blend together, so a stale value mentioned
earlier in the conversation can silently override a fresh instruction.

## How to apply
- Any prompt that concatenates history/session-state context with the current
  user message needs an explicit rule: "if the current message conflicts with
  something in history, the current message always wins for this turn; use
  history only to fill in what the current message doesn't mention."
- For high-stakes fields (credentials, accounts, payment info), consider also
  detecting explicit "switch/override" phrasing in the current message and
  adding a stronger directive ("ignore old values entirely, ask if missing")
  rather than relying only on the general precedence rule.
- Put the rule in both the runtime-built prompt AND any static system-prompt
  spec file the model also reads, so it survives even if one is refactored
  independently of the other.
