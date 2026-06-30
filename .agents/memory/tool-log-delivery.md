---
name: Tool log delivery
description: Tool logs must be buffered in memory and polled via HTTP, not WS-only
---

## Rule
Buffer tool_start / tool_output events in `Brain.tool_log_buffer[chat_id]`
(in-memory dict). Serve via `GET /sciparser/v1/chat/sessions/{chat_id}/tool-logs-live`.
Frontend polls every 2s while `isAiTyping`.

## Why
Tool logs go through `broadcast_frame(..., is_tool=True)` which writes to
`browser_connections[user_id]`. If the frontend browser WebSocket is not yet
connected when the first tool calls execute, all those log events are silently
dropped and never show in the UI. HTTP polling with in-memory buffer is
resilient to this race condition.

## How to apply
- `Brain.buffer_tool_event(chat_id, event)` — called in `_call_tool` for both
  tool_start and tool_output events (capped at 200 per chat)
- `Brain.clear_live_tool_logs(chat_id)` — called at start of each new execution
- Frontend: `useEffect` polls `/tool-logs-live` every 2s while `isAiTyping`
  and reconstructs the tool log map from start+output event pairs
