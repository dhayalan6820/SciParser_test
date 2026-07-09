# Fix WebSocket Errors and Tool-Log Polling

## What & Why
Two infrastructure problems are causing backend noise and unnecessary load:

**Problem 1 — WebSocket "Cannot call receive" error spam:**
When a client disconnects, the `except Exception` handler in `main.py` logs it as ERROR. This is a normal disconnect signal (not a real failure) but it floods the logs and makes real errors harder to find. The fix is to detect this specific error string and handle it silently like a `WebSocketDisconnect`.

**Problem 2 — Frontend hammer-polls `/tool-logs-live` every 2 seconds:**
The frontend uses `setInterval(poll, 2000)` while `isAiTyping=true`. With multiple browser tabs open, the backend sees 5–10 simultaneous polling requests per second all hitting the same endpoint. Tool logs are already being sent over the existing plan WebSocket — the HTTP poll is a redundant fallback that should be removed in favour of WebSocket delivery.

## Done looks like
- Backend logs no longer show ERROR for normal client disconnects
- `/tool-logs-live` HTTP endpoint is no longer hammered during agent runs
- Tool logs appear in the UI at the same speed (delivered via existing WebSocket instead)

## Out of scope
- Changing the tool log data format or UI display
- Adding new WebSocket event types beyond what already exists

## Steps
1. **Silence disconnect noise** — In `main.py` plan stream and browser stream exception handlers, check if the error message contains "Cannot call" or "disconnect" and handle it the same as `WebSocketDisconnect` (no ERROR log).
2. **Push tool logs over WebSocket** — In `brain.py`, when `broadcast_thought` or plan updates fire, also broadcast tool-log events through the same plan WebSocket instead of buffering for HTTP poll. On the frontend, remove the `setInterval` polling effect and instead parse tool-log events from the incoming WebSocket messages in the existing plan-stream handler.

## Relevant files
- `Backend/src/main.py:686-702,731-739`
- `Backend/src/services/brain.py:905-940`
- `Frontend/src/components/ui/chat_page.tsx:713-763`
