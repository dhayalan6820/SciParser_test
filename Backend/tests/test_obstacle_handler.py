"""Tests for the generic obstacle-handling framework (obstacle_handler.py)
and its wiring into Brain (pause on ObstacleInputNeeded, resume via
pending_obstacle in ChatSession.session_state).
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import json
import pytest

from src.services.obstacle_handler import (
    detect_captcha_type,
    detect_otp,
    detect_obstacle,
    build_input_form,
    ObstacleMatch,
    ObstacleInputNeeded,
)
from src.services.brain import _extract_form_answer
from src.database.chat_db import ChatSession


# ── detect_obstacle / detect_otp ────────────────────────────────────────────

OTP_OBS = "We've sent you a code. Please check your email for a code and enter it below."
CAPTCHA_OBS = "Please solve the recaptcha verification code challenge below."
CLEAN_OBS = "Booking confirmed! Your reservation is complete."


def test_detect_otp_matches_verification_prompt():
    match = detect_obstacle(OTP_OBS)
    assert match is not None
    assert match.category == "otp"
    assert match.obstacle_type == "email_or_sms_code"
    assert match.requires_human_input is True
    assert match.skill_name == "otp_email_or_sms_code"


def test_captcha_takes_priority_over_otp_when_both_present():
    # CAPTCHA copy that also contains "verification code" must resolve to
    # CAPTCHA (agent can self-solve) rather than OTP (would ask the human
    # unnecessarily for something the agent should attempt first).
    match = detect_obstacle(CAPTCHA_OBS)
    assert match is not None
    assert match.category == "captcha"
    assert match.requires_human_input is False
    assert detect_otp(CAPTCHA_OBS) is None


def test_no_obstacle_on_clean_observation():
    assert detect_obstacle(CLEAN_OBS) is None
    assert detect_captcha_type(CLEAN_OBS) is None
    assert detect_otp(CLEAN_OBS) is None


def test_detect_obstacle_handles_empty_and_none():
    assert detect_obstacle("") is None
    assert detect_obstacle(None) is None


# ── build_input_form ─────────────────────────────────────────────────────────

def test_build_input_form_for_otp_matches_needs_input_schema():
    match = ObstacleMatch(category="otp", obstacle_type="email_or_sms_code", requires_human_input=True)
    form = build_input_form(match, "example.com")

    assert form["title"]
    assert "example.com" in form["description"]
    assert isinstance(form["sections"], list) and len(form["sections"]) == 1

    section = form["sections"][0]
    assert "fields" in section
    field = section["fields"][0]
    for key in ("id", "label", "type", "placeholder", "required", "options", "note"):
        assert key in field
    assert field["required"] is True
    assert form["obstacle_type"] == "email_or_sms_code"
    assert form["obstacle_category"] == "otp"
    assert "security_note" in form


def test_build_input_form_unknown_category_falls_back_gracefully():
    match = ObstacleMatch(category="future_type", obstacle_type="x", requires_human_input=True)
    form = build_input_form(match, "example.com")
    assert form["title"] == "Input Required"
    assert form["sections"] == []


# ── ObstacleInputNeeded exception ───────────────────────────────────────────

def test_obstacle_input_needed_carries_match_and_domain():
    match = ObstacleMatch(category="otp", obstacle_type="email_or_sms_code", requires_human_input=True)
    exc = ObstacleInputNeeded(match, "example.com")
    assert exc.match is match
    assert exc.site_domain == "example.com"
    assert "example.com" in str(exc)


# ── _extract_form_answer ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "message,expected",
    [
        ("Verification Code: 483920", "483920"),
        ("otp_code: 001122", "001122"),
        ("999999", "999999"),  # no "Label: value" pattern -> full message
        ("  Code:   123 456  ", "123 456"),
    ],
)
def test_extract_form_answer(message, expected):
    assert _extract_form_answer(message) == expected


# ── DB integration: pending_obstacle round-trips through ChatSession.session_state ──

@pytest.mark.asyncio
async def test_pending_obstacle_persists_and_pops_from_session_state(sqlite_session_factory):
    """Simulates the two halves of the pause/resume contract Brain relies on:
    writing pending_obstacle into session_state when pausing, and popping it
    back out (dict semantics used by process_message) when resuming."""
    async with sqlite_session_factory() as db:
        session = ChatSession(id="chat-1", user_id="user-1", title="Test chat", session_state=None)
        db.add(session)
        await db.commit()

    pending_obstacle_state = {
        "obstacle_type": "email_or_sms_code",
        "obstacle_category": "otp",
        "skill_name": "otp_email_or_sms_code",
        "site_domain": "example.com",
        "task_summary": "Book a flight",
        "confirmed_inputs": {"origin": "NYC"},
        "discovery_strategy": "direct_execution",
        "attempt": 1,
    }

    async with sqlite_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(select(ChatSession).where(ChatSession.id == "chat-1"))
        row = result.scalar_one()
        existing_state = json.loads(row.session_state) if row.session_state else {}
        existing_state["pending_obstacle"] = pending_obstacle_state
        row.session_state = json.dumps(existing_state)
        await db.commit()

    async with sqlite_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(select(ChatSession).where(ChatSession.id == "chat-1"))
        row = result.scalar_one()
        prior_session_state = json.loads(row.session_state)
        popped = prior_session_state.pop("pending_obstacle", None)

    assert popped == pending_obstacle_state
    assert "pending_obstacle" not in prior_session_state
