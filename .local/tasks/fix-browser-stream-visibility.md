# Fix Browser Stream — Frames Never Appear in UI

## What & Why
The live browser preview panel always shows "INITIALIZING STREAM" even while the agent is actively browsing. Three distinct bugs cause this:

1. **Frame size exceeds Replit proxy WebSocket limit** (primary): CDP screenshots are sent as base64-encoded PNG (~130–220 KB per message). The Replit reverse proxy silently drops WebSocket messages above its internal size threshold. `send_json` completes on the server (so the backend logs "Broadcasting browser frame..."), but the message never arrives at the browser. Fix: convert each screenshot to JPEG at 80% quality resized to max 1280 px wide before encoding — target ~25–40 KB per frame.

2. **Zombie WebSocket connections accumulate** (secondary): When the proxy closes a WS connection, the client reconnects correctly but the server never removes the dead entry from `browser_connections[user_id]`. `broadcast_frame` swallows `send_json` failures with `except Exception: pass` and never calls `disconnect()`. Dead entries pile up and every frame is "broadcast" twice (visible in logs). Fix: in `broadcast_frame`, catch the exception and call `self.disconnect(user_id, connection, is_browser=True)` to evict the stale socket.

3. **Stream stops when the agent finishes** (design gap): `_stream_browser_frames` is tied to `process_message` via `stop_stream.set()`. After the run ends, the WebSocket stays open but silent. If the user opens the panel after the run completes, no frame ever arrives. Fix: send one final "last frame" screenshot immediately before `stop_stream.set()` so the panel shows the browser's end-state instead of "INITIALIZING STREAM".

## Done looks like
- While the agent is browsing, the live browser panel shows a real-time JPEG screenshot updating roughly every 1.5 seconds
- The panel shows "Connected" (green dot) instead of "Connecting" within a few seconds of the agent starting
- After the run completes the panel continues to display the last screenshot (not a blank spinner)
- The backend logs show each frame logged only once per broadcast (no zombie duplicates)

## Out of scope
- Interactive clicking/typing inside the browser panel
- Changing the screenshot frame rate
- Sending screenshots for runs triggered by the scheduler (separate stream path)

## Steps
1. **Install Pillow** — Add `Pillow` to `Backend/requirements.txt` so image resizing is available server-side.
2. **Compress screenshots before broadcast** — In `_stream_browser_frames` in `brain.py`, after calling `page.screenshot(type="png")`, open the PNG bytes with `PIL.Image`, resize to max 1280 px wide (preserve aspect ratio), save as JPEG at quality=80, then base64-encode the JPEG bytes. Replace the current `b64` variable with this compressed version.
3. **Clean up stale WS connections on send failure** — In `broadcast_frame` in `main.py`, change the `except Exception: pass` block to call `self.disconnect(user_id, connection, is_browser=True)` so dead sockets are evicted immediately. Use a copied list (`list(self.browser_connections[user_id])`) to iterate safely while modifying.
4. **Send final frame on stream end** — At the very end of `_stream_browser_frames`, just before the `finally` block exits, take one last screenshot (inside a `try/except`) and broadcast it. This ensures the panel shows the browser's final state after the run.
5. **Verify** — Restart the backend, send a browser task, confirm the live browser panel displays JPEG frames and the backend logs each frame once.

## Relevant files
- `Backend/src/services/brain.py:180-240`
- `Backend/src/main.py:89-97`
- `Backend/requirements.txt`
