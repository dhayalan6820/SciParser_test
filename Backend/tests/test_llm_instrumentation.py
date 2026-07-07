"""Integration tests: real token_usage metadata flows end-to-end into LlmRequest rows.

These tests exercise the full pipeline that runs when a browser agent completes:

  LangChain ainvoke response
      → extract_token_usage()         (ATAG.py — pulls counts from response metadata)
      → count_message_tokens()        (llm_instrumentation.py — categorises prompt breakdown)
      → record_llm_request()          (llm_instrumentation.py — writes LlmRequest row to DB)
      → LlmRequest row in DB          ← asserted here

The DB is an in-memory SQLite instance (via conftest.sqlite_session_factory) so
no real Postgres connection is required.
"""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import uuid
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from sqlalchemy import select

from src.database.chat_db import LlmRequest
from src.services.ATAG import calculate_llm_cost, extract_token_usage
from src.utils.llm_instrumentation import count_message_tokens, record_llm_request


# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for real LangChain AIMessage objects
# ---------------------------------------------------------------------------

def _response_usage_metadata(input_tokens: int, output_tokens: int) -> Any:
    """Simulate a newer LangChain / Gemini response with usage_metadata."""
    return SimpleNamespace(
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens},
        response_metadata={},
        content="I'll click the submit button.",
    )


def _response_openrouter(prompt_tokens: int, completion_tokens: int) -> Any:
    """Simulate an OpenRouter / older LangChain response with response_metadata."""
    return SimpleNamespace(
        usage_metadata=None,
        response_metadata={
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "finish_reason": "stop",
        },
        content="Done.",
    )


# ---------------------------------------------------------------------------
# Unit: extract_token_usage — covers both metadata formats
# ---------------------------------------------------------------------------

def test_extract_token_usage_reads_usage_metadata():
    """usage_metadata path (newer LangChain / Gemini)."""
    model = "google/gemini-3-flash-preview"
    resp = _response_usage_metadata(input_tokens=1200, output_tokens=300)
    usage = extract_token_usage(resp, model)

    assert usage["input"] == 1200
    assert usage["output"] == 300
    assert usage["total"] == 1500
    expected_cost = calculate_llm_cost(model, 1200, 300)
    assert usage["cost"] == expected_cost
    assert usage["cost"] > 0


def test_extract_token_usage_reads_response_metadata():
    """response_metadata / token_usage path (OpenRouter / older LangChain)."""
    model = "google/gemini-3-flash-preview"
    resp = _response_openrouter(prompt_tokens=800, completion_tokens=200)
    usage = extract_token_usage(resp, model)

    assert usage["input"] == 800
    assert usage["output"] == 200
    assert usage["total"] == 1000
    assert usage["cost"] > 0


def test_extract_token_usage_returns_empty_for_missing_metadata():
    """When neither metadata field is present, an empty dict is returned."""
    resp = SimpleNamespace(usage_metadata=None, response_metadata={})
    assert extract_token_usage(resp, "unknown-model") == {}


# ---------------------------------------------------------------------------
# Unit: count_message_tokens — categorisation
# ---------------------------------------------------------------------------

def test_count_message_tokens_categorises_correctly():
    """System, user, history, and tool messages are binned into the right buckets."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    messages = [
        SystemMessage(content="You are a helpful browser agent."),
        HumanMessage(content="Navigate to example.com and click Sign In."),  # history
        AIMessage(content="I will click the sign-in button."),
        ToolMessage(content='{"result": "clicked"}', tool_call_id="t1"),
        HumanMessage(content="Good. Now fill in the username field."),  # current turn
    ]

    counts = count_message_tokens(messages)

    assert counts["system_tokens"] > 0, "system prompt should be counted"
    assert counts["user_tokens"] > 0,   "current user turn should be counted"
    assert counts["history_tokens"] > 0, "prior AI + human messages should go to history"
    assert counts["tool_tokens"] > 0,   "tool result should be counted"
    # No memory/RAG markers in these messages
    assert counts["memory_tokens"] == 0
    assert counts["rag_tokens"] == 0


def test_count_message_tokens_detects_memory_and_rag_markers():
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content="You are an agent."),
        HumanMessage(
            content=(
                "EXECUTION MEMORY: user prefers dark mode.\n"
                "RETRIEVED CONTEXT: relevant docs about login flow.\n"
                "Please proceed with the login task."
            )
        ),
    ]
    counts = count_message_tokens(messages)

    assert counts["memory_tokens"] > 0, "memory marker should carve out memory_tokens"
    assert counts["rag_tokens"] > 0,    "RAG marker should carve out rag_tokens"
    # user_tokens should be smaller than the raw total because fractions were carved out
    raw_estimate = len(messages[-1].content) // 4
    assert counts["user_tokens"] < raw_estimate


# ---------------------------------------------------------------------------
# Integration: record_llm_request → LlmRequest row in DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_llm_request_writes_nonzero_row(sqlite_session_factory, monkeypatch):
    """
    Mock a complete LangChain ainvoke response, run it through extract_token_usage,
    and assert a non-zero LlmRequest row lands in the DB with correct fields.
    """
    import src.database.chat_db as chat_db_module

    monkeypatch.setattr(chat_db_module, "AsyncSessionLocal", sqlite_session_factory)

    model = "google/gemini-3-flash-preview"
    user_id = str(uuid.uuid4())
    chat_id = f"thread-{uuid.uuid4()}"

    # ── 1. Simulate ainvoke returning a response with usage_metadata ──────────
    resp = _response_usage_metadata(input_tokens=2500, output_tokens=400)

    # ── 2. Extract token counts exactly as brain.py / ATAG.py do ─────────────
    usage = extract_token_usage(resp, model)
    assert usage, "extract_token_usage must return a non-empty dict for a valid response"

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [
        SystemMessage(content="You are a web automation agent. Use the browser tools."),
        HumanMessage(content="Go to https://example.com and click Sign In."),
        AIMessage(content="Navigating to the page now."),
        HumanMessage(content="Click the Sign In button in the top-right corner."),
    ]
    category_tokens = count_message_tokens(messages)

    # ── 3. Persist the row exactly as brain.py's _fire_record does ────────────
    await record_llm_request(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        source="brain",
        category_tokens=category_tokens,
        input_tokens=usage["input"],
        output_tokens=usage["output"],
        cost_usd=usage["cost"],
        latency_ms=350,
        finish_reason="stop",
    )

    # ── 4. Assert the row was committed with the correct values ───────────────
    async with sqlite_session_factory() as session:
        rows = (
            await session.execute(
                select(LlmRequest).where(LlmRequest.user_id == user_id)
            )
        ).scalars().all()

    assert len(rows) == 1, "exactly one LlmRequest row should have been written"
    row = rows[0]

    assert row.input_tokens == 2500,  f"expected 2500 input_tokens, got {row.input_tokens}"
    assert row.output_tokens == 400,  f"expected 400 output_tokens, got {row.output_tokens}"
    assert row.total_tokens == 2900,  f"expected 2900 total_tokens, got {row.total_tokens}"
    assert row.cost_usd > 0,          f"cost_usd must be positive, got {row.cost_usd}"
    assert row.model == model
    assert row.source == "brain"
    assert row.chat_id == chat_id
    assert row.latency_ms == 350
    assert row.finish_reason == "stop"

    # Category breakdown must be non-zero (at least system + user buckets filled)
    assert row.system_tokens > 0,  "system prompt tokens must be tracked"
    assert row.user_tokens > 0,    "user message tokens must be tracked"
    assert row.history_tokens > 0, "history tokens must be tracked (prior AI + human turns)"


@pytest.mark.asyncio
async def test_record_llm_request_openrouter_format(sqlite_session_factory, monkeypatch):
    """Same end-to-end flow but via the OpenRouter / response_metadata path."""
    import src.database.chat_db as chat_db_module

    monkeypatch.setattr(chat_db_module, "AsyncSessionLocal", sqlite_session_factory)

    model = "google/gemini-3-flash-preview"
    user_id = str(uuid.uuid4())
    chat_id = f"thread-{uuid.uuid4()}"

    resp = _response_openrouter(prompt_tokens=1800, completion_tokens=250)
    usage = extract_token_usage(resp, model)
    assert usage["input"] == 1800
    assert usage["output"] == 250

    await record_llm_request(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        source="atag",
        category_tokens={},
        input_tokens=usage["input"],
        output_tokens=usage["output"],
        cost_usd=usage["cost"],
    )

    async with sqlite_session_factory() as session:
        rows = (
            await session.execute(
                select(LlmRequest).where(LlmRequest.user_id == user_id)
            )
        ).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.input_tokens == 1800
    assert row.output_tokens == 250
    assert row.total_tokens == 2050
    assert row.cost_usd > 0
    assert row.source == "atag"


@pytest.mark.asyncio
async def test_record_llm_request_is_nonfatal_on_db_error(monkeypatch):
    """record_llm_request must never raise even when the DB session factory fails."""
    import src.database.chat_db as chat_db_module

    async def _broken_session_factory():
        raise RuntimeError("simulated DB connection failure")

    class _BrokenFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise RuntimeError("simulated DB connection failure")

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr(chat_db_module, "AsyncSessionLocal", _BrokenFactory())

    # Must complete without raising
    await record_llm_request(
        user_id=str(uuid.uuid4()),
        chat_id="thread-test",
        model="google/gemini-3-flash-preview",
        source="brain",
        category_tokens={},
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
    )


@pytest.mark.asyncio
async def test_atag_run_script_generation_writes_llm_request_row(
    sqlite_session_factory, monkeypatch
):
    """
    Exercises the ATAG code path end-to-end:

      ATAGProcessor.run_script_generation
          → _meter() closure fires asyncio.ensure_future(record_llm_request(...))
          → LlmRequest row with source="atag" and cost_usd > 0 lands in DB

    This catches regressions where user_id is dropped or the ensure_future task
    silently swallows an error before the row is committed.
    """
    import src.database.chat_db as chat_db_module
    from src.services.ATAG import ATAGProcessor

    monkeypatch.setattr(chat_db_module, "AsyncSessionLocal", sqlite_session_factory)

    # ── 1. Mock LLM: returns valid Python content + usage_metadata ───────────
    _VALID_SCRIPT = (
        "import asyncio\n"
        "async def main():\n"
        "    pass\n"
    )

    class _MockLLM:
        model_name = "google/gemini-3-flash-preview"

        async def ainvoke(self, messages):
            return SimpleNamespace(
                usage_metadata={"input_tokens": 3000, "output_tokens": 500},
                response_metadata={},
                content=_VALID_SCRIPT,
            )

    # ── 2. Stub out Tavily enrichment and coder system prompt ─────────────────
    async def _stub_tavily_enrich(self, task_summary):
        return ""

    monkeypatch.setattr(ATAGProcessor, "_tavily_enrich", _stub_tavily_enrich)
    monkeypatch.setattr(
        ATAGProcessor,
        "_build_coder_system_prompt",
        lambda self, framework: "You are a coder.",
    )

    # ── 3. Stub DatabaseManager so the billing tail doesn't hit real Postgres ─
    class _NoOpDatabaseManager:
        async def log_agent_execution(self, **_kwargs):
            pass

        async def deduct_credits(self, *_args):
            pass

    monkeypatch.setattr(
        "src.services.brain.DatabaseManager",
        _NoOpDatabaseManager,
        raising=False,
    )

    # ── 4. Run script generation ──────────────────────────────────────────────
    user_id = str(uuid.uuid4())
    chat_id = f"thread-{uuid.uuid4()}"

    processor = ATAGProcessor(llm=_MockLLM(), tavily_api_key=None)
    script = await processor.run_script_generation(
        task_summary="Go to example.com and click Sign In",
        execution_history=[{"action": "navigate", "url": "https://example.com"}],
        framework="playwright",
        user_id=user_id,
        chat_id=chat_id,
    )

    assert script, "run_script_generation must return a non-empty script"

    # ── 5. Drain the event loop so ensure_future tasks complete ──────────────
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    # Extra yield in case record_llm_request spawns its own awaits internally
    for _ in range(5):
        await asyncio.sleep(0)

    # ── 6. Assert LlmRequest row exists with correct source and non-zero cost ─
    async with sqlite_session_factory() as session:
        rows = (
            await session.execute(
                select(LlmRequest).where(LlmRequest.user_id == user_id)
            )
        ).scalars().all()

    assert len(rows) >= 1, (
        f"expected at least one LlmRequest row for user {user_id}, got 0 — "
        "_meter's ensure_future may have dropped user_id or silently errored"
    )

    atag_rows = [r for r in rows if r.source == "atag"]
    assert atag_rows, (
        f"no rows with source='atag' found (sources present: {[r.source for r in rows]})"
    )

    row = atag_rows[0]
    assert row.cost_usd > 0, (
        f"cost_usd must be positive for an ATAG script-generation call, got {row.cost_usd}"
    )
    assert row.input_tokens == 3000, f"expected 3000 input_tokens, got {row.input_tokens}"
    assert row.output_tokens == 500, f"expected 500 output_tokens, got {row.output_tokens}"
    assert row.chat_id == chat_id


@pytest.mark.asyncio
async def test_multiple_llm_calls_produce_multiple_rows(sqlite_session_factory, monkeypatch):
    """
    Simulates what happens during a real browser run: multiple sequential LLM
    calls (brain turns + optional nudge) each produce their own LlmRequest row.
    """
    import src.database.chat_db as chat_db_module

    monkeypatch.setattr(chat_db_module, "AsyncSessionLocal", sqlite_session_factory)

    model = "google/gemini-3-flash-preview"
    user_id = str(uuid.uuid4())
    chat_id = f"thread-{uuid.uuid4()}"

    call_specs = [
        (800, 120, "brain"),         # first brain turn
        (820, 40, "brain_nudge"),    # nudge re-invoke (pending-action guard)
        (900, 200, "brain"),         # second brain turn
        (950, 180, "brain"),         # third brain turn (run completes)
    ]

    for inp, out, src in call_specs:
        resp = _response_usage_metadata(input_tokens=inp, output_tokens=out)
        usage = extract_token_usage(resp, model)
        await record_llm_request(
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            source=src,
            category_tokens={},
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            cost_usd=usage["cost"],
        )

    async with sqlite_session_factory() as session:
        rows = (
            await session.execute(
                select(LlmRequest).where(LlmRequest.user_id == user_id)
            )
        ).scalars().all()

    assert len(rows) == 4, f"expected one row per LLM call, got {len(rows)}"

    sources = [r.source for r in rows]
    assert sources.count("brain") == 3
    assert sources.count("brain_nudge") == 1

    total_input = sum(r.input_tokens for r in rows)
    total_output = sum(r.output_tokens for r in rows)
    assert total_input == 800 + 820 + 900 + 950
    assert total_output == 120 + 40 + 200 + 180

    for row in rows:
        assert row.cost_usd > 0, "every row must carry a positive cost_usd"
        assert row.total_tokens == row.input_tokens + row.output_tokens
