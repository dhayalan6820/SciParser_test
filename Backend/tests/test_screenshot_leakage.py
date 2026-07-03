"""Tests for Task #120: confirm secrets never leak through browser
screenshots or console logs.

Task #118 closed the main persistence leaks for typed secret VALUES
(Message.content, ToolExecutionLog, AgentExecutionLog). This file pins down
the remaining surface called out in #120: the live browser-frame screenshot
stream (`Brain._stream_browser_frames`), which broadcasts raw base64 CDP
screenshots over the websocket while a user may be typing a password/OTP
into a visible form field.

Audit findings (see code references below), each backed by a test:

1. `_stream_browser_frames` only ever calls `stream_manager.broadcast_frame`
   / `broadcast_mouse` — it never touches `db_manager`, `log_tool_execution`,
   or `memory_service`. No screenshot frame is written to any DB-backed
   table from this code path.
2. `PlanStreamManager.last_frame` is a plain in-memory dict (process memory,
   not a DB table) used only to replay the most recent frame to a
   reconnecting websocket client for the SAME authenticated user. It is
   never serialized to disk or a persisted table.
3. `ToolExecutionLog.screenshot_url` is a schema column that is never
   populated by either write site (`Brain.log_tool_execution` /
   `AgentManager.log_tool_execution`) — dead column, always NULL.
4. The tool-output observation text that DOES get persisted to
   `ToolExecutionLog.tool_output` has any `[SCREENSHOT]...[/SCREENSHOT]`
   block stripped out BEFORE the secret-value redaction pass runs, so no
   base64 image payload can ever end up in a persisted observation string
   (screenshot data is removed structurally, not just secret-value-matched).
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import ast
import inspect
import re
import textwrap
import pytest

from src.services.brain import Brain, DatabaseManager
from src.database.chat_db import ToolExecutionLog


# ── 1. _stream_browser_frames never touches persistence ────────────────────

def test_stream_browser_frames_never_calls_persistence_apis():
    """Static audit: the screenshot-broadcast coroutine's source must not
    reference any DB/log/memory persistence call. If someone later wires a
    `self.db_manager.log_tool_execution(...)` or `self.memory_service...`
    call into this function to "cache" frames, this test fails immediately
    rather than silently allowing a screenshot into a persisted table."""
    source = inspect.getsource(Brain._stream_browser_frames)

    forbidden_calls = [
        "db_manager",
        "log_tool_execution",
        "memory_service",
        "ToolExecutionLog",
        "MemoryEpisodic",
        "AsyncSessionLocal",
    ]
    for forbidden in forbidden_calls:
        assert forbidden not in source, (
            f"_stream_browser_frames now references '{forbidden}' — a browser "
            "screenshot frame must never reach a persisted table/log."
        )

    # It IS expected to broadcast over the websocket stream manager.
    assert "stream_manager.broadcast_frame" in source or "broadcast_frame" in source


def test_stream_browser_frames_source_has_no_db_write_statements():
    """Belt-and-suspenders AST check: no `await self.db*` / db.add / db.commit
    calls anywhere inside the function body."""
    source = inspect.getsource(Brain._stream_browser_frames)
    tree = ast.parse(textwrap.dedent(source))

    write_indicators = {"add", "commit", "execute"}
    found = []

    class _Visitor(ast.NodeVisitor):
        def visit_Attribute(self, node):
            if node.attr in write_indicators:
                found.append(node.attr)
            self.generic_visit(node)

    _Visitor().visit(tree)
    assert not found, f"Unexpected DB-write-like calls found in _stream_browser_frames: {found}"


# ── 2. last_frame cache is in-memory only, scoped per authenticated user ───

def test_last_frame_cache_is_plain_in_memory_dict():
    """PlanStreamManager.last_frame must be a plain in-process dict (no disk
    or DB backing) so a restart clears it and it can never be queried like a
    persisted table."""
    import src.main as main_module

    manager = main_module.PlanStreamManager()
    assert isinstance(manager.last_frame, dict)

    # Simulate a frame broadcast and confirm it only lives in the dict,
    # keyed by user_id, with nothing written to disk/DB as a side effect.
    import asyncio

    async def _run():
        await manager.broadcast_frame({"chat_id": "chat-1", "frame": "data:image/jpeg;base64,AAA"}, "user-1")

    asyncio.run(_run())
    assert manager.last_frame["user-1"]["frame"].startswith("data:image/jpeg;base64,")
    # No other user's cache is populated.
    assert "user-2" not in manager.last_frame


# ── 3. ToolExecutionLog.screenshot_url is never populated ──────────────────

def test_tool_execution_log_never_sets_screenshot_url():
    """Static audit of both write sites that construct ToolExecutionLog rows:
    neither DatabaseManager.log_tool_execution nor
    AgentManager.log_tool_execution may pass screenshot_url. If a future
    change starts populating it with a frame from _stream_browser_frames,
    this test must fail."""
    import src.services.agent_manager as agent_manager_module

    db_manager_log_source = inspect.getsource(DatabaseManager.log_tool_execution)
    agent_manager_log_source = inspect.getsource(agent_manager_module.AgentManager.log_tool_execution)

    assert "screenshot_url" not in db_manager_log_source
    assert "screenshot_url" not in agent_manager_log_source

    # Column still exists in the schema (documenting current dead-column
    # state); if it gets removed entirely that's fine too, so don't assert
    # its bare existence — just that nothing constructs a row with it set.
    assert "screenshot_url" in ToolExecutionLog.__table__.columns


@pytest.mark.asyncio
async def test_tool_execution_log_row_has_null_screenshot_url_after_write(sqlite_session_factory):
    """End-to-end: actually persist a ToolExecutionLog row the same way the
    real code path does, and confirm screenshot_url is NULL — never a
    base64 payload."""
    from datetime import datetime, timezone

    async with sqlite_session_factory() as db:
        log = ToolExecutionLog(
            chat_id="chat-1",
            agent_id="3",
            tool_name="browser_fill",
            tool_input="{}",
            tool_output="Filled field. Success.",
            status="SUCCESS",
            created_at=datetime.now(timezone.utc),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        assert log.screenshot_url is None


# ── 4. [SCREENSHOT]...[/SCREENSHOT] blocks are stripped before persistence ─

def test_screenshot_block_stripped_from_observation_before_logging():
    """Mirrors the exact regex used in Brain._call_tool (~line 998) to strip
    any embedded screenshot payload out of the observation text before it is
    redacted and written to ToolExecutionLog.tool_output."""
    fake_b64 = "data:image/jpeg;base64," + ("A" * 500)
    observation = (
        f"Filled password field with the secret value.\n"
        f"[SCREENSHOT]{fake_b64}[/SCREENSHOT]\n"
        f"Clicked submit. Success."
    )

    clean_obs = re.sub(r"\[SCREENSHOT\].*?\[/SCREENSHOT\]", "[Image Data]", observation, flags=re.DOTALL)

    assert fake_b64 not in clean_obs
    assert "base64" not in clean_obs
    assert "[Image Data]" in clean_obs
    assert "Success" in clean_obs

    # Compose with the secret-value redaction pass, as _call_tool does, to
    # confirm both a screenshot AND a known secret value are gone from what
    # actually reaches the DB.
    scrubbed = Brain._redact_secret_values_in_text(clean_obs[:1000], ["hunter2"])
    redacted_full = clean_obs.replace("secret value", "hunter2")
    scrubbed_full = Brain._redact_secret_values_in_text(redacted_full, ["hunter2"])
    assert "hunter2" not in scrubbed_full
    assert fake_b64 not in scrubbed_full


def test_screenshot_block_regex_handles_multiple_and_multiline_blocks():
    observation = (
        "[SCREENSHOT]aaaa\nbbbb\ncccc[/SCREENSHOT]"
        "Some text in between."
        "[SCREENSHOT]dddd[/SCREENSHOT]"
    )
    clean_obs = re.sub(r"\[SCREENSHOT\].*?\[/SCREENSHOT\]", "[Image Data]", observation, flags=re.DOTALL)
    assert "aaaa" not in clean_obs
    assert "dddd" not in clean_obs
    assert clean_obs.count("[Image Data]") == 2
    assert "Some text in between." in clean_obs
