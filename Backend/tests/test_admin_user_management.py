import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from src.database.chat_db import User, ChatSession, Message
from src.services.chat_service import ChatService


_next_id = [1]


def _make_user(role="user", status="active"):
    now = datetime.now(timezone.utc)
    # SQLite maps BigInteger primary keys to a plain INTEGER column (not the
    # rowid-aliased "INTEGER PRIMARY KEY"), so autoincrement doesn't kick in
    # under the in-memory sqlite test engine. Assign `id` explicitly here to
    # work around that sqlite-only quirk; production Postgres autoincrements
    # this column normally.
    user_id_pk = _next_id[0]
    _next_id[0] += 1
    return User(
        id=user_id_pk,
        user_id=str(uuid.uuid4()),
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        role=role,
        status=status,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_admin_delete_user_cascades_to_chat_sessions_and_messages(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        admin = _make_user(role="admin")
        target = _make_user(role="user")
        session.add_all([admin, target])
        await session.flush()

        chat_session = ChatSession(
            id=f"thread-{uuid.uuid4()}",
            user_id=target.user_id,
            title="test chat",
        )
        session.add(chat_session)
        await session.flush()

        message = Message(
            message_id=str(uuid.uuid4()),
            chat_id=chat_session.id,
            user_id=target.user_id,
            role="user",
            content="hello",
        )
        session.add(message)
        await session.commit()

        result = await ChatService.admin_delete_user(session, target.user_id, admin)
        assert result == {"status": "success"}

        remaining_user = (
            await session.execute(select(User).where(User.user_id == target.user_id))
        ).scalar_one_or_none()
        remaining_sessions = (
            await session.execute(select(ChatSession).where(ChatSession.user_id == target.user_id))
        ).scalars().all()
        remaining_messages = (
            await session.execute(select(Message).where(Message.user_id == target.user_id))
        ).scalars().all()

        assert remaining_user is None
        assert remaining_sessions == []
        assert remaining_messages == []


@pytest.mark.asyncio
async def test_admin_cannot_delete_own_account(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        admin = _make_user(role="admin")
        session.add(admin)
        await session.commit()

        with pytest.raises(Exception):
            await ChatService.admin_delete_user(session, admin.user_id, admin)
