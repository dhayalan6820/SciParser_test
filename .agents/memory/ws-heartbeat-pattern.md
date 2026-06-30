---
name: WS heartbeat pattern
description: Replit proxy kills idle WebSockets; all WS effects need 20s ping + auto-reconnect
---

## Rule
Every WebSocket useEffect must follow this pattern:
1. Define a `connect()` function that creates the WS
2. `ws.onopen` starts a 20-second interval calling `ws.send("ping")`
3. `ws.onclose` schedules a `setTimeout(connect, 3000)` if not destroyed
4. `ws.onerror` calls `ws.close()` to trigger the reconnect path
5. Cleanup sets `destroyed = true`, clears timers, closes WS

## Why
The Replit reverse proxy closes WebSocket connections that have no client→server
traffic after ~60-90 seconds. Browser stream is purely server→client so the
proxy kills it. This caused the browser panel to stay stuck on "INITIALIZING
STREAM" until the user refreshed the page.

## How to apply
- Apply to BOTH the browser stream WS and the plan WS in chat_page.tsx
- Backend must use `receive()` not `receive_text()` so ping frames don't throw
- Backend `except Exception` branch must also call `disconnect()` to clean stale sockets
