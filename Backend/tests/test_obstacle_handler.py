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

OTP_OBS = "Sign in: We've sent you a code. Please check your email for a code and enter it below."
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


# ── Regression: bare mentions of "verification code"/"otp" elsewhere on a
# page (help text, footer, unrelated marketing/SMS-signup banner) must never
# pause the run and ask the user for a code that was never actually
# required — only an imperative "enter/type/confirm the code" or an explicit
# "code sent to you"/"required to continue" framing counts as a real block.

@pytest.mark.parametrize(
    "observation",
    [
        "Sign up for texts to receive exclusive deals. We'll send you a verification code to confirm your number.",
        "FAQ: What is a verification code? It's a temporary code used to confirm your identity.",
        "Enter your promo code at checkout to save 10%.",
        "Need help? Chat with us. Standard SMS/OTP rates may apply for text alerts.",
        "Your security code (CVV) is the 3-digit number on the back of your card.",
        "Join our newsletter — verification code required to unsubscribe at any time.",
    ],
)
def test_detect_otp_ignores_unrelated_page_mentions(observation):
    assert detect_otp(observation) is None
    assert detect_obstacle(observation) is None


@pytest.mark.parametrize(
    "observation",
    [
        "Sign in to your account: please enter the verification code we just sent to your email to continue.",
        "Two-factor authentication: a verification code is required to continue. Enter it below.",
        "Login verification: please enter your OTP below to proceed.",
        "To protect your account, your one-time password has been sent to your registered phone number.",
        "Complete payment: we've texted you a code. Enter the 6-digit code to verify your account.",
        "Checkout — verify it's really you: enter the code sent to your phone before we charge your card.",
    ],
)
def test_detect_otp_still_matches_genuine_blocking_prompts(observation):
    assert detect_otp(observation) == "email_or_sms_code"
    match = detect_obstacle(observation)
    assert match is not None
    assert match.category == "otp"
    assert match.requires_human_input is True


# ── Regression: an OTP-shaped prompt on a step that is NOT sign-in or
# payment/checkout (e.g. an address-verification widget) must never pause the
# run and interrupt the user — only sign-in/authentication and payment steps
# are places a site legitimately needs to prove identity mid-task.

@pytest.mark.parametrize(
    "observation",
    [
        "Frontier requires a verification code to proceed with the address check.",
        "Please enter the verification code to confirm your shipping address.",
        "Enter the 6-digit code sent to your phone to validate your delivery address.",
        "A verification code is required to continue with the address lookup.",
    ],
)
def test_detect_otp_ignores_genuine_prompts_outside_signin_or_payment(observation):
    assert detect_otp(observation) is None
    assert detect_obstacle(observation) is None


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


def test_build_input_form_otp_retry_requests_new_code_never_implies_reuse():
    """When the SAME obstacle recurs after the user already answered once
    (is_retry=True), the prompt must explicitly say the previous code didn't
    work and ask for a NEW one — it must never silently resubmit the stale
    value or word the prompt as if this were the first ask."""
    match = ObstacleMatch(category="otp", obstacle_type="email_or_sms_code", requires_human_input=True)

    first_form = build_input_form(match, "example.com", is_retry=False)
    retry_form = build_input_form(match, "example.com", is_retry=True)

    assert retry_form["description"] != first_form["description"]
    retry_desc_lower = retry_form["description"].lower()
    assert "new" in retry_desc_lower
    assert any(word in retry_desc_lower for word in ("didn't work", "expired", "already been used"))
    # Still the same well-formed OTP form schema, just different copy.
    assert retry_form["obstacle_category"] == "otp"
    assert len(retry_form["sections"]) == 1


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


# ── Task #118: never persist raw obstacle-answer values (e.g. OTP codes) ────
#
# Root cause of "agent reuses an expired OTP": Message.content stored the raw
# answer, and history_context (built from the last 5 Message rows) fed it
# back into Agent 1 on a later turn, so a stale/expired code could look like
# a still-valid "confirmed input". The fix stores a fixed placeholder for any
# message answering a pending obstacle, so a code can never resurface via
# chat history.

from src.services.brain import Brain


def test_obstacle_answer_message_content_never_contains_raw_value():
    otp_code = "483920"
    placeholder = Brain.OBSTACLE_ANSWER_PLACEHOLDER_TEMPLATE.format(label="email_or_sms_code")
    assert otp_code not in placeholder
    assert "email_or_sms_code" in placeholder


@pytest.mark.asyncio
async def test_obstacle_answer_never_written_to_message_content_in_db(sqlite_session_factory):
    """End-to-end version of the placeholder check: simulate the exact
    Message-insert Brain.process_message performs when resuming a paused
    obstacle run, and confirm the OTP code never lands in the DB row."""
    from src.database.chat_db import Message
    from sqlalchemy import select
    from datetime import datetime, timezone
    import uuid

    otp_code = "998877"
    pending_obstacle = {"obstacle_type": "email_or_sms_code"}
    stored_content = Brain.OBSTACLE_ANSWER_PLACEHOLDER_TEMPLATE.format(
        label=pending_obstacle.get("obstacle_type", "verification")
    )

    async with sqlite_session_factory() as db:
        msg = Message(
            message_id=str(uuid.uuid4()),
            chat_id="chat-otp",
            user_id="user-1",
            role="user",
            content=stored_content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.commit()

    async with sqlite_session_factory() as db:
        result = await db.execute(select(Message).where(Message.chat_id == "chat-otp"))
        row = result.scalar_one()
        assert otp_code not in row.content
        assert row.content == stored_content


# ── Task #118: never persist secrets (password/OTP/card) into free text ─────

def test_is_sensitive_key_matches_common_secret_field_names():
    for key in ["password", "Password", "otp", "otp_code", "verification_code", "cvv", "card_number", "pin"]:
        assert Brain._is_sensitive_key(key) is True
    for key in ["email", "website", "origin_city", "task_summary"]:
        assert Brain._is_sensitive_key(key) is False


def test_extract_sensitive_values_pulls_only_sensitive_fields():
    confirmed_inputs = {
        "email": "user@example.com",
        "password": "hunter2",
        "otp_code": "123456",
        "destination": "Paris",
    }
    values = Brain._extract_sensitive_values(confirmed_inputs)
    assert "hunter2" in values
    assert "123456" in values
    assert "user@example.com" not in values
    assert "Paris" not in values


def test_extract_sensitive_values_handles_empty():
    assert Brain._extract_sensitive_values(None) == []
    assert Brain._extract_sensitive_values({}) == []


def test_redact_secret_values_in_text_scrubs_known_values():
    text = "Typed password hunter2 into the field and submitted OTP 123456."
    scrubbed = Brain._redact_secret_values_in_text(text, ["hunter2", "123456"])
    assert "hunter2" not in scrubbed
    assert "123456" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_redact_secret_values_in_text_ignores_short_values_and_non_strings():
    # Values under 3 chars are skipped to avoid mass-redacting common substrings.
    assert Brain._redact_secret_values_in_text("ab cd", ["ab"]) == "ab cd"
    # Non-string input passed through untouched.
    assert Brain._redact_secret_values_in_text({"a": 1}, ["secret"]) == {"a": 1}
    assert Brain._redact_secret_values_in_text(None, ["secret"]) is None


def test_mask_labeled_secrets_scrubs_label_value_pairs():
    text = "Here you go — password: hunter2 and CVV: 123"
    masked = Brain._mask_labeled_secrets(text)
    assert "hunter2" not in masked
    assert "123" not in masked
    assert "password: [REDACTED]" in masked
    assert "CVV: [REDACTED]" in masked


def test_mask_labeled_secrets_leaves_normal_text_untouched():
    text = "Book me a flight to Paris next Tuesday."
    assert Brain._mask_labeled_secrets(text) == text


def test_mask_labeled_secrets_handles_empty():
    assert Brain._mask_labeled_secrets("") == ""
    assert Brain._mask_labeled_secrets(None) is None


# ── Live bug: legacy raw OTP rows already in the DB (written before the
# Task #118 fix shipped, or any other write-path gap) must not resurrect a
# stale code once they're read back into history_context. This is
# defense-in-depth applied at READ time, mirroring the write-time scrub, so
# pre-existing unmasked data can never poison a later Agent-1 pass.

def test_mask_labeled_secrets_scrubs_legacy_otp_and_verification_phrasings():
    for text, otp in [
        ("try this OTP : L4EX3M", "L4EX3M"),
        ("6-Digit Verification Code: LK763F", "LK763F"),
        ("Verification Code: XYLCHM", "XYLCHM"),
    ]:
        masked = Brain._mask_labeled_secrets(text)
        assert otp not in masked
        assert "[REDACTED]" in masked


def test_history_context_construction_masks_legacy_unredacted_history(monkeypatch):
    """Simulates the exact history_context list-comprehension in
    Brain.process_message: even if chat_history contains an old Message row
    that was never scrubbed, building history_context must not leak the raw
    OTP value into the Agent-1 prompt."""
    from langchain_core.messages import HumanMessage, AIMessage

    chat_history = [
        AIMessage(content="booking.com is asking for a verification code..."),
        HumanMessage(content="try this OTP : L4EX3M"),
    ]
    history_context = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {Brain._mask_labeled_secrets(m.content)}"
        for m in chat_history[-5:]
    ])
    assert "L4EX3M" not in history_context
    assert "[REDACTED]" in history_context
