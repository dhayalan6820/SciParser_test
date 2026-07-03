"""Tests for Task #116: letting users override a saved account/credential
mid-conversation instead of the Input-Understanding step silently reusing a
stale value from history_context / prior_session_state.

Covers:
  - Brain._is_credential_override_intent() heuristic used to flag the
    stronger "ignore stale history" directive to Agent 1.
  - ATAGProcessor.run_input_understanding() building a precedence-aware
    prompt (current-message-wins language, plus an extra override directive
    when override_intent=True), without regressing the legitimate case of
    reusing prior confirmed inputs across turns.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest

from src.services.brain import Brain
from src.services.ATAG import ATAGProcessor


# ── Brain._is_credential_override_intent ────────────────────────────────────

@pytest.mark.parametrize(
    "message",
    [
        "Actually, use a different account this time.",
        "Try another account for this one.",
        "Use this email instead: new@example.com",
        "That's the wrong account, use my other one.",
        "Switch accounts and log in again.",
        "instead use jane@example.com / newpassword123",
    ],
)
def test_override_intent_detected(message):
    assert Brain._is_credential_override_intent(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Book me a flight to Paris next week.",
        "Continue where you left off.",
        "Log in with the same account as before.",
        "What's the status of my task?",
    ],
)
def test_override_intent_not_detected_for_normal_messages(message):
    assert Brain._is_credential_override_intent(message) is False


# ── ATAGProcessor.run_input_understanding prompt construction ───────────────

class _StubATAGProcessor(ATAGProcessor):
    """Bypasses the real CrewAI/LLM call so we can inspect the prompt that
    would have been sent, without network access or an OpenAI key."""

    def __init__(self):
        # Intentionally skip ATAGProcessor.__init__ (needs a real llm) — we
        # only exercise run_input_understanding's prompt-building logic.
        self.captured_description = None

    def _get_planner_agent(self):
        return None

    async def _run_crew_task(self, agent, description, expected_output):
        self.captured_description = description
        return '{"status": "READY", "task_type": "test", "task_summary": "x", "confirmed_inputs": {}, "discovery_strategy": "direct_execution"}'


@pytest.mark.asyncio
async def test_history_context_always_carries_precedence_rule():
    processor = _StubATAGProcessor()
    await processor.run_input_understanding(
        "Book a table for 2 tonight",
        history_context="User: my email is old@example.com",
    )
    assert "current request's value ALWAYS wins" in processor.captured_description
    assert "old@example.com" in processor.captured_description


@pytest.mark.asyncio
async def test_override_intent_adds_explicit_ignore_history_directive():
    processor = _StubATAGProcessor()
    await processor.run_input_understanding(
        "Actually use a different account this time: new@example.com",
        history_context="User: my email is old@example.com",
        override_intent=True,
    )
    assert "Do NOT reuse any account/email/username/password" in processor.captured_description


@pytest.mark.asyncio
async def test_no_override_directive_when_intent_not_flagged():
    processor = _StubATAGProcessor()
    await processor.run_input_understanding(
        "Continue booking the same flight as before",
        history_context="User: my email is old@example.com",
        override_intent=False,
    )
    # Legitimate reuse case: no extra "ignore history" directive should be
    # injected, so history remains available to fill in the same account.
    assert "Do NOT reuse any account/email/username/password" not in processor.captured_description


@pytest.mark.asyncio
async def test_no_precedence_text_when_no_history_context():
    processor = _StubATAGProcessor()
    await processor.run_input_understanding("Book a table for 2 tonight")
    assert "RECENT CHAT HISTORY" not in processor.captured_description
    assert "PRECEDENCE RULE" not in processor.captured_description


# ── Never persist personal data: redaction + in-memory-only credential cache ─
#
# Follow-up to Task #116: confirmed_inputs (which may include account/
# credential values) must never be written to durable storage — only kept in
# memory for the lifetime of a run. Anything that reaches AgentExecutionLog
# or ChatSession.session_state must be redacted first.

def test_redact_confirmed_inputs_keeps_keys_strips_values():
    raw = {"email": "user@example.com", "password": "hunter2", "website": "example.com"}
    redacted = Brain._redact_confirmed_inputs(raw)
    assert set(redacted.keys()) == set(raw.keys())
    assert all(v == "[REDACTED]" for v in redacted.values())
    # Original dict must be untouched — execution still needs the real values.
    assert raw["password"] == "hunter2"


def test_redact_confirmed_inputs_handles_empty():
    assert Brain._redact_confirmed_inputs({}) == {}
    assert Brain._redact_confirmed_inputs(None) == {}


def test_pending_confirmed_inputs_cache_is_in_memory_only():
    """The Brain instance must hold real confirmed_inputs in a plain in-memory
    dict (never touching the DB) so a paused obstacle run can resume with the
    real values, while a redacted placeholder is what actually gets persisted."""
    brain = Brain.__new__(Brain)
    brain.pending_confirmed_inputs = {}

    real_inputs = {"email": "user@example.com", "password": "hunter2"}
    chat_id = "chat-abc"
    brain.pending_confirmed_inputs[chat_id] = real_inputs

    # Resume: pop (single-use) and get the real values back.
    resumed = brain.pending_confirmed_inputs.pop(chat_id, None)
    assert resumed == real_inputs
    # Cache is now empty — a second resume attempt (e.g. after a restart)
    # must not find stale credentials sitting around.
    assert brain.pending_confirmed_inputs.pop(chat_id, None) is None


# ── Task #118: never persist secrets into ToolExecutionLog ──────────────────
#
# Beyond confirmed_inputs (redacted above), the tool-execution graph itself
# must scrub any known secret value (a sensitive confirmed_inputs value, or
# the OTP code just supplied to resume an obstacle) out of tool_input/
# tool_output before they reach ToolExecutionLog — a generic "text"/"value"
# form-fill arg is exactly how a password or OTP gets typed into a page.

def test_tool_input_dict_scrubbed_of_known_secret_values():
    tool_args = {"selector": "#otp-field", "text": "123456"}
    secret_values = ["123456"]
    scrubbed = {
        k: Brain._redact_secret_values_in_text(v, secret_values)
        for k, v in tool_args.items()
    }
    assert scrubbed["selector"] == "#otp-field"
    assert scrubbed["text"] == "[REDACTED]"


def test_tool_output_text_scrubbed_of_known_secret_values():
    observation = "Filled field with 123456 and clicked Submit. Success."
    scrubbed = Brain._redact_secret_values_in_text(observation, ["123456"])
    assert "123456" not in scrubbed
    assert "Success" in scrubbed


def test_run_secret_values_combines_confirmed_inputs_and_obstacle_answer():
    confirmed_inputs = {"email": "user@example.com", "password": "hunter2"}
    secret_values = Brain._extract_sensitive_values(confirmed_inputs)
    otp_answer = "998877"
    secret_values.append(otp_answer)

    tool_args = {"text": "hunter2"}
    scrubbed_args = {
        k: Brain._redact_secret_values_in_text(v, secret_values)
        for k, v in tool_args.items()
    }
    observation = "Entered 998877 into verification field."
    scrubbed_observation = Brain._redact_secret_values_in_text(observation, secret_values)

    assert scrubbed_args["text"] == "[REDACTED]"
    assert "998877" not in scrubbed_observation
    assert "user@example.com" not in secret_values
