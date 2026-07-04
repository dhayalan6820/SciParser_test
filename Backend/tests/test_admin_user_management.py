import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from src.database.chat_db import (
    User,
    ChatSession,
    Message,
    AgentExecutionLog,
    Schedule,
    ScheduleRun,
    LoginEvent,
)
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


@pytest.mark.asyncio
async def test_admin_list_users_includes_per_user_metrics(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(role="user")
        session.add(target)
        await session.flush()

        message = Message(
            message_id=str(uuid.uuid4()),
            chat_id=f"thread-{uuid.uuid4()}",
            user_id=target.user_id,
            role="user",
            content="hi",
        )
        session.add(message)

        session.add_all([
            AgentExecutionLog(
                id=str(uuid.uuid4()),
                chat_id="chat-1",
                user_id=target.user_id,
                agent_stage="1",
                stage_name="plan",
                status="COMPLETED",
                cost="0.01",
            ),
            AgentExecutionLog(
                id=str(uuid.uuid4()),
                chat_id="chat-2",
                user_id=target.user_id,
                agent_stage="1",
                stage_name="plan",
                status="FAILED",
                cost="0.02",
            ),
        ])

        schedule = Schedule(id=_next_id[0], schedule_id=str(uuid.uuid4()), user_id=target.user_id, title="daily run")
        _next_id[0] += 1
        session.add(schedule)
        await session.commit()

        result = await ChatService.admin_list_users(session, page=1, page_size=20)
        row = next(u for u in result["users"] if u["user_id"] == target.user_id)

        assert row["total_runs"] == 2
        assert row["success_rate"] == 50.0
        assert row["total_cost"] == pytest.approx(0.03)
        assert row["automation_count"] == 1
        assert row["last_active"] is not None


@pytest.mark.asyncio
async def test_admin_get_user_analytics_aggregates_usage_activity_and_automations(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(role="user")
        session.add(target)
        await session.flush()

        chat_session = ChatSession(id=f"thread-{uuid.uuid4()}", user_id=target.user_id, title="test chat")
        session.add(chat_session)
        await session.flush()

        session.add(Message(
            message_id=str(uuid.uuid4()),
            chat_id=chat_session.id,
            user_id=target.user_id,
            role="user",
            content="hello",
        ))

        session.add_all([
            AgentExecutionLog(
                id=str(uuid.uuid4()),
                chat_id="chat-1",
                user_id=target.user_id,
                agent_stage="1",
                stage_name="plan",
                status="COMPLETED",
                cost="1.50",
                token_usage='{"total": 100}',
            ),
            AgentExecutionLog(
                id=str(uuid.uuid4()),
                chat_id="chat-2",
                user_id=target.user_id,
                agent_stage="1",
                stage_name="plan",
                status="FAILED",
                cost="0.50",
                token_usage='{"total": 50}',
            ),
        ])

        session.add(LoginEvent(
            id=str(uuid.uuid4()),
            user_id=target.user_id,
            username_attempted=target.username,
            success=True,
        ))

        schedule = Schedule(id=_next_id[0], schedule_id=str(uuid.uuid4()), user_id=target.user_id, title="daily run", status="active")
        _next_id[0] += 1
        session.add(schedule)
        await session.flush()

        session.add(ScheduleRun(
            id=_next_id[0],
            run_id=str(uuid.uuid4()),
            schedule_id=schedule.schedule_id,
            status="COMPLETED",
        ))
        _next_id[0] += 1
        await session.commit()

        result = await ChatService.admin_get_user_analytics(session, target.user_id, days=30)

        assert result["user_id"] == target.user_id
        assert result["total_runs"] == 2
        assert result["success_count"] == 1
        assert result["failed_count"] == 1
        assert result["success_rate"] == 50.0
        assert result["total_tokens"] == 150
        assert result["total_cost"] == pytest.approx(2.0)
        assert len(result["daily_usage"]) == 1
        assert result["activity"]["total_sessions"] == 1
        assert result["activity"]["total_messages"] == 1
        assert result["activity"]["last_active"] is not None
        assert len(result["activity"]["recent_logins"]) == 1
        assert result["automations"]["total"] == 1
        assert result["automations"]["active"] == 1
        assert result["automations"]["success_rate"] == 100.0
        assert result["automations"]["items"][0]["schedule_id"] == schedule.schedule_id


@pytest.mark.asyncio
async def test_admin_get_user_analytics_raises_for_unknown_user(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        with pytest.raises(Exception):
            await ChatService.admin_get_user_analytics(session, str(uuid.uuid4()), days=30)
