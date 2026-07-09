---
title: Browser preview tool activity notification
---
# Browser Preview Tool Activity Notification

## What & Why
While the live browser preview is active, users currently have no lightweight, glanceable indicator of what the agent is doing moment-to-moment — the only detail view is the separate "Tool Log" popup, which requires an extra click to open. Add a small, friendly notification/toast area directly below the live browser preview image that shows the current action in plain language (e.g. "Browser navigated", "Checking element", "Button clicked") so users can follow along without opening the tool log.

## Done looks like
- While the browser preview is active and a run is in progress, a small notification area appears just below the preview image.
- It shows a short, friendly label for the most recent tool action (e.g. "Browser navigated" instead of a raw tool/function name like `browser_navigate`).
- The label updates automatically as new tool activity streams in, with a subtle transition (not a jarring flash) between messages.
- When there's no active run or no tool activity yet, the notification area is hidden or shows a neutral idle state — it doesn't show stale or misleading information.
- Doesn't interfere with or duplicate the existing full "Tool Log" popup — this is a lightweight glance, not a replacement.

## Out of scope
- Redesigning or replacing the existing Tool Log popup/history view.
- Showing full tool arguments/output in this notification (name/friendly label only).
- Persisting this notification's history anywhere — it only reflects the latest live action.

## Steps
1. **Friendly label mapping** — Create a mapping from raw tool names (and any relevant tool arguments) to short, human-friendly action phrases (e.g. `browser_navigate` → "Browser navigated", `browser_click` → "Button clicked", element-check tools → "Checking element"), with a sensible fallback label for unmapped tools.
2. **Latest-activity notification UI** — Add a small notification/toast element below the live preview image inside the browser preview component, driven by the most recent entry in the existing tool logs stream, using the friendly label mapping and an unobtrusive enter/exit transition.
3. **Wire to live updates** — Ensure the notification reflects `tool_start`/`tool_output` events as they arrive in real time (not just on tool completion), and clears/hides appropriately when the preview becomes inactive or a run ends.

## Relevant files
- `Frontend/src/components/ui/browser-preview.tsx:380-533`
- `Frontend/src/components/ui/chat_page.tsx:568-725`