# Token-Efficient Context Management

## What & Why
Currently the agent sends the full raw content of every tool call (`ToolMessage`) and full agent-execution logs into the LangGraph `messages[]` list, which is replayed to the LLM on every single call. This balloons the token count rapidly — a 10-step browser run can easily send 50,000–200,000 input tokens per subsequent message. This rework changes the strategy so:
- Everything is stored in the DB (already true for agent/tool logs).
- The LLM only receives compact references instead of raw tool output blobs.
- Summarisation runs per-chat (not globally) when a token threshold is crossed.
- Scheduled task code generation pulls its context from DB records (linked to the triggering message), not from the growing LangGraph in-memory state.

## Done looks like
- Opening a long thread and sending a new message does NOT trigger 100k+ token input — typical context stays under 20k tokens for routine follow-up questions.
- History panel shows exactly the same agent + tool log detail as before (data is still stored in full in the DB; nothing is lost).
- When a chat's rolling context exceeds the threshold, a compact per-chat summary is auto-generated and stored; future calls load summary + recent messages only.
- Scheduling a task uses the DB-linked successful tool logs for that chat, not the in-memory `execution_history` from the LangGraph state.
- Token usage numbers reported in the UI drop measurably on repeated-message threads.

## Out of scope
- Changing the frontend history panel UI (already fixed separately).
- Cross-chat or global summarisation (summaries are strictly per `chat_id`).
- Changing the LLM model or provider.
- Modifying the browser screenshot stream or browser panel.

## Steps

1. **DB schema additions** — Add a `message_id` foreign-key column to both `AgentExecutionLog` and `ToolExecutionLog` so every agent stage and every tool call is linked to the `Message` row that triggered the run. Add a `ChatSummary` table (`chat_id`, `summary_text`, `covered_through_message_id`, `estimated_tokens`, `created_at`) to store per-chat compressed history. Run Alembic migration (or equivalent `CREATE TABLE` / `ALTER TABLE` calls via the existing DB setup).

2. **Write message_id when logging executions** — In `brain.py`, when the agent run starts, capture the `message_id` of the current user message. Pass it down into every `AgentExecutionLog.create()` and `ToolExecutionLog.create()` call so the FK is populated from the first run after migration.

3. **Compact ToolMessage content in LangGraph** — In `brain.py`'s `_call_tool` node, change what goes into `ToolMessage.content`: instead of the full `llm_observation` blob, write a compact one-liner: `"[tool_id: <id>] <tool_name> → SUCCESS | first 300 chars of result…"`. The complete output is already persisted to `ToolExecutionLog`; it does not need to be in the LangGraph messages list.

4. **Per-chat context builder** — Add a `_build_llm_context(chat_id, current_messages)` helper in `brain.py`. It: (a) estimates total tokens of `current_messages`; (b) if below threshold (40,000 tokens), returns them as-is; (c) if above threshold, calls a summariser against the DB records for this `chat_id` (agent logs + tool logs scoped to this chat only — not all logs), stores the result in `ChatSummary`, then returns `[SystemMessage(summary)] + last 8 raw messages`. Replace the existing 600k-token global compression trigger with this per-chat builder.

5. **Code generation pulls from DB** — In `ATAG.py`'s `run_script_generation`, replace the `execution_history` parameter (in-memory state) with a DB query: fetch all `ToolExecutionLog` rows for the given `chat_id` where `status = "COMPLETED"`, ordered by creation time. Summarise them (tool name + key input/output fields, capped at 500 chars each) and pass the summary as `tool_context`. This makes code gen consistent even after the in-memory state has been compressed or the session restarted.

## Relevant files
- `Backend/src/services/brain.py`
- `Backend/src/services/ATAG.py`
- `Backend/src/db/chat_db.py`
- `Backend/src/models/chat_models.py`
