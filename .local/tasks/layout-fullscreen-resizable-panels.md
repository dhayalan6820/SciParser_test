# Fix Full-Screen Layout & Resizable Panels

## What & Why
Several layout bugs cause the app to not fill the full viewport and the Schedules page to show overlapping panels. The root cause is a chain of missing height constraints starting from the top-level `motion.div` in `App.tsx`, plus the schedules page using a fixed 12-column CSS grid that overflows at narrower widths. Additionally the schedules page sidebar is a fixed 320 px column with no drag-to-resize handle, making it inflexible.

## Done looks like
- App fills the entire browser window at all times; no vertical whitespace below the content.
- Schedules page sidebar and main content area never overlap; they sit flush side-by-side.
- On narrower viewports the schedules grid stacks vertically instead of overflowing.
- The schedules sidebar can be dragged to resize (same pattern as the browser/history panel in the chat page).
- The chat page browser panel and history panel resize handles remain functional.
- No content is cut off or hidden behind other elements.

## Out of scope
- Mobile (< 768 px) breakpoint redesign beyond basic stacking.
- Adding new features to the schedules monitoring dashboard.
- Any backend changes.

## Steps

1. **Fix global height chain** — In `index.css` ensure `html`, `body`, and `#root` all get `height: 100%; overflow: hidden`. In `App.tsx` add `h-screen overflow-hidden` to the outer `motion.div` so that `h-full` on every child propagates correctly all the way down the tree.

2. **Fix schedules page grid overflow** — Replace the hard-coded `grid grid-cols-12` with a responsive variant (`grid-cols-1 xl:grid-cols-12`). At `xl` (≥1280 px) keep the `col-span-8` / `col-span-4` split; below `xl` let both columns stack full-width. Remove the `max-w-[1400px] mx-auto` constraint that fights the flex parent on narrower screens.

3. **Add drag-to-resize to schedules sidebar** — Convert the fixed `w-[320px]` schedules sidebar into a resizable panel using React state (`sidebarWidth`, default 280 px, min 200 px, max 480 px). Add a 6 px drag handle on the right edge of the sidebar wired to `mousedown/mousemove/mouseup` events — identical pattern to the existing `handleBrowserResizeStart` logic in `chat_page.tsx`. Show a visual indicator (thin line that highlights indigo on hover) on the handle.

4. **Tighten flex containers** — Add `min-h-0` and `min-w-0` where needed on flex children throughout `schedules-page.tsx` and `chat_page.tsx` to prevent flex children from growing past their parent bounds and causing scroll bleed.

5. **Verify and test** — After changes, take a screenshot to confirm no overlap, the grid stacks correctly, and the resize handle works in the schedules sidebar.

## Relevant files
- `Frontend/src/App.tsx`
- `Frontend/src/index.css:1-60`
- `Frontend/src/components/ui/schedules-page.tsx:209-300`
- `Frontend/src/components/ui/schedules-page.tsx:375-660`
- `Frontend/src/components/ui/chat_page.tsx:122-279`
- `Frontend/src/components/ui/chat_page.tsx:1711-2034`
