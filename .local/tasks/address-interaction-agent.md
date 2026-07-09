# Address Interaction Agent

## What & Why
Address autocomplete widgets are the most fragile part of automation today — the single browser agent currently just "clicks a matching suggestion" with no confidence check, no verification, and no fallback when it's unsure. Add a dedicated Address Agent spec with a deterministic confidence/verification layer around address selection, following the project's existing `*.agent.md` spec pattern, so address entry stops being a guess and becomes a scored, verifiable decision — escalating to the user only when genuinely uncertain.

## Done looks like
- A new `address.agent.md` spec exists describing the address agent's rules, decision tree, and escalation policy, loaded the same way `browser.agent.md` is today.
- When the live browser agent hits an address field with an autocomplete dropdown, it types naturally, waits for suggestions to stabilize (network/DOM based, not fixed sleeps), and extracts every visible suggestion instead of assuming the first one is correct.
- Each suggestion is scored against the requested address components (street, house/unit number, city, postal code, country); the suggestion is only auto-selected above a high-confidence threshold.
- After selection, the agent verifies the input's final value actually reflects the chosen suggestion before moving on.
- If confidence is low or verification fails, the run pauses and asks the user to pick from the candidate suggestions — reusing the existing OTP-style "pause and ask" flow already used for verification codes — instead of guessing or silently continuing.
- Retries are capped (max 1 retry) before escalating, so the agent never loops forever on a bad autocomplete widget.

## Out of scope
- Calendar, Login, Signup, Pagination, Table, Booking, Broadband, or Data Aggregation agents from the pasted proposal — future follow-up work.
- A full standalone "Interaction Router" microservice or a separate state-machine execution engine replacing the LangGraph loop — this task adapts the address logic into the existing spec + tool-loop architecture rather than building new infrastructure.
- Changing how CAPTCHA is handled.

## Steps
1. **Author the Address Agent spec** — Write `address.agent.md` with the address-specific role, decision tree (type → wait for suggestions → extract → score → select if confident → verify → escalate if not), and hard rules (never assume the first suggestion, never invent addresses, retry only once), matching the frontmatter/section format used by the existing agent specs.
2. **Detect address-autocomplete context** — Add a deterministic detector (alongside the existing obstacle detection) that recognizes, from the current page observation/tool result, that an address field with an open suggestion list is present and that a requested address was supplied.
3. **Score suggestions against the requested address** — Build a deterministic scoring function comparing extracted suggestion text against the requested street, house/unit number, city, postal code, and country, producing a numeric confidence score.
4. **Inject Address Agent guidance into the running loop** — When address context is detected, feed the Address Agent's rules/decision tree into the next turn of the existing browser tool-loop (same mechanism already used to inject stored CAPTCHA-bypass steps), rather than switching to a separate graph.
5. **Verify the final selection** — After the agent selects a suggestion, deterministically re-check the input's resulting value (and any linked hidden fields, where readable) against the top-scored suggestion before allowing the run to proceed.
6. **Escalate low-confidence matches to the user** — When confidence is below the threshold or verification fails, pause the run and surface the candidate suggestions to the user through the existing pause/resume input-form flow, then resume with the user's chosen address.
7. **Add tests** — Cover the scoring function, the address-context detector, and the escalation trigger (low confidence and failed verification both pause the run) with unit tests.

## Relevant files
- `Backend/src/agents/specs/browser.agent.md`
- `Backend/src/agents/spec_loader.py`
- `Backend/src/services/brain.py`
- `Backend/src/services/obstacle_handler.py`
- `Backend/tests/test_obstacle_handler.py`
