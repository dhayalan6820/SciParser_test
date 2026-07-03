"""Regression test for the "create schedule silently gets no tool data" bug.

Root cause: ToolExecutionLog.id is a server-generated UUID (see
`Backend/src/database/chat_db.py`), assigned only when the row is persisted
in `Brain._call_tool` after the tool finishes executing. That value is
independent of `tool_call["id"]` (the LLM-issued tool_call_id used purely to
correlate the `tool_start`/`tool_output` websocket stream events for the live
browser-preview UI).

The frontend's tool-selection checkboxes (chat_page.tsx) keyed each ToolLog
entry by the *stream* tool_call_id. When a user selected a tool from that
live stream and created a schedule, `selected_tool_ids` sent to
`/scheduler/create` held tool_call_ids that matched NO row in
`tool_execution_logs`, so `execution_history` came back empty and the
generated schedule silently had no tool data.

Fix: `Brain._call_tool` now returns the real DB id from
`log_tool_execution(...)` and includes it as `db_id` on the `tool_output`
stream event so the frontend can reconcile its selection state to the actual
persisted row id.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import inspect

from src.services.brain import Brain


def test_call_tool_source_captures_db_log_id_from_log_tool_execution():
    """Static audit: the tool_output event must be built from the value
    returned by log_tool_execution (the real DB primary key), not just the
    LLM tool_call_id — otherwise the frontend has no way to reconcile.

    `_call_tool` is a nested function defined inside a graph-building method,
    so it isn't reachable as a standalone attribute; assert against the
    module source instead of trying to isolate the nested function object.
    """
    import src.services.brain as brain_module
    module_source = inspect.getsource(brain_module)

    assert "_db_log_id = await self.db_manager.log_tool_execution(" in module_source, (
        "log_tool_execution's return value must be captured so the real DB "
        "id can be surfaced to the frontend."
    )
    assert '"db_id": _db_log_id' in module_source, (
        "tool_output stream event must include the real ToolExecutionLog.id "
        "as db_id, or the frontend tool-selection UI keeps using the "
        "stream-only tool_call_id, which matches nothing in the DB."
    )


def test_log_tool_execution_returns_the_persisted_row_id():
    """log_tool_execution must return log.id (not None) so callers can use
    it — this is the value that becomes `db_id` on the tool_output event."""
    from src.services.brain import DatabaseManager

    source = inspect.getsource(DatabaseManager.log_tool_execution)
    assert "return log.id" in source
