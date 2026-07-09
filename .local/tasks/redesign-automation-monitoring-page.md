# Redesign Automation Monitoring Page

## What & Why
The automation monitoring/schedule detail view (schedules-page.tsx) is dense and overflows the screen — the header, progress ring, execution pipeline, tabs, and side panels (execution summary, live browser, final result) are all shown at once with fixed heights and horizontal scroll workarounds. The user wants a redesigned layout that fits without overflow, shows the most important information directly, and moves secondary/heavy content (like the generated script) behind a button that opens a popup/modal.

Specifically: when the user wants to view the automation script, clicking a button should open the script in a popup/modal instead of it being an always-visible tab panel taking up space.

## Done looks like
- The monitoring page for a selected schedule fits within the viewport without content overflowing or requiring awkward horizontal scrolling on desktop.
- Core at-a-glance info remains directly visible: schedule identity/status, next/last run, run/edit/delete actions, live progress (progress ring + ETA + pipeline steps), and current status.
- Secondary/heavy content is accessed via a button that opens a popup/modal instead of always rendering inline: at minimum the generated Script. The agent implementing this should decide which other panels (e.g. AI Planning details, full run History table, Execution Summary metrics, Live Browser preview) are important enough to stay inline vs. moved to a "View X" button + popup, based on how much space they take and how often they're needed at a glance.
- Clicking "View Script" (or equivalent) opens a popup showing the script with existing functionality preserved (copy code, syntax display).
- All existing functionality (run now, activate, edit, delete, live logs, live browser stream, AI planning info, run history, final result download) remains reachable — either inline or via a popup — nothing is removed.
- Responsive: works on smaller/narrower viewports without breaking (no fixed-height overflow, sensible stacking).

## Out of scope
- Backend/API changes — this is a frontend layout/UX redesign only, no changes to schedule data, execution logic, or endpoints.
- Changing the schedules list/sidebar (left navigation of schedules) unless needed to fix overflow caused by that specific element.
- The scheduler creation flow (premium-scheduler.tsx) — that was already fixed in a prior task; do not modify it here.

## Steps
1. **Audit current layout for overflow sources** — Identify which sections cause the page to exceed viewport height/width (e.g. tabbed panel with fixed min-heights, side-by-side grid columns, wide execution pipeline row) and note them for redesign.
2. **Design the redesigned layout** — Decide what stays directly visible (status, progress, pipeline, run controls) vs. what moves behind a "view" button + popup (at minimum the Script; use judgment for AI Planning, History, Execution Summary, Live Browser based on their footprint and importance). Keep tabs only for content that's still worth switching between inline; move heavy read-once content to modals.
3. **Implement the popup pattern for the Script view** — Add a button (e.g. next to or replacing the current Script tab) that opens a modal/popup displaying the generated script with copy functionality, matching the styling conventions already used for other modals in this file (Edit/Delete modals).
4. **Implement the popup pattern for other deprioritized sections** — For any other panel moved out of the main flow, add its own trigger button and popup, preserving all current functionality (e.g. run history table, execution summary metrics, live browser preview enlarge).
5. **Rebuild the main inline layout** — Restructure the remaining inline sections (header/actions, progress, pipeline, live logs) so they fit without overflow and remain responsive at common breakpoints (mobile/tablet/desktop), removing now-unnecessary horizontal scroll containers where possible.
6. **Verify functionality end-to-end** — Confirm run now/activate, edit, delete, live log streaming, live browser streaming, script viewing, AI planning viewing, history viewing, and result download all still work after the redesign, and that no layout overflows on standard viewport sizes.

## Relevant files
- `Frontend/src/components/ui/schedules-page.tsx`
