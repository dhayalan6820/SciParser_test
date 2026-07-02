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


# ── Test 4: fresh rows (< 7 days) are NOT touched by apply_decay ──────────────

@pytest.mark.asyncio
async def test_apply_decay_does_not_touch_fresh_rows(sqlite_session_factory, memory_service):
    """Episodic and semantic rows created within the last 7 days must be untouched.

    apply_decay() only operates on rows whose last-access / last-validated timestamp
    is older than _DECAY_STALE_DAYS (7 days).  A row touched yesterday must keep its
    original confidence_score of 1.0.
    """
    from sqlalchemy import select, update
    from src.database.chat_db import MemoryEpisodic, MemorySemantic

    user_id = "user-fresh-001"
    domain = "fresh.example.com"
    recent_date = datetime.now(timezone.utc) - timedelta(days=2)

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        episode_id = await memory_service.store_episode(
            user_id=user_id,
            domain=domain,
            task_summary="Very recent task — should not be decayed",
            outcome="SUCCESS",
            key_steps=[],
        )

    async with sqlite_session_factory() as db:
        await db.execute(
            update(MemoryEpisodic)
            .where(MemoryEpisodic.id == episode_id)
            .values(created_at=recent_date, last_accessed=recent_date)
        )
        ep_row_before = (await db.execute(
            select(MemoryEpisodic).where(MemoryEpisodic.id == episode_id)
        )).scalar_one()
        original_score = ep_row_before.confidence_score
        await db.commit()

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        with patch.dict("src.services.memory_service._DECAY_LAST_RUN", {}, clear=True):
            await memory_service.apply_decay(user_id=user_id)

    async with sqlite_session_factory() as db:
        row = (await db.execute(
            select(MemoryEpisodic).where(MemoryEpisodic.id == episode_id)
        )).scalar_one_or_none()

    assert row is not None, "Fresh episode must still exist after apply_decay"
    assert row.confidence_score == original_score, (
        f"Fresh row must NOT be decayed: expected {original_score}, got {row.confidence_score}"
    )


# ── Test 5: rows decayed below 0.05 are hard-deleted ─────────────────────────

@pytest.mark.asyncio
async def test_apply_decay_hard_deletes_near_zero_rows(sqlite_session_factory, memory_service):
    """Episodic and semantic rows below _DECAY_DELETE_THRESHOLD (0.05) must be deleted.

    We insert a row with confidence_score already at 0.04 (below the threshold) and an
    old timestamp, then call apply_decay().  The row must not exist afterwards.
    """
    from sqlalchemy import select, update, insert
    from src.database.chat_db import MemoryEpisodic, MemorySemantic

    user_id = "user-delete-001"
    domain = "low-conf.example.com"
    old_date = datetime.now(timezone.utc) - timedelta(days=60)

    ep_id = str(__import__("uuid").uuid4())

    async with sqlite_session_factory() as db:
        await db.execute(
            insert(MemoryEpisodic).values(
                id=ep_id,
                user_id=user_id,
                domain=domain,
                task_summary="Barely-alive episode",
                outcome="FAIL",
                key_steps="[]",
                tags="[]",
                confidence_score=0.04,
                access_count=0,
                created_at=old_date,
                last_accessed=old_date,
            )
        )
        sem_id = str(__import__("uuid").uuid4())
        await db.execute(
            insert(MemorySemantic).values(
                id=sem_id,
                user_id=user_id,
                domain=domain,
                fact_key="dying_selector",
                fact_value="#gone",
                confidence_score=0.03,
                access_count=0,
                created_at=old_date,
                last_validated=old_date,
            )
        )
        await db.commit()

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        with patch.dict("src.services.memory_service._DECAY_LAST_RUN", {}, clear=True):
            await memory_service.apply_decay(user_id=user_id)

    async with sqlite_session_factory() as db:
        ep_row = (await db.execute(
            select(MemoryEpisodic).where(MemoryEpisodic.id == ep_id)
        )).scalar_one_or_none()
        sem_row = (await db.execute(
            select(MemorySemantic).where(MemorySemantic.id == sem_id)
        )).scalar_one_or_none()

    assert ep_row is None, (
        "Episodic row with confidence < 0.05 must be hard-deleted by apply_decay"
    )
    assert sem_row is None, (
        "Semantic row with confidence < 0.05 must be hard-deleted by apply_decay"
    )


# ── Test 6: second call within 6 hours is a no-op ────────────────────────────

@pytest.mark.asyncio
async def test_apply_decay_rate_limited_within_6_hours(sqlite_session_factory, memory_service):
    """A second apply_decay() call within 6 hours must be skipped entirely.

    After the first call the _DECAY_LAST_RUN timestamp is set.  A second call
    moments later must not alter any row — confidence_score must remain identical.
    """
    from sqlalchemy import select, update, insert
    from src.database.chat_db import MemoryEpisodic

    user_id = "user-ratelimit-001"
    domain = "ratelimit.example.com"
    old_date = datetime.now(timezone.utc) - timedelta(days=30)
    ep_id = str(__import__("uuid").uuid4())

    async with sqlite_session_factory() as db:
        await db.execute(
            insert(MemoryEpisodic).values(
                id=ep_id,
                user_id=user_id,
                domain=domain,
                task_summary="Stale task for rate-limit test",
                outcome="SUCCESS",
                key_steps="[]",
                tags="[]",
                confidence_score=0.9,
                access_count=0,
                created_at=old_date,
                last_accessed=old_date,
            )
        )
        await db.commit()

    import src.services.memory_service as _ms_mod

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        with patch.dict(_ms_mod._DECAY_LAST_RUN, {}, clear=True):
            await memory_service.apply_decay(user_id=user_id)

            async with sqlite_session_factory() as db:
                row_after_first = (await db.execute(
                    select(MemoryEpisodic).where(MemoryEpisodic.id == ep_id)
                )).scalar_one_or_none()

            score_after_first = row_after_first.confidence_score if row_after_first else None

            await memory_service.apply_decay(user_id=user_id)

            async with sqlite_session_factory() as db:
                row_after_second = (await db.execute(
                    select(MemoryEpisodic).where(MemoryEpisodic.id == ep_id)
                )).scalar_one_or_none()

    if score_after_first is None:
        assert row_after_second is None, (
            "Row deleted on first call must remain deleted after rate-limited second call"
        )
    else:
        assert row_after_second is not None, (
            "Row must still exist after the skipped second apply_decay call"
        )
        assert row_after_second.confidence_score == score_after_first, (
            f"Second call (rate-limited) must not change confidence_score: "
            f"first={score_after_first}, second={row_after_second.confidence_score}"
        )
