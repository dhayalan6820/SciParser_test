"""Tests for Task #130: an active websocket connection (chat plan stream,
browser stream, schedule monitor) must be disconnected promptly when the
account is suspended mid-session, rather than only being caught on the next
HTTP request or reconnect.

`_watch_suspension` runs as a background task alongside each websocket's
`receive()` loop. It polls `_is_user_suspended` (a direct DB check, independent
of the request-scoped session used by `get_current_user`) and, once the user
is found to be suspended, sends a `{"type": "suspended", ...}` message and
closes the socket with a dedicated close code the frontend can recognize.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import uuid
import asyncio
from datetime import datetime, timezone

import pytest

from src.database.chat_db import User


def _make_user(status="active"):
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4().int % 1_000_000,
        user_id=str(uuid.uuid4()),
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        role="user",
        status=status,
        created_at=now,
        updated_at=now,
    )


class _FakeWebSocket:
    """Minimal stand-in for FastAPI's WebSocket, just enough for the watcher."""

    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed_with = code


@pytest.mark.asyncio
async def test_is_user_suspended_reflects_current_db_status(sqlite_session_factory, monkeypatch):
    import src.main as main_module

    monkeypatch.setattr(main_module, "AsyncSessionLocal", sqlite_session_factory)

    active_user = _make_user(status="active")
    suspended_user = _make_user(status="suspended")
    async with sqlite_session_factory() as session:
        session.add_all([active_user, suspended_user])
        await session.commit()

    assert await main_module._is_user_suspended(active_user.user_id) is False
    assert await main_module._is_user_suspended(suspended_user.user_id) is True
    # Unknown user id (e.g. deleted account) must not be treated as "suspended".
    assert await main_module._is_user_suspended(str(uuid.uuid4())) is False


@pytest.mark.asyncio
async def test_watch_suspension_closes_socket_once_user_is_suspended(sqlite_session_factory, monkeypatch):
    import src.main as main_module

    monkeypatch.setattr(main_module, "AsyncSessionLocal", sqlite_session_factory)
    monkeypatch.setattr(main_module, "SUSPENSION_CHECK_INTERVAL_SECONDS", 0.01)

    user = _make_user(status="active")
    async with sqlite_session_factory() as session:
        session.add(user)
        await session.commit()

    ws = _FakeWebSocket()
    watcher = asyncio.create_task(main_module._watch_suspension(ws, user.user_id))

    # Give the watcher a couple of poll cycles while the user is still active —
    # it must not close the connection.
    await asyncio.sleep(0.03)
    assert ws.closed_with is None
    assert ws.sent == []

    # Now suspend the user mid-session and confirm the open connection reacts
    # promptly instead of waiting for a reconnect or the next HTTP request.
    async with sqlite_session_factory() as session:
        db_user = await session.get(User, user.id)
        db_user.status = "suspended"
        await session.commit()

    await asyncio.wait_for(watcher, timeout=1)

    assert ws.closed_with == main_module.SUSPENDED_CLOSE_CODE
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "suspended"
    assert ws.sent[0]["error"] == main_module.SUSPENDED_MESSAGE


@pytest.mark.asyncio
async def test_watch_suspension_stops_cleanly_when_cancelled(sqlite_session_factory, monkeypatch):
    """Every websocket endpoint cancels this task in a `finally` block on normal
    disconnect — it must not swallow CancelledError or linger."""
    import src.main as main_module

    monkeypatch.setattr(main_module, "AsyncSessionLocal", sqlite_session_factory)
    monkeypatch.setattr(main_module, "SUSPENSION_CHECK_INTERVAL_SECONDS", 5)

    user = _make_user(status="active")
    async with sqlite_session_factory() as session:
        session.add(user)
        await session.commit()

    ws = _FakeWebSocket()
    watcher = asyncio.create_task(main_module._watch_suspension(ws, user.user_id))
    await asyncio.sleep(0.01)
    watcher.cancel()

    with pytest.raises(asyncio.CancelledError):
        await watcher

    assert ws.closed_with is None
