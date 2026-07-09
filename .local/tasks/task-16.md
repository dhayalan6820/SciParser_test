---
title: Show tool logs with plan context for script generation
---
# Include tool logs with plan for script generation

## What & Why
Currently the scheduler sends only message IDs and a few selected tool IDs to
the backend when creating a schedule. The AI script generator is missing the
rich tool execution context (what tools ran, what they returned) that lives in
the tool log, so generated scripts lack the real-world output data needed to
reproduce the task accurately.

The fix is simple: when the user clicks "Create Schedule", automatically attach
all SUCCESS/COMPLETED tool logs — tool name + truncated output — as context
alongside the AI plan and user prompt. No tool-picker UI is required. The MCP
TOOLS tab becomes a read-only summary of what will be included.

Token cost is kept in check by:
1. Sending only SUCCESS / COMPLETED tools (skip FAILED / IN_PROGRESS)
2. Truncating each tool output to 500 characters on the frontend before sending

## Done looks like
- The MCP TOOLS tab shows all available toolLogs as read-only cards (tool
  name, status badge, truncated output preview) — no empty-state "please
  select" message
- The count badge on the tab reflects how many SUCCESS tools will be sent
- When "Create Schedule" is submitted, the payload includes every SUCCESS
  tool's name and output (truncated to 500 chars) as inline context alongside
  the plan — the backend receives richer context for better script generation
- FAILED / IN_PROGRESS tools are excluded automatically

## Out of scope
- Checkbox / toggle selection UI for individual tools
- Changing backend API signatures (frontend only)
- Paginating or searching the tool list

## Steps
1. **Show all toolLogs in the MCP TOOLS tab** — Replace the
   `filteredTools`-only grid with a full list of `toolLogs`. Each card shows
   tool name, status badge (colour-coded), and a truncated output preview.
   Cards for SUCCESS tools get a highlighted border; FAILED ones are dimmed.
2. **Update the tab badge count** — Count only SUCCESS/COMPLETED tools so
   the badge accurately reflects what will be sent for generation.
3. **Auto-include success tools in the schedule payload** — In
   `handleCreateSchedule`, build a `tool_context` array from all toolLogs
   where status is SUCCESS or COMPLETED, each entry containing
   `{ tool_name, output: summarizeOutput(tool_output) }`. Add this array to
   the `data` object sent to `sciparserApi.createSchedule`.
4. **Summarize helper** — Add a `summarizeOutput(raw, maxChars=500)` helper
   that stringifies non-string values and slices to `maxChars`, appending a
   truncation notice.

## Relevant files
- `Frontend/src/components/ui/premium-scheduler.tsx:60-127`
- `Frontend/src/components/ui/premium-scheduler.tsx:538-593`
- `Frontend/src/components/ui/premium-scheduler.tsx:344`