---
title: Token instrumentation & data layer
---
# Token Instrumentation & Data Layer

## What & Why
Every LLM call currently records zero tokens because `LangChainChatModelWrapper.ainvoke()` returns mocked usage (`prompt_tokens=0, completion_tokens=0`). This makes all token analytics meaningless. The fix is to: (1) read real token counts from the Gemini API response, (2) categorise those tokens by message type before each call (system / user / history / memory / tool / RAG), and (3) persist everything in a new structured `llm_requests` table so downstream dashboards have real data to display.

## Done looks like
- Every LLM call stores real `input_tokens` and `output_tokens` from the API response (no more zeros)
- Each `llm_requests` row has separate columns for `system_tokens`, `user_tokens`, `history_tokens`, `memory_tokens`, `tool_tokens`, `rag_tokens`, `cached_tokens`, `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `model`, `finish_reason`, `chat_id`, `user_id`, `source` (which call site: brain/chat/atag), `created_at`
- Token counts per category are estimated by counting the tokens in each message role/type before the call is sent (tiktoken or character-based approximation is fine; the LLM response gives the authoritative input/output totals)
- Alembic migration creates the `llm_requests` table with indexes on `(user_id, created_at)` and `(chat_id, created_at)`
- `agent_execution_logs.token_usage` and `messages.token_usage` are still populated as before (no breaking changes), but now with real numbers derived from the instrumentation layer
- Cost is calculated using a hardcoded rate constant (e.g. Gemini Flash: $0.075 / 1M input, $0.30 / 1M output) defined in one place in `config.py` so it is easy to update later

## Out of scope
- Dynamic pricing DB table (hardcoded rate in config only)
- UI changes (handled in a later task)
- OpenTelemetry / Prometheus / external observability
- Image / audio / video token tracking

## Steps
1. **Fix `LangChainChatModelWrapper.ainvoke()`** — After calling `self.langchain_llm.ainvoke()`, read token counts from `response.response_metadata` (LangChain/Gemini stores `usage_metadata` or `token_usage` there) and populate the real `ChatInvokeUsage` fields instead of zeros. Handle the case where the metadata is absent gracefully (fall back to zero rather than crash).
2. **Add token-category pre-counting helper** — Before each LLM call in the three call sites (brain.py, chat_service.py, ATAG.py), walk the message list and bin each message into a category (system, user, history, memory, tool, rag) by inspecting role and content markers. Count tokens using `len(content) // 4` as a fast approximation (close enough for analytics; exact totals come from the API).
3. **Create `llm_requests` SQLAlchemy model and Alembic migration** — Add the new table with all the columns listed above. Index on `(user_id, created_at)` and `(chat_id, created_at)`. Soft-delete (`deleted_at`) column included.
4. **Wire instrumentation into call sites** — At each of the three call sites (brain.py LLM invocations, chat_service.py chat completions, ATAG.py script generation), after the LLM returns, write one `llm_requests` row using the real usage data plus the pre-counted category estimates. Do this in a `try/except` so a DB write failure never breaks the agent run.
5. **Backfill `agent_execution_logs` and `messages` with real numbers** — Update the existing code that writes `token_usage` JSON blobs so it pulls from the real response metadata rather than relying on whatever was there before.
6. **Add hardcoded pricing constants to config** — Define `LLM_INPUT_COST_PER_MILLION` and `LLM_OUTPUT_COST_PER_MILLION` in `config.py` and use them in the cost calculation written to `llm_requests.cost_usd`.

## Relevant files
- `Backend/src/utils/llm_wrapper.py`
- `Backend/src/services/brain.py`
- `Backend/src/services/chat_service.py`
- `Backend/src/services/ATAG.py`
- `Backend/src/database/chat_db.py`
- `Backend/src/config.py`