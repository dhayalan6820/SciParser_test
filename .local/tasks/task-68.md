---
title: Agent remembers what it did in previous messages
---
# Agent Multi-Turn Memory

## What & Why
When a user sends a second message in the same chat, the agent starts completely from scratch — re-navigating to the same URL, redoing steps it already completed. This happens because the mission-generation prompt has no knowledge of what was previously accomplished, and there is a bug in how the "current task context" is injected into the LangGraph message chain.

Three root causes identified in the code:

**Root cause 1 — `PROMPT_2_EXECUTION_GENERATOR` is stateless:**
`run_execution_generation` receives only `task_summary`, `confirmed_inputs`, and `target_info`. It has no knowledge of the current browser state (what page we are on, what has already been done). Every invocation generates "open browser, navigate to X, log in, do Y, do Z" from scratch.

**Root cause 2 — `dynamic_context` is injected into the wrong message:**
In `call_model` (brain.py ~line 833), the current task context is prepended to `raw_messages[0]` — the OLDEST accumulated message — instead of the NEWEST one. On a second user message, this overwrites the first message with the new task's context while the new mission objective sits unmodified at the end, creating contradictory task instructions.

**Root cause 3 — No persisted "where we left off" state:**
After execution completes, the browser state (current URL, accomplished steps) exists only in LangGraph's in-memory `MemorySaver`. If the server restarts between messages, or if there are multiple server instances, that context is lost entirely.

## Done looks like
- User sends message 1: "Go to amazon.com and search for laptops" → agent does it, lands on search results
- User sends message 2: "Now filter by brand Dell" → agent CONTINUES from the search results page, does not re-navigate to amazon.com or re-search
- User sends message 3: "Add the cheapest one to my cart" → agent continues from the filtered results, does not restart
- Agent's mission for each follow-up message references what was already accomplished ("currently on Amazon search results for 'laptops'") and only describes the new action

## Out of scope
- Full LangGraph-level message deduplication or state compression
- Cross-session memory (different chat threads)

## Steps

1. **Add `session_state` column to `ChatSession`** — Add a nullable text column `session_state` to the `ChatSession` model and run an Alembic migration (or `CREATE TABLE IF NOT EXISTS` equivalent). This field will store a JSON blob: `{ "last_url": "...", "accomplishment_summary": "...", "ts": <unix timestamp> }`.

2. **Save session state after each execution** — After `_execute_tool_graph` completes successfully in `process_message` (brain.py ~line 1344-1358), extract a brief summary from `graph_output["execution_history"]` — the last known URL from tool results and a 2-3 sentence accomplishment summary — and persist it to `session_state` on the `ChatSession` row for this `chat_id`.

3. **Load and pass session state into `run_input_understanding`** — At the start of `process_message` (brain.py ~line 1205), read `session.session_state` from the DB and append it to `history_context` so the ATAG analysis stage knows the current browser state when interpreting the new message.

4. **Pass session state into `run_execution_generation`** — Add a `prior_context` parameter to `run_execution_generation` (ATAG.py line 375) and add a `{prior_context}` slot to `PROMPT_2_EXECUTION_GENERATOR`. When `session_state` is available, populate it with: `"CURRENT BROWSER STATE: {accomplishment_summary}. Currently on: {last_url}. The agent MUST continue from this state and NOT redo already-completed steps."` When no prior state exists, this slot is empty.

5. **Fix `dynamic_context` injection to target the latest message** — In `call_model` (brain.py ~line 832), change the injection logic so the task context is prepended to the LAST HumanMessage in `raw_messages`, not `raw_messages[0]`. This ensures the current task description is adjacent to the new mission objective and not mixed into the oldest accumulated message.

## Relevant files
- `Backend/src/services/brain.py:790-870`
- `Backend/src/services/brain.py:1160-1360`
- `Backend/src/services/ATAG.py:207-245`
- `Backend/src/services/ATAG.py:375-390`
- `Backend/src/schemas/schema.py`
- `Backend/src/database/models.py`