---
name: Replit WS frame size limit
description: Replit reverse proxy silently drops WebSocket messages larger than ~64 KB without closing the connection
---

## Rule
Any data sent over a WebSocket through the Replit proxy must be kept under ~64 KB per message. Never send raw PNG screenshots over WebSocket — always compress to JPEG first.

## Why
The Replit reverse proxy (mTLS) has an undocumented per-message size limit. When a message exceeds it, the proxy drops the message silently:
- `send_json` succeeds on the server (writes to TCP buffer)
- The backend logs the broadcast as if it succeeded
- The browser's `onmessage` never fires
- The WebSocket connection stays alive (no close event)

This caused browser stream frames (130–220 KB PNG) to never appear in the UI even though the backend logged them successfully.

## How to apply
In `_stream_browser_frames` (brain.py): call `_compress_screenshot()` which uses Pillow to resize to max 1280 px wide and save as JPEG quality=80 (~25–40 KB).

Also applies to: any other server→client WebSocket push (tool logs, plan updates). Check payload sizes if data isn't arriving.

## Companion issue: zombie WS connections
`broadcast_frame` must iterate over a COPY of `browser_connections[user_id]` and call `disconnect()` on any connection where `send_json` raises — otherwise dead sockets accumulate and every frame is "broadcast" to a growing list of dead connections (visible as duplicate log entries).
