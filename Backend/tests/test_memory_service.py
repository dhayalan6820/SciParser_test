"""Integration tests for MemoryService.

Tests run against an in-memory SQLite database so no real database is needed.
The AsyncSessionLocal used by MemoryService is patched with the SQLite factory
for the duration of each test.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.memory_service import MemoryService


@pytest.fixture
def memory_service():
    return MemoryService(llm=None)


# ── Test 1: seed_captcha_skills idempotency ───────────────────────────────────

@pytest.mark.asyncio
async def test_seed_captcha_skills_idempotent(sqlite_session_factory, memory_service):
    """Calling seed_captcha_skills() twice must not duplicate rows.

    There are 6 default CAPTCHA skills. A second call on the same database
    must leave exactly 6 rows — not 12.
    """
    from sqlalchemy import select, func
    from src.database.chat_db import MemoryProcedural

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        await memory_service.seed_captcha_skills()
        await memory_service.seed_captcha_skills()

    async with sqlite_session_factory() as db:
        count = (await db.execute(
            select(func.count()).select_from(MemoryProcedural)
            .where(MemoryProcedural.skill_name.like("captcha_%"))
        )).scalar_one()

    assert count == 6, (
        f"Expected exactly 6 CAPTCHA skills after two seed calls, got {count}"
    )


# ── Test 2: store_episode → retrieve round-trip ───────────────────────────────

@pytest.mark.asyncio
async def test_store_and_retrieve_episode(sqlite_session_factory, memory_service):
    """An episode stored for a domain must appear in retrieve() for that domain."""
    user_id = "user-test-001"
    domain = "example.com"
    task_summary = "Fill out the contact form on example.com"
    key_steps = [{"tool": "click", "args": {"selector": "#submit"}}]

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        episode_id = await memory_service.store_episode(
            user_id=user_id,
            domain=domain,
            task_summary=task_summary,
            outcome="SUCCESS",
            key_steps=key_steps,
        )

        ctx = await memory_service.retrieve(
            user_id=user_id,
            domain=domain,
            task_summary=task_summary,
        )

    assert episode_id, "store_episode must return a non-empty id"
    assert len(ctx.episodes) == 1, (
        f"Expected 1 episode in retrieved context, got {len(ctx.episodes)}"
    )
    assert ctx.episodes[0]["outcome"] == "SUCCESS"
    assert task_summary[:120] in ctx.episodes[0]["task_summary"] or \
           ctx.episodes[0]["task_summary"] in task_summary


# ── Test 3: apply_decay lowers confidence on a 30-day-old episode ─────────────

@pytest.mark.asyncio
async def test_apply_decay_reduces_confidence(sqlite_session_factory, memory_service):
    """apply_decay() must reduce the confidence_score of a 30-day-old episode."""
    from sqlalchemy import select, update
    from src.database.chat_db import MemoryEpisodic

    user_id = "user-test-002"
    domain = "stale.example.com"
    old_date = datetime.now(timezone.utc) - timedelta(days=30)

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        episode_id = await memory_service.store_episode(
            user_id=user_id,
            domain=domain,
            task_summary="An old task that nobody has revisited",
            outcome="SUCCESS",
            key_steps=[],
        )

    async with sqlite_session_factory() as db:
        await db.execute(
            update(MemoryEpisodic)
            .where(MemoryEpisodic.id == episode_id)
            .values(created_at=old_date, last_accessed=old_date)
        )
        await db.commit()

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        with patch.dict("src.services.memory_service._DECAY_LAST_RUN", {}, clear=True):
            await memory_service.apply_decay(user_id=user_id)

    async with sqlite_session_factory() as db:
        row = (await db.execute(
            select(MemoryEpisodic).where(MemoryEpisodic.id == episode_id)
        )).scalar_one_or_none()

    assert row is not None, "Episode should still exist (confidence above delete threshold)"
    assert row.confidence_score < 1.0, (
        f"confidence_score should have decayed below 1.0, got {row.confidence_score}"
    )
