# Address Agent: incremental typing + non-blocking selection

## What & Why
The Address Agent (`Backend/src/agents/specs/address.agent.md` +
`Backend/src/services/address_agent.py`) currently tells the Browser agent to
type the whole requested address in one go, then wait once for the
suggestion list to render before scoring it. In practice, many address
autocomplete widgets only return relevant suggestions once enough characters
have been typed, and the correct match often appears well before the full
address string has been entered — waiting for a full-string retype cycle
wastes turns and can even overshoot past the field's expected input length.
Separately, once a correct suggestion is selected, the current verification
step can stall progress on a target site that has already moved past the
address step (e.g. into a plan/package-selection page) even though the
selection itself succeeded — the agent should not block forward progress
just because a "visible submit button" or additional verification chrome
around the address field is still being checked for.

This task adds two behavior changes to the Address Agent's decision
procedure:
1. **Incremental (char-by-char) typing with per-character suggestion
   checks** — instead of typing the full address then waiting once, the
   agent types one character at a time and re-checks the suggestion list
   after each character, so it can react to the correct suggestion the
   moment it appears rather than always typing to completion first.
2. **Immediate selection + non-blocking continuation** — the instant a
   high-confidence suggestion appears during incremental typing, the agent
   clicks it immediately (stops typing further characters). After that,
   whether or not a "submit" control becomes visible right away is
   informational only — it must never block the agent from proceeding to
   (or recognizing) a subsequent page/step the target site navigates to
   (e.g. a plan/package selection page) as a result of the address being
   accepted.

## Done looks like
- `address.agent.md`'s decision tree documents the incremental typing loop:
  click the field, type one character, check for a rendered suggestion list
  matching the requested address with high confidence, and only continue
  typing the next character if no confident match is found yet (bounded by
  the full requested address length so it never types past that).
- The moment a high-confidence suggestion is detected mid-typing, the spec
  instructs the agent to stop typing and click that suggestion immediately
  — it does not first finish typing the rest of the address.
- The verification step after selection is reframed as non-blocking: it
  confirms the field reflects the chosen suggestion for logging/escalation
  purposes, but explicitly does NOT gate or delay the agent from continuing
  once the target site has moved on (e.g. redirected to a plan-selection
  page) — a "submit" button being visible or not visible is not a
  precondition for proceeding.
- `Backend/src/services/address_agent.py`'s detection/guidance functions
  support this incremental flow: the address-autocomplete context detector
  and suggestion scoring can be invoked after a partial (not just complete)
  typed value, and `build_address_guidance` communicates "select now, do not
  keep typing" when a confident match is found early.
- `handle_address_verification_observation` (or equivalent) no longer treats
  "no submit button visible yet" or "page already navigated" as a failure
  condition — only an actual mismatched field value (verification failure)
  still triggers the existing retry/escalation path.
- Existing high-confidence auto-select, low-confidence retry, and
  escalation-to-user behavior are preserved — this task changes *when*
  typing/checking happens and *what counts as blocking*, not the
  scoring/escalation policy itself.

## Out of scope
- Changing the scoring algorithm/weights in `score_suggestion`.
- Changing the escalation/pause-for-user flow itself (still reuses the
  existing `ObstacleInputNeeded` pause/resume mechanism).
- Any other agent spec (booking, calendar, login, browser, planner).
- Frontend changes — this is Browser-agent/tool-loop behavior only.

## Steps
1. **Update `address.agent.md`** — rewrite the decision tree's typing step
   to describe character-by-character entry with a suggestion check after
   each character, immediate click on first high-confidence match, and an
   explicit rule that a visible/invisible submit control or a site
   navigating onward (e.g. to a plan page) never blocks proceeding once
   selection is verified.
2. **Support partial-input scoring in `address_agent.py`** — ensure
   `detect_address_autocomplete_context`, `extract_suggestions`, and
   `score_suggestions` work correctly when called against a suggestion list
   rendered from a partially-typed address, not only a fully-typed one.
3. **Adjust guidance text** — update `build_address_guidance` (or add a
   variant) so the injected instruction to the Browser agent tells it to
   stop typing and click immediately, rather than implying typing is
   already finished.
4. **Make verification non-blocking** — adjust
   `handle_address_verification_observation` (and any caller in
   `brain.py`) so that the absence of a submit button, or evidence the page
   has already advanced (e.g. new page content/URL after selection), is
   treated as a benign "selection succeeded, site moved on" case rather
   than an unverifiable/failed state that would trigger retry or
   escalation. Only a genuinely mismatched field value should still count
   as a verification failure.
5. **Tests** — add/update unit tests in
   `Backend/tests/test_address_agent.py` covering: a high-confidence match
   found after a partial (not full) typed prefix, guidance text reflecting
   "stop typing, click now," and verification treating a navigated-away/no
   visible-submit observation as success rather than escalation.

## Relevant files
- `Backend/src/agents/specs/address.agent.md`
- `Backend/src/services/address_agent.py`
- `Backend/src/services/brain.py`
- `Backend/tests/test_address_agent.py`
