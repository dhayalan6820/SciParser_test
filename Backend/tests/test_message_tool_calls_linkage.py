"""Regression test for automatic tool inclusion when scheduling a chat message.

Product requirement: when a user selects a chat message to schedule, the
tool(s) used to produce that AI response must be included automatically —
no manual "select tool runs" checkbox UI.

Root cause of the original bug: `Message.tool_calls` (see
`Backend/src/database/chat_db.py`) is meant to link an AI message to the
tools used to produce it, but `_execute_tool_graph`'s graph-output handling
built each `all_tool_calls` entry with a freshly generated `uuid.uuid4()`
id, disconnected from the real `ToolExecutionLog.id` created in `_call_tool`.
That meant a message's `tool_calls` could never be used to look up real
tool logs for auto-selection.

Fix:
1. `_call_tool` now carries the real `_db_log_id` through each
   `execution_history` entry (as `"id"`).
2. The `all_tool_calls.append(...)` block reuses that real id
   (`entry.get("id")`) instead of always minting a new uuid4.
3. `ChatService.get_chat_history` and the `process_message` response both
   expose `tool_calls` on each AI message so the frontend can auto-derive
   tool selection from selected messages.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import inspect


def test_execution_history_entries_carry_the_real_db_log_id():
    import src.services.brain as brain_module
    module_source = inspect.getsource(brain_module)

    assert (
        'execution_history.append({' in module_source
        and '"tool": tool_call["name"],' in module_source
        and '"status": status,' in module_source
        and '"result": llm_observation[:500],' in module_source
        and '"id": _db_log_id,' in module_source
    ), (
        "execution_history entries must carry the real ToolExecutionLog.id "
        "(_db_log_id), or Message.tool_calls can never be linked back to a "
        "persisted tool log."
    )


def test_all_tool_calls_reuse_real_execution_history_id_instead_of_fresh_uuid():
    import src.services.brain as brain_module
    module_source = inspect.getsource(brain_module)

    assert '"id": entry.get("id") or str(uuid.uuid4())' in module_source, (
        "all_tool_calls (persisted to Message.tool_calls) must reuse the "
        "real db id captured in execution_history, only falling back to a "
        "fresh uuid4 when it's genuinely missing. Always minting a new "
        "uuid4 disconnects the message from any real ToolExecutionLog row."
    )


def test_process_message_response_exposes_tool_calls_on_the_ai_message():
    import src.services.brain as brain_module
    module_source = inspect.getsource(brain_module)

    assert '"tool_calls": all_tool_calls,' in module_source, (
        "The live process_message response message dict must expose "
        "tool_calls so the frontend can auto-derive tool selection "
        "immediately, without needing a full chat history reload."
    )


def test_chat_history_endpoint_exposes_tool_calls_per_message():
    import src.services.chat_service as chat_service_module

    source = inspect.getsource(chat_service_module.ChatService.get_chat_history)
    assert '"tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else []' in source, (
        "get_chat_history must return each message's tool_calls (parsed "
        "from Message.tool_calls) so a reloaded chat still supports "
        "automatic tool selection when a message is selected for scheduling."
    )


def test_backend_chat_message_schema_declares_tool_calls_field():
    from src.schemas.schema import BackendChatMessage

    assert "tool_calls" in BackendChatMessage.model_fields, (
        "BackendChatMessage must declare tool_calls or FastAPI's "
        "response_model will silently strip it from API responses."
    )
