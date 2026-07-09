# Objective
Add Ollama, NVIDIA, and Groq LLM provider support to the Settings page, admin-only access.

## Design
All three providers support the OpenAI API format, so we use `ChatOpenAI` with different `base_url` values. This avoids installing new LangChain packages. The global `brain` singleton gets per-user LLM overrides.

## Tasks

### T001: Backend — DB schema, migration, Pydantic schemas
- **Blocked By**: []
- **Details**:
  - Add `llm_provider`, `llm_model`, `llm_api_key`, `llm_base_url` to `User` model in `chat_db.py`
  - Add raw SQL migration in `init_db.py` (IF NOT EXISTS pattern)
  - Add Pydantic schemas in `schema.py`

### T002: Backend — Admin-only settings endpoints
- **Blocked By**: [T001]
- **Details**:
  - `GET /sciparser/v1/settings/llm-provider` — returns masked config (admin only)
  - `POST /sciparser/v1/settings/llm-provider` — saves provider + model + api_key + base_url (admin only)
  - `DELETE /sciparser/v1/settings/llm-provider` — resets to default (admin only)

### T003: Backend — Per-user LLM factory in brain.py
- **Blocked By**: [T001]
- **Details**:
  - Add `_build_user_llm(user_id)` async method in Brain class
  - Modify `process_message()` to use per-user LLM
  - Modify `_execute_tool_graph()` to accept optional `custom_llm`
  - Update ATAGProcessor usage to also use per-user LLM

### T004: Frontend — API layer
- **Blocked By**: []
- **Details**:
  - Add `getLlmProvider`, `setLlmProvider`, `deleteLlmProvider` to `api.ts`

### T005: Frontend — Settings page LLM Provider section (admin-only)
- **Blocked By**: [T004]
- **Details**:
  - Add admin-gated LLM Provider section to `settings-page.tsx`
  - Provider selector cards (OpenRouter default, Groq, NVIDIA, Ollama)
  - API key input with show/hide toggle
  - Model name input
  - Base URL input (for Ollama, optional)
  - Save/Test/Remove buttons with status feedback

### T006: Verification
- **Blocked By**: [T002, T003, T005]
- **Details**:
  - Run backend tests
  - Verify frontend builds cleanly
  - Restart workflows
