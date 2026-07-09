# Plan Panel: Sub-step Labels, Inline Reasoning & Stage Indicator

## What & Why
Three visual issues in the live agent plan panel make it hard to follow what the agent is doing:

1. **Blank loading dots** — sub-steps inside a running task show only a spinning circle with no text, so the user can't tell what each one is.
2. **Reasoning block is at a fixed position** — the "Agent Reasoning" thought box always renders at the bottom of the entire task card, detached from the sub-step it belongs to.
3. **No active-stage indicator** — there is no persistent, prominent display of *which step is currently executing*. The blue border on the active task card is easy to miss, and once the card is collapsed (auto-collapse on complete) the context is completely gone.

## Done looks like
- Every sub-step row shows a readable label while loading; if the backend sends an empty title the UI shows a fallback like "Step N" so there is always text next to the spinner.
- The Agent Reasoning block appears directly beneath the currently active sub-step (inline in the sub-step list) instead of as a fixed footer block after all sub-steps. When there are no sub-steps, it remains below the task description.
- A persistent "Currently running" banner (or highlighted header strip) is pinned inside the plan panel header area — it shows the active task number and title at all times while a task is in-progress, so the user always knows which stage is executing even when other tasks are collapsed or scrolled out of view.

## Out of scope
- Changes to what data the backend sends for sub-step titles or stages.
- Any other plan panel styling or layout changes beyond the three fixes above.

## Steps
1. **Fix blank sub-step labels** — In the subtask list render, when `sub.title` is falsy, display a fallback string (`"Step ${index + 1}"`) so the spinner always has a readable label beside it.
2. **Move reasoning inline** — Remove the Agent Reasoning block from its fixed bottom position. Render it immediately below the currently active sub-step inside the subtask loop. When there are no sub-steps, keep it below the task description as before.
3. **Add a "currently running" stage indicator** — Inside the plan panel header (below the progress bar or just above the task list), show a small strip that reads something like `"Executing · Step 02 — Capture screenshot of verification page"` while any task is in-progress. Hide it when no task is running. Keep it compact so it doesn't take significant vertical space.

## Relevant files
- `Frontend/src/components/ui/agent-plan.tsx:44-351`
- `Frontend/src/components/ui/chat_page.tsx:128-134`
