"""Regression test: token_usage/cost must be persisted to AgentExecutionLog
for every LLM call, including calls that return only a tool call with empty
`response.content`.

Root cause of the original bug: in `Brain.call_model` (src/services/brain.py),
the `update_ui_func(...)` call that persists `token_usage`/`cost` via
`log_agent_execution` lived inside the `if response.content:` /
`if clean_content:` branches used only for broadcasting the model's "thinking"
text to the UI. Many real LLM turns return a tool call with empty/no content,
so those calls' token usage never reached `AgentExecutionLog`, silently
undercounting usage/cost for any reporting built on that table.

Fix: `update_ui_func` (which persists token_usage/cost) is now called
unconditionally once per `call_model` invocation, independent of whether the
model produced any content to broadcast.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import inspect


def test_update_ui_func_called_unconditionally_for_token_usage_logging():
    import src.services.brain as brain_module
    source = inspect.getsource(brain_module)

    call_model_start = source.index("async def call_model(state: AgentState):")
    call_tool_start = source.index("async def _call_tool(state: AgentState):", call_model_start)
    call_model_source = source[call_model_start:call_tool_start]

    assert "if response.content:" in call_model_source, (
        "expected the content-broadcast branch to still exist"
    )

    # The token_usage/cost-persisting update_ui_func(...) call must sit AFTER
    # (not nested inside) the `if response.content:` broadcast branch, so it
    # fires unconditionally for every LLM call in call_model — including
    # tool-call-only responses with empty content.
    broadcast_branch_start = call_model_source.index("if response.content:")
    broadcast_branch_end = call_model_source.index(
        'await self.stream_manager.broadcast_thought(chat_id, thought_text)', broadcast_branch_start
    )
    return_stmt_idx = call_model_source.index('return {"messages": [response]}')
    update_ui_call_idx = call_model_source.index("await update_ui_func(1,")

    assert broadcast_branch_end < update_ui_call_idx < return_stmt_idx, (
        "update_ui_func(...) that persists token_usage/cost to "
        "AgentExecutionLog must be called after the `if response.content:` "
        "broadcast branch (not nested inside it) and before call_model "
        "returns, or tool-call-only responses (empty content) will silently "
        "skip AgentExecutionLog persistence again."
    )

    # Guard against the call being re-nested inside `if response.content:` /
    # `if clean_content:` by requiring it to appear in a standalone
    # `if update_ui_func:` guard rather than the content-cleanup block.
    between = call_model_source[broadcast_branch_end:update_ui_call_idx]
    assert "if update_ui_func:" in between, (
        "expected update_ui_func(...) to be guarded only by `if "
        "update_ui_func:`, independent of response.content"
    )
