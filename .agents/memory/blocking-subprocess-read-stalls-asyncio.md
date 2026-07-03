---
name: Blocking subprocess stdout read stalls the whole asyncio event loop
description: Why WebSocket broadcasts (logs, progress, resource usage) can appear to "batch up" and only arrive at the very end of a long-running task instead of streaming live
---

Iterating a `subprocess.Popen(...).stdout` pipe with a plain `for line in process.stdout:` (or a blocking `.readline()`/`.wait()` call) inside an `async def` coroutine blocks the *entire* asyncio event loop for as long as the subprocess runs — not just that one task. Any other coroutine, including WebSocket message sends scheduled via `asyncio.run_coroutine_threadsafe` from a background sampling thread, gets queued but cannot actually run/flush over the socket until the blocking call returns. From the outside this looks like every live-update message (logs, progress, sampled metrics) silently "waits" and then all arrives in a single burst right as the subprocess exits — a very confusing symptom that superficially resembles a broken WebSocket connection rather than a scheduling stall.

**Why:** asyncio is single-threaded cooperative multitasking; a synchronous blocking call in a coroutine never yields control back to the loop, so nothing else in the process can make progress (including sends whose bytes were already handed to the transport but need the loop to drain the socket buffer).

**How to apply:** when a subprocess's output needs to stream live to clients while the coroutine also does other async work (DB writes, WebSocket broadcasts), never read the pipe with a bare blocking loop in an async function. Instead read via `await loop.run_in_executor(None, process.stdout.readline)` per line (or run the whole read loop on a dedicated thread) so the event loop stays free between reads. Apply the same fix to `process.wait(timeout=...)`. If you see "all my live WS messages arrived at once at the end" bug reports, suspect a blocking call in an async task before suspecting the WebSocket/proxy layer.
