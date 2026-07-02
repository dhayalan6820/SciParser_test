"""Tests for CAPTCHA outcome learning in Brain._evaluate_captcha_outcome.

Covers three unit scenarios (success, failure, empty state) and one DB
integration test confirming that confidence_score in MemoryProcedural
actually changes after a simulated bypass outcome.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.services.brain import Brain


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_brain() -> Brain:
    """Return a Brain instance with memory_service wired to an AsyncMock."""
    brain = Brain.__new__(Brain)
    brain.memory_service = MagicMock()
    brain.memory_service._update_procedural = AsyncMock()
    brain.memory_service.store_reflection = AsyncMock()
    return brain


PENDING_RECAPTCHA = {
    "captcha_type": "recaptcha_v2",
    "skill_name": "captcha_recaptcha_v2",
}

CLEAN_OBS = "Page loaded successfully. No CAPTCHA present."
CAPTCHA_OBS = "Please complete the recaptcha to continue."
ERROR_OBS = "Error: The page could not be loaded."


# ── Test 1: CAPTCHA-free observation → success=True, no reflection ────────────

@pytest.mark.asyncio
async def test_captcha_resolved_calls_update_procedural_with_success():
    """When the new observation is CAPTCHA-free, _update_procedural(success=True)."""
    brain = _make_brain()
    captcha_state = {"pending": dict(PENDING_RECAPTCHA)}

    await brain._evaluate_captcha_outcome(
        captcha_state,
        observation=CLEAN_OBS,
        user_id="user-1",
        task_domain="example.com",
    )

    brain.memory_service._update_procedural.assert_awaited_once_with(
        "user-1",
        "captcha_recaptcha_v2",
        "example.com",
        [],
        success=True,
    )
    brain.memory_service.store_reflection.assert_not_awaited()

    assert "pending" not in captcha_state, (
        "_evaluate_captcha_outcome must pop 'pending' from captcha_state"
    )


# ── Test 2: CAPTCHA still present → success=False AND store_reflection ────────

@pytest.mark.asyncio
async def test_captcha_still_present_calls_update_procedural_with_failure_and_reflection():
    """When CAPTCHA lingers, _update_procedural(success=False) + store_reflection(HIGH)."""
    brain = _make_brain()
    captcha_state = {"pending": dict(PENDING_RECAPTCHA)}

    await brain._evaluate_captcha_outcome(
        captcha_state,
        observation=CAPTCHA_OBS,
        user_id="user-2",
        task_domain="shop.example.com",
    )

    brain.memory_service._update_procedural.assert_awaited_once_with(
        "user-2",
        "captcha_recaptcha_v2",
        "shop.example.com",
        [],
        success=False,
    )

    brain.memory_service.store_reflection.assert_awaited_once()
    _call_kwargs = brain.memory_service.store_reflection.call_args
    assert _call_kwargs.kwargs.get("category") == "CAPTCHA", (
        "store_reflection must be called with category='CAPTCHA'"
    )
    assert _call_kwargs.kwargs.get("severity") == "HIGH", (
        "store_reflection must be called with severity='HIGH'"
    )


# ── Test 3: error observation → treated as failure (not resolved) ─────────────

@pytest.mark.asyncio
async def test_error_observation_treated_as_captcha_failure():
    """An observation starting with 'Error' is treated as failure even if no CAPTCHA text."""
    brain = _make_brain()
    captcha_state = {"pending": dict(PENDING_RECAPTCHA)}

    await brain._evaluate_captcha_outcome(
        captcha_state,
        observation=ERROR_OBS,
        user_id="user-3",
        task_domain="app.example.com",
    )

    _up_call = brain.memory_service._update_procedural.call_args
    assert _up_call.kwargs.get("success") is False or _up_call.args[4] is False, (
        "Error observation must produce success=False"
    )
    brain.memory_service.store_reflection.assert_awaited_once()


# ── Test 4: empty captcha_state → neither function called ─────────────────────

@pytest.mark.asyncio
async def test_empty_captcha_state_causes_no_updates():
    """When captcha_state has no 'pending' entry, no memory calls are made."""
    brain = _make_brain()
    captcha_state = {}

    await brain._evaluate_captcha_outcome(
        captcha_state,
        observation=CLEAN_OBS,
        user_id="user-4",
        task_domain="example.com",
    )

    brain.memory_service._update_procedural.assert_not_awaited()
    brain.memory_service.store_reflection.assert_not_awaited()


# ── Test 5: DB integration — confidence_score changes after outcomes ───────────

@pytest.mark.asyncio
async def test_captcha_confidence_score_changes_in_db(sqlite_session_factory):
    """confidence_score on captcha_* MemoryProcedural changes after success/failure runs."""
    from sqlalchemy import select
    from src.database.chat_db import MemoryProcedural
    from src.services.memory_service import MemoryService

    user_id = "user-captcha-db"
    skill_name = "captcha_recaptcha_v2"
    domain = "test.example.com"

    memory_service = MemoryService(llm=None)

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        await memory_service._update_procedural(
            user_id, skill_name, domain, [], success=True
        )

    async with sqlite_session_factory() as db:
        row = (await db.execute(
            select(MemoryProcedural).where(
                MemoryProcedural.user_id == user_id,
                MemoryProcedural.skill_name == skill_name,
            )
        )).scalar_one_or_none()

    assert row is not None, "MemoryProcedural row must exist after _update_procedural"
    score_after_success = row.confidence_score
    assert score_after_success > 0.5, (
        f"After a success, confidence_score should be > 0.5, got {score_after_success}"
    )

    with patch("src.services.memory_service.AsyncSessionLocal", sqlite_session_factory):
        for _ in range(3):
            await memory_service._update_procedural(
                user_id, skill_name, domain, [], success=False
            )

    async with sqlite_session_factory() as db:
        row = (await db.execute(
            select(MemoryProcedural).where(
                MemoryProcedural.user_id == user_id,
                MemoryProcedural.skill_name == skill_name,
            )
        )).scalar_one_or_none()

    assert row is not None
    score_after_failures = row.confidence_score
    assert score_after_failures < score_after_success, (
        f"Three failures must drive confidence_score below the post-success value "
        f"({score_after_failures} >= {score_after_success})"
    )


# ── Test 6: no memory_service → silently skipped ──────────────────────────────

@pytest.mark.asyncio
async def test_no_memory_service_is_skipped():
    """When memory_service is None the method returns without error."""
    brain = Brain.__new__(Brain)
    brain.memory_service = None

    captcha_state = {"pending": dict(PENDING_RECAPTCHA)}
    await brain._evaluate_captcha_outcome(
        captcha_state,
        observation=CAPTCHA_OBS,
        user_id="user-5",
        task_domain="example.com",
    )
    assert captcha_state.get("pending") is not None, (
        "pending entry should NOT be popped when memory_service is None"
    )
