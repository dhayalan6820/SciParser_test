---
title: Fix schedule modal — time, timezone, headless, tools
---
# Scheduler Modal — 6 Fixes

## What & Why
The schedule creation modal has several broken or incomplete wires: time and timezone pickers have no state binding (values are never sent to the backend), tools shown are the entire session's tool log instead of just the selected content's tools, the headless toggle exists in state but has no UI and never reaches the backend, and several summary cards show hardcoded dates/values. This task fixes all of them end-to-end.

## Done looks like
- Time picker has a full 24-hour grid (every hour, e.g. 01:00 AM … 12:00 AM) with a state variable wired to the select; the selected time reaches the backend and is used by the cron scheduler
- Timezone picker shows exactly 6 options (US: EST, CST, MST, PST + India: IST + UTC fallback), wired to state; the selected timezone reaches the backend and is stored on the schedule row
- A headed / headless toggle appears in Advanced Options; the value is sent to the backend and passed as `BROWSER_USE_HEADLESS` env var override when the scheduled script subprocess is spawned
- The Tools tab shows **only** the tools whose IDs are in `selectedTools` (the user's checked subset), and each card is always a SUCCESS tool (failed tools are already excluded upstream); tool output is summarised to ≤ 300 chars per entry
- The `tool_context` array sent in the create-schedule payload is restricted to the same `selectedTools` intersection (not all success tools indiscriminately)
- The AI Context / AI Plan tabs populate from the AI message linked to the selected messages; if no message is selected but tools are, a clear "Select a chat message to see AI plan" placeholder is shown instead of blank space
- Next Run Preview, Selection Summary, and Execution Config Summary cards derive all values from live state (no hardcoded dates or timezone strings)

## Out of scope
- Changing the three frequency types (daily / weekly / monthly) or adding cron-expression freeform input
- Multi-recipient email
- Any other scheduler backend logic not directly needed to wire these fields

## Steps

1. **Add `scheduleTime` and `timezone` state variables** — Replace the two unbound `<select>` elements with controlled selects backed by `scheduleTime` (default `"09:00"`) and `timezone` (default `"America/New_York"`) state. Populate the time select with 24 hour-on-the-hour options (00:00 → 23:00, formatted as 12-h labels). Populate the timezone select with exactly 6 entries: EST (America/New_York), CST (America/Chicago), MST (America/Denver), PST (America/Los_Angeles), IST (Asia/Kolkata), UTC.

2. **Wire headed/headless toggle in Advanced Options UI** — Add a toggle row in the Advanced Options section that controls the existing `headless` state variable. Show the current mode ("Headless" / "Headed") and update the Execution Config Summary "Browser" card to reflect the live value.

3. **Send schedule_time, timezone, and advanced_options to backend** — Add `schedule_time` (string `"HH:MM"`), `timezone` (IANA string), and `advanced_options` (object with `retry_count`, `timeout`, `headless`) to the `data` object in `handleCreateSchedule`. Add the three fields to the `ScheduleRequest` Pydantic schema. Add `timezone` column to the `Schedule` DB model (String 50, nullable). Update `create_schedule` in `chat_service.py` to persist `schedule_time` and `timezone`. Pass `schedule_time` and `timezone` into `_calculate_next_run` / `_build_cron_trigger` in `main.py` so the cron job actually honours the user's choice. When spawning the script subprocess in `_run_schedule_task`, inject `BROWSER_USE_HEADLESS=true/false` into the subprocess environment based on the stored `advanced_options` or schedule default.

4. **Filter Tools tab to selectedTools only** — In the Tools tab, replace `allTools` with a filtered list: `toolLogs.filter(l => selectedTools.includes(l.id))`. Show this as the tool cards grid. Update the badge count accordingly. Change `tool_context` in `handleCreateSchedule` to also filter by `selectedTools` (instead of filtering all logs by status alone). Ensure output is summarised to ≤ 300 chars. Show tool name prominently (it is the key identifier for script generation).

5. **Fix AI Context / Plan tab empty state** — If `selectedAiMsg` is null (no message selected), render a clear placeholder card in the AI Plan and AI Response sections instead of blank/default text. If an AI message IS found, ensure the plan renders from `selectedAiMsg.plan` (already present), and the response renders from `selectedAiMsg.content`.

6. **Replace all hardcoded summary strings** — Next Run Preview: compute next run date dynamically from `scheduleType` + `scheduleTime` + `timezone` (simple JS Date arithmetic is fine). Selection Summary "Time of Day" and "Timezone" rows: read from state variables. "Next Run" row: same computed date. Execution Config Summary "Browser" card: read from `headless` state.

## Relevant files
- `Frontend/src/components/ui/premium-scheduler.tsx:1-899`
- `Backend/src/schemas/schema.py:81-88`
- `Backend/src/services/chat_service.py:189-222`
- `Backend/src/database/chat_db.py:140-155`
- `Backend/src/main.py:150-230`