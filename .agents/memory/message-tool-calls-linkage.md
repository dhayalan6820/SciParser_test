---
name: AI message to tool log linkage
description: How to correctly link an AI chat message to the tool runs used to produce it, for auto-selecting tools when scheduling a message.
---

When a graph/tool-execution flow logs a tool run to a DB table (e.g. `ToolExecutionLog`) AND separately builds an in-memory/JSON summary of the same tool calls to persist elsewhere (e.g. `Message.tool_calls`), both must reference the exact same real primary key. Do not mint a fresh `uuid4()` for the second copy — it silently disconnects the two records and any UI/feature that tries to join them later (e.g. "look up the tool logs used by this message") will find nothing.

**Why:** This exact bug happened here — `_call_tool` logged tools with a real DB id, but the later step that saved `Message.tool_calls` generated a brand new uuid per entry instead of reusing the id from the earlier step. It silently broke a feature (auto-including tool data when scheduling a message) that looked correct in code review but produced empty results at runtime.

**How to apply:** When persisting a per-step summary/history structure (e.g. `execution_history` list) that will later be re-packaged into a different persisted record, thread the real DB id through the intermediate structure end-to-end and reuse it — never regenerate an id at each hop. When adding a new field to an API response model in FastAPI (e.g. Pydantic `response_model`), the field must be explicitly declared on the schema or it gets silently stripped even if the underlying dict has the data.

**Product decision:** For scheduling chat tasks in SciParser, tool selection is fully automatic and derived from which chat message(s) the user selects — no manual "select tool runs" checkbox UI exists anywhere (removed twice after user pushback). The main chat page shows only user input / AI response selection; the tools list itself is only ever shown inside the scheduler dialog's "MCP Tools" tab.
