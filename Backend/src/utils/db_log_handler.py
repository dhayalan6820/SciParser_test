"""
Database-backed logging handler.

Persists application log records (info/warning/error emitted via the
`sciparser` logger) into the `app_logs` table instead of a rotating log
file. Log I/O must never block the caller or crash the app if the database
is briefly unavailable, so this handler:

- Only does a non-blocking queue put in `emit()` — no DB access happens on
  the calling thread/coroutine.
- Runs a single dedicated background daemon thread with its own persistent
  asyncio event loop and its own async engine (a fresh engine/loop pair per
  batch was tried first but reliably hung during loop teardown — asyncpg
  connection cleanup doesn't play well with one-shot `asyncio.run()` calls
  in a tight loop, so this handler keeps one loop/engine alive for the
  process lifetime instead).
- Swallows any DB error during a flush; a failed flush simply drops that
  batch rather than raising or retrying forever, and the loop keeps going.
- Ignores `close()`/`logging.shutdown()` as a signal to stop the worker
  thread. Uvicorn calls `logging.config.dictConfig()` during its own
  startup, which internally calls `logging.shutdown()` on every handler
  that already exists (ours included) as part of clearing out prior
  config — that happens moments after our handler is created, long before
  the app is actually shutting down. Since the worker thread is a daemon
  thread, it is safe to just let it keep running until the process exits.
"""

import asyncio
import logging
import queue
import threading
import traceback
from datetime import datetime, timezone

_MAX_BATCH_SIZE = 200
_FLUSH_INTERVAL_SECONDS = 2.0
_QUEUE_MAX_SIZE = 5000


def _record_to_row(record: logging.LogRecord) -> dict:
    message = record.getMessage()
    if record.exc_info:
        message = f"{message}\n{''.join(traceback.format_exception(*record.exc_info))}"

    return {
        "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc),
        "level": record.levelname,
        "logger_name": record.name,
        "message": message,
        "module": record.module,
        "func_name": record.funcName,
        "line_no": record.lineno,
    }


class DatabaseLogHandler(logging.Handler):
    """A `logging.Handler` that batches records and writes them to `app_logs`."""

    def __init__(self):
        super().__init__()
        self._queue: "queue.Queue[logging.LogRecord]" = queue.Queue(maxsize=_QUEUE_MAX_SIZE)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._thread_main, name="db-log-handler", daemon=True
        )
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except Exception:
            # Includes queue.Full — drop the log line rather than block the
            # caller or raise out of a logging call.
            pass

    def close(self) -> None:
        # Deliberately does NOT stop the worker thread — see module
        # docstring. Just do the base bookkeeping (e.g. removing this
        # handler from logging's global handler registry).
        super().close()

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run(loop))
        except Exception:
            pass
        finally:
            loop.close()

    async def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        # Imported lazily (rather than at module load) to avoid a hard
        # dependency/circular import between the logging setup (imported
        # very early) and the database module.
        from sqlalchemy.ext.asyncio import create_async_engine

        from src.database.chat_db import AppLog, DATABASE_URL

        if not DATABASE_URL:
            return

        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_size=2,
            max_overflow=2,
            pool_pre_ping=True,
        )
        try:
            while not self._stop_event.is_set():
                # Block for new records on a worker thread (not the event
                # loop) so the loop stays free to run other tasks/cleanup.
                batch = await loop.run_in_executor(None, self._collect_batch)
                if not batch:
                    continue
                try:
                    rows = [_record_to_row(record) for record in batch]
                    async with engine.begin() as conn:
                        await conn.execute(AppLog.__table__.insert(), rows)
                except Exception:
                    # A DB hiccup must never take down logging or the app;
                    # the batch is simply dropped and the loop continues.
                    pass
        finally:
            await engine.dispose()

    def _collect_batch(self):
        batch = []
        try:
            batch.append(self._queue.get(timeout=_FLUSH_INTERVAL_SECONDS))
        except queue.Empty:
            return batch
        while len(batch) < _MAX_BATCH_SIZE:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch
