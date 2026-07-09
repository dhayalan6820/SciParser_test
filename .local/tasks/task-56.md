---
title: Show agent mouse cursor in browser preview
---
# Show Agent Mouse Cursor in Browser Preview

## What & Why
When watching the live browser preview, the user can't see where the agent's mouse is — clicks and hovers appear to happen invisibly. This adds a visible animated cursor dot that moves in real time so the user can follow exactly what the agent is doing.

## Done looks like
- A red (or branded-color) cursor dot appears in the browser preview pane while an agent session is running
- The dot moves smoothly to each position before clicks and hovers happen
- Click actions briefly flash/pulse the dot so the user can see the moment of the click
- The cursor disappears when the agent session ends
- Works with both the stealth mouse movements (browser_hover + browser_click) and regular Playwright actions

## Out of scope
- Showing the cursor in exported screenshots or recordings
- Per-user cursor color preferences

## Steps

1. **Emit mouse events from the bridge** — After every `mouse.move()`, `mouse.click()`, and `mouse.down()` call in the browser session (including the human-tools patch: `browser_hover`, `browser_drag`, and all regular Playwright clicks), emit a small JSON event `{ type: "mouse", x, y, event: "move"|"click" }` through the existing WebSocket/SSE channel used for screenshot streaming.

2. **Intercept Playwright mouse calls** — Monkey-patch `Page.mouse.move`, `Page.mouse.click`, and `Page.mouse.down` on the active Playwright page after `BrowserSession.start()` so every mouse action (not just the human-tools) automatically emits a position event without requiring changes to each tool.

3. **Frontend cursor overlay** — In the browser preview component, listen for `mouse` events on the WebSocket/SSE stream. Render an absolutely-positioned `<div>` (a small circle, 18px, red with 60% opacity) on top of the iframe using CSS `pointer-events: none` so it doesn't interfere with the preview. Translate the agent's browser coordinates (1920×1080 or 1280×800) to the iframe's displayed pixel size using a scale factor.

4. **Click pulse animation** — On a `click` event, briefly add a CSS class that scales the cursor dot up and fades it out (a ripple effect) using a keyframe animation, then removes the class — giving clear visual feedback of when and where a click landed.

5. **Cursor lifecycle** — Show the cursor dot only while an agent task is actively running. Hide it (opacity 0) when the session ends or the stream disconnects.

## Relevant files
- `Backend/src/agents/browser_use_bridge.py`
- `Backend/src/agents/mcp_agent.py`
- `Backend/src/agents/agent_manager.py`