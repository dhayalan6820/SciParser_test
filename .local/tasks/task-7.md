---
title: Stack browser above tool log (vertical layout)
---
# Browser/Tool Log: Vertical Stack Layout

## What & Why
The live browser panel and tool execution log are currently side-by-side (horizontal split). The user wants browser on top and tool log below (vertical stack). This gives the browser more horizontal space to display the page clearly and pushes the tool log to the bottom where it reads naturally like a terminal.

## Done looks like
- When the browser panel is open, the browser stream occupies the top portion of the panel
- The tool execution log sits directly below the browser stream
- A horizontal drag handle between the two lets users resize the split (drag up for more log space, drag down for more browser space)
- The `split` view mode default height split is ~65% browser / 35% log
- `browser`-only and `logs`-only view modes still work (toggle the other panel to 0 height / hidden)
- No horizontal overflow or content clipping — the browser image fills the full panel width

## Out of scope
- The outer resizable panel width (the handle between chat column and browser panel in `chat_page.tsx`) — keep as-is
- View mode toggle buttons — keep as-is

## Steps
1. **Flip the workspace flex direction** — Change the "Main Workspace Area" container from `flex` (row) to `flex-col` so browser and tool log stack vertically.
2. **Swap width-based sizing to height-based** — `browserWidth` state → `browserHeight` (default 65%). Update the browser panel's `style` from `width` to `height`, and the log panel's remaining space from `100 - browserWidth` to `100 - browserHeight`.
3. **Update the resize handle** — Change from a vertical `w-1 cursor-col-resize` bar to a horizontal `h-1 cursor-row-resize` bar. Update the mouse move calculation to use `clientY` and container `top`/`height` instead of `clientX` and `left`/`width`.
4. **Fix panel border direction** — The tool log panel has `border-l` (left border); change to `border-t` (top border) since it now sits below.
5. **Fix browser panel layout** — The browser stream panel is currently `flex-col h-full`; ensure it has `w-full` and its height is driven by the `height` style, not fixed.

## Relevant files
- `Frontend/src/components/ui/browser-preview.tsx:50-88,169-265,267-428`