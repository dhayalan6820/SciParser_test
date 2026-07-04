---
name: MCP-only tool audits — what counts as a "tool"
description: How to scope an "every tool must come from the MCP registry" audit without over-reaching into unrelated helper functions.
---

When asked to make "all tools MCP-only" / remove non-MCP tool definitions, the boundary is:
a **tool** is anything exposed to the LLM as an invokable function via `bind_tools`,
`@tool`, or `StructuredTool` in the agent's ReAct/tool-calling loop. A plain internal
helper that calls a third-party API (e.g. a search SDK) to build prompt context —
never registered as an LLM-callable schema — is not a "tool" in this sense, even if
it shares a vendor name with a tool that was removed elsewhere in the codebase.

**Why:** SciParser had a standalone `@tool`-decorated Tavily wrapper bypassing MCP
(removed), *and* a separate, unrelated `ATAGProcessor._tavily_enrich` helper used only
to inject search context into a code-generation prompt (never bound as an LLM tool).
Only the former was in scope; conflating the two would have meant deleting a working,
unrelated feature.

**How to apply:** When auditing "no tool outside the MCP registry," grep for
`bind_tools`, `@tool`, `StructuredTool`, and the tool-loop's tool list — not just the
vendor/library name — to decide what's actually in scope.
