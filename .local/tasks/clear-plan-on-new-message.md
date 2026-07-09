# Clear Old Plan and Reasoning on New Message

## What & Why
When the user sends a new message while a previous agent run has completed, the old plan steps and old "AGENT REASONING" thoughts persist on screen until the WebSocket delivers the first `plan_update` event for the new run — which can take several seconds. The user sees stale reasoning from the previous task (e.g. old AT&T address text) while the new task is already starting.

The root cause is in `handleSendMessage` (chat_page.tsx ~line 1056): only `setAiThinking(null)` is called to reset thought state. Neither `setCurrentPlan(null)` nor `setTaskThoughts({})` is cleared at that point.

- `currentPlan` holds the old task steps (e.g. "Navigate and Initialize" with AT&T reasoning)
- `taskThoughts` is a `Record<string, string>` mapping each task ID to its last reasoning string — these persist across messages because they're only ever merged with `{ ...th, [active.id]: msg.data }` and never reset

## Done looks like
- Immediately after the user hits Send, the agent plan panel goes blank (no old task steps visible)
- Old AGENT REASONING text disappears instantly — it does not linger until the new WebSocket data arrives
- New plan steps and new reasoning appear progressively as the new process starts, with no flash of old content

## Out of scope
- Changes to WebSocket message handling or backend plan state
- Any changes to agent-plan.tsx display logic

## Steps
1. **Clear plan and thought state on message send** — In `handleSendMessage` in `chat_page.tsx`, alongside the existing `setAiThinking(null)` call, add `setCurrentPlan(null)` and `setTaskThoughts({})` so all three state values are reset together the moment a new message is submitted.

## Relevant files
- `Frontend/src/components/ui/chat_page.tsx:1050-1060`
