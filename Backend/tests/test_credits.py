import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from src.database.chat_db import User, Message
from src.services.chat_service import ChatService
from src.services import brain as brain_module


_next_id = [10_000]


def _make_user(role="user", status="active", credit_balance=5.0):
    now = datetime.now(timezone.utc)
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
        credit_balance=credit_balance,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_new_user_defaults_to_five_credits(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        user = User(
            id=_next_id[0],
            user_id=str(uuid.uuid4()),
            username=f"user_{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-real-hash",
        )
        _next_id[0] += 1
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.credit_balance == 5.0


@pytest.mark.asyncio
async def test_admin_set_user_credits_absolute(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=5.0)
        session.add(target)
        await session.commit()

        updated = await ChatService.admin_set_user_credits(session, target.user_id, credits=12.5)
        assert updated.credit_balance == 12.5


@pytest.mark.asyncio
async def test_admin_set_user_credits_delta(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=5.0)
        session.add(target)
        await session.commit()

        updated = await ChatService.admin_set_user_credits(session, target.user_id, delta=3.0)
        assert updated.credit_balance == 8.0

        updated = await ChatService.admin_set_user_credits(session, target.user_id, delta=-100.0)
        assert updated.credit_balance == 0.0


@pytest.mark.asyncio
async def test_admin_set_user_credits_requires_exactly_one_arg(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=5.0)
        session.add(target)
        await session.commit()

        with pytest.raises(Exception):
            await ChatService.admin_set_user_credits(session, target.user_id)

        with pytest.raises(Exception):
            await ChatService.admin_set_user_credits(session, target.user_id, credits=1.0, delta=1.0)


@pytest.mark.asyncio
async def test_admin_list_users_includes_credit_balance(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=3.25)
        session.add(target)
        await session.commit()

        result = await ChatService.admin_list_users(session, page=1, page_size=20, search=target.username)
        assert result["users"][0]["credit_balance"] == 3.25


@pytest.mark.asyncio
async def test_get_user_conversation_usage_groups_by_chat_id(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user()
        session.add(target)
        await session.flush()

        chat_a = f"thread-{uuid.uuid4()}"
        chat_b = f"thread-{uuid.uuid4()}"

        session.add_all([
            Message(
                message_id=str(uuid.uuid4()), chat_id=chat_a, user_id=target.user_id, role="ai",
                content="hi", token_usage='{"input": 100, "output": 50, "total": 150}', cost=0.01,
            ),
            Message(
                message_id=str(uuid.uuid4()), chat_id=chat_a, user_id=target.user_id, role="ai",
                content="hi again", token_usage='{"input": 20, "output": 10, "total": 30}', cost=0.002,
            ),
            Message(
                message_id=str(uuid.uuid4()), chat_id=chat_b, user_id=target.user_id, role="ai",
                content="other convo", token_usage='{"input": 5, "output": 5, "total": 10}', cost=0.001,
            ),
            # user-authored messages should not be counted
            Message(
                message_id=str(uuid.uuid4()), chat_id=chat_a, user_id=target.user_id, role="user",
                content="prompt",
            ),
        ])
        await session.commit()

        usage = await ChatService.get_user_conversation_usage(session, target.user_id)
        by_chat = {u["chat_id"]: u for u in usage}

        assert by_chat[chat_a]["total_tokens"] == 180
        assert by_chat[chat_a]["input_tokens"] == 120
        assert by_chat[chat_a]["output_tokens"] == 60
        assert round(by_chat[chat_a]["total_cost"], 4) == 0.012

        assert by_chat[chat_b]["total_tokens"] == 10


@pytest.mark.asyncio
async def test_admin_get_user_analytics_includes_credits_and_conversations(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=2.5)
        session.add(target)
        await session.flush()

        chat_id = f"thread-{uuid.uuid4()}"
        session.add(Message(
            message_id=str(uuid.uuid4()), chat_id=chat_id, user_id=target.user_id, role="ai",
            content="hi", token_usage='{"input": 10, "output": 10, "total": 20}', cost=0.005,
        ))
        await session.commit()

        analytics = await ChatService.admin_get_user_analytics(session, target.user_id, days=30)
        assert analytics["credit_balance"] == 2.5
        assert len(analytics["conversations"]) == 1
        assert analytics["conversations"][0]["chat_id"] == chat_id


@pytest.mark.asyncio
async def test_db_manager_get_user_credit_balance(sqlite_session_factory, monkeypatch):
    monkeypatch.setattr(brain_module, "AsyncSessionLocal", sqlite_session_factory)

    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=1.75)
        session.add(target)
        await session.commit()

    db_manager = brain_module.DatabaseManager()
    balance = await db_manager.get_user_credit_balance(target.user_id)
    assert balance == 1.75

    missing_balance = await db_manager.get_user_credit_balance(str(uuid.uuid4()))
    assert missing_balance == 0.0


@pytest.mark.asyncio
async def test_db_manager_deduct_credits_never_goes_negative(sqlite_session_factory, monkeypatch):
    monkeypatch.setattr(brain_module, "AsyncSessionLocal", sqlite_session_factory)

    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=1.0)
        session.add(target)
        await session.commit()

    db_manager = brain_module.DatabaseManager()
    await db_manager.deduct_credits(target.user_id, 0.4)

    async with sqlite_session_factory() as session:
        refreshed = (
            await session.execute(select(User).where(User.user_id == target.user_id))
        ).scalar_one()
        assert refreshed.credit_balance == 0.6

    await db_manager.deduct_credits(target.user_id, 5.0)
    async with sqlite_session_factory() as session:
        refreshed = (
            await session.execute(select(User).where(User.user_id == target.user_id))
        ).scalar_one()
        assert refreshed.credit_balance == 0.0

    # No-op for non-positive amounts
    await db_manager.deduct_credits(target.user_id, 0)
    await db_manager.deduct_credits(target.user_id, -1)
    async with sqlite_session_factory() as session:
        refreshed = (
            await session.execute(select(User).where(User.user_id == target.user_id))
        ).scalar_one()
        assert refreshed.credit_balance == 0.0


@pytest.mark.asyncio
async def test_process_message_blocks_when_out_of_credits(sqlite_session_factory, monkeypatch):
    monkeypatch.setattr(brain_module, "AsyncSessionLocal", sqlite_session_factory)

    async with sqlite_session_factory() as session:
        target = _make_user(credit_balance=0.0)
        session.add(target)
        await session.commit()
        user_id = target.user_id

    result = await brain_module.brain.process_message(user_id, "do something", f"thread-{uuid.uuid4()}")
    assert result["success"] is False
    assert "credit" in result["message"].lower()
