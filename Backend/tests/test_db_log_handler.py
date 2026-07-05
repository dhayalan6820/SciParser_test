"""Tests for the database-backed logging handler
(src/utils/db_log_handler.py): records queued via emit() must eventually be
persisted to the app_logs table, and a failing/unavailable DB must never
raise out of a logging call.
"""
import asyncio
import logging
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest
from sqlalchemy import select

from src.database.chat_db import AppLog
from src.utils.db_log_handler import DatabaseLogHandler, _record_to_row


def _make_record(message="hello world", level=logging.INFO, logger_name="sciparser"):
    return logging.LogRecord(
        name=logger_name,
        level=level,
        pathname=__file__,
        lineno=42,
        msg=message,
        args=None,
        exc_info=None,
        func="some_func",
    )


def test_emit_never_raises_when_queue_full(monkeypatch):
    handler = DatabaseLogHandler.__new__(DatabaseLogHandler)
    handler._queue = __import__("queue").Queue(maxsize=1)
    handler._queue.put_nowait(_make_record())

    # Queue is now full; emit() must swallow the resulting queue.Full error
    # rather than raise out of a logging call.
    handler.emit(_make_record("second message"))


def test_close_does_not_stop_the_worker_thread():
    handler = DatabaseLogHandler()
    try:
        assert handler._thread.is_alive()
        handler.close()
        assert not handler._stop_event.is_set()
        assert handler._thread.is_alive()
    finally:
        handler._stop_event.set()


def test_record_to_row_maps_fields():
    record = _make_record(message="something happened", level=logging.WARNING)
    row = _record_to_row(record)

    assert row["level"] == "WARNING"
    assert row["logger_name"] == "sciparser"
    assert row["message"] == "something happened"
    assert row["func_name"] == "some_func"
    assert row["line_no"] == 42


@pytest.mark.asyncio
async def test_write_batch_persists_records_to_app_logs(sqlite_session_factory):
    records = [_make_record("first"), _make_record("second", level=logging.ERROR)]
    # SQLite (used only for this test's in-memory DB) requires an explicit
    # id for a BigInteger PK to auto-increment correctly; Postgres (used in
    # production) handles this natively without any id in the insert.
    rows = [
        {**_record_to_row(record), "id": i}
        for i, record in enumerate(records, start=1)
    ]

    async with sqlite_session_factory() as session:
        await session.execute(AppLog.__table__.insert(), rows)
        await session.commit()

        result = await session.execute(select(AppLog).order_by(AppLog.id))
        persisted = result.scalars().all()

    assert len(persisted) == 2
    assert persisted[0].message == "first"
    assert persisted[0].level == "INFO"
    assert persisted[1].message == "second"
    assert persisted[1].level == "ERROR"


def test_collect_batch_respects_max_size():
    handler = DatabaseLogHandler.__new__(DatabaseLogHandler)
    handler._queue = __import__("queue").Queue()
    for i in range(250):
        handler._queue.put_nowait(_make_record(f"msg-{i}"))

    batch = handler._collect_batch()
    assert len(batch) == 200
