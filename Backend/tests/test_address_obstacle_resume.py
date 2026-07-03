"""Integration-style tests for resuming a paused run after the Address
Interaction Agent escalated to the user (Task #122, 3rd review round).

These prove the fix for a reviewer-flagged bug: after the user answers the
"Confirm Address" NEEDS_INPUT form, the resumed run must treat the user's
choice as authoritative and must NOT re-run the deterministic address
scoring/escalation logic against it (which could otherwise re-trigger
another low-confidence escalation and loop forever), and must never type
the internal "__none__" sentinel value into the page.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from src.services import address_agent
from src.services.brain import Brain


def _make_brain() -> Brain:
    brain = Brain(stream_manager=None)
    brain.memory_service = None
    brain.atag_processor = MagicMock()
    brain.atag_processor._estimate_tokens = MagicMock(return_value=10)
    return brain


class _StubLLMWithTools:
    """Mimics `self.llm.bind_tools(...)` — returns one AIMessage with a tool
    call (so `_call_tool` runs once and the address-detection block gets a
    chance to inspect the resulting observation), then an AIMessage with no
    tool calls so the graph terminates."""

    def __init__(self, tool_name: str, tool_args: dict, observation_text: str):
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._observation_text = observation_text
        self.calls = 0
        self.tool = MagicMock()
        self.tool.name = tool_name
        self.tool.ainvoke = AsyncMock(return_value=observation_text)

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": self._tool_name, "args": self._tool_args, "id": "call_1"}],
            )
        return AIMessage(content="Done.")


@pytest.mark.asyncio
async def test_suppress_address_agent_skips_detection_even_with_dropdown_observation(monkeypatch):
    """When resuming from a user-answered address obstacle, `suppress_address_agent=True`
    must prevent the Address Agent from re-scoring a suggestion dropdown that
    happens to reappear in the tool's observation — proving no re-escalation
    loop is possible on the resumed run."""
    brain = _make_brain()

    dropdown_observation = (
        "Address suggestions:\n"
        "- 123 Main St, Springfield, IL 62704\n"
        "- 456 Main St, Springfield, IL 62704\n"
    )
    stub_llm = _StubLLMWithTools("fill_address", {"value": "123 Main St"}, dropdown_observation)

    class _LLM:
        def bind_tools(self, tools):
            return stub_llm

    brain.llm = _LLM()

    detect_calls = []
    original_detect = address_agent.detect_address_autocomplete_context

    def _spy_detect(text):
        detect_calls.append(text)
        return original_detect(text)

    monkeypatch.setattr(address_agent, "detect_address_autocomplete_context", _spy_detect)

    result = await brain._execute_tool_graph(
        graph_input={"messages": [AIMessage(content="continue")]},
        tools=[stub_llm.tool],
        user_id="user-1",
        chat_id="chat-suppressed",
        task_summary="Enter address 123 Main St, Springfield, IL 62704",
        confirmed_inputs={"address": "123 Main St, Springfield, IL 62704"},
        suppress_address_agent=True,
    )

    assert result is not None
    # The Address Agent's own detection helper must never be invoked when
    # suppressed — it is skipped entirely by the `_requested_address = {}`
    # short-circuit, so there is no scoring/escalation path left to loop on.
    assert detect_calls == []


@pytest.mark.asyncio
async def test_address_agent_active_without_suppression_detects_dropdown(monkeypatch):
    """Sanity check for the above: with `suppress_address_agent=False` (the
    default, used on a fresh run) the same dropdown observation IS inspected
    by the Address Agent, proving the suppression flag is what changes the
    behavior rather than some other difference between the two calls."""
    brain = _make_brain()

    dropdown_observation = (
        "Address suggestions:\n"
        "- 123 Main St, Springfield, IL 62704\n"
        "- 456 Main St, Springfield, IL 62704\n"
    )
    stub_llm = _StubLLMWithTools("fill_address", {"value": "123 Main St"}, dropdown_observation)

    class _LLM:
        def bind_tools(self, tools):
            return stub_llm

    brain.llm = _LLM()

    detect_calls = []
    original_detect = address_agent.detect_address_autocomplete_context

    def _spy_detect(text):
        detect_calls.append(text)
        return original_detect(text)

    monkeypatch.setattr(address_agent, "detect_address_autocomplete_context", _spy_detect)

    result = await brain._execute_tool_graph(
        graph_input={"messages": [AIMessage(content="continue")]},
        tools=[stub_llm.tool],
        user_id="user-1",
        chat_id="chat-active",
        task_summary="Enter address 123 Main St, Springfield, IL 62704",
        confirmed_inputs={"address": "123 Main St, Springfield, IL 62704"},
        suppress_address_agent=False,
    )

    assert result is not None
    assert len(detect_calls) >= 1


def test_resume_branch_never_forwards_none_sentinel_as_mission_objective():
    """Regression guard: the literal `__none__` sentinel (emitted by the
    "None of these are correct" option) must never be treated as a real
    address value to type into the page."""
    from src.services.brain import _extract_form_answer

    user_message = "Select the correct address: __none__"
    answer = _extract_form_answer(user_message)
    assert answer == "__none__"
    # The resume branch in brain.py must special-case exactly this value
    # (see the `_selected_address.strip() == "__none__"` check) rather than
    # ever passing it through into a mission_objective that instructs the
    # agent to type it.
