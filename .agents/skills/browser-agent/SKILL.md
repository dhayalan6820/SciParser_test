---
name: browser-agent
description: >
  Core browser execution agent — the LangGraph ReAct loop in brain.py that
  receives MCP tool calls, executes them via Playwright/CDP, and drives
  multi-turn browser automation with observation-action cycles.
---

## What It Does

The Browser Agent is Agent 3 in the pipeline — the one that actually operates the browser.
It runs as a LangGraph `StateGraph` with two nodes (`call_model` → `_call_tool` → loop)
inside `Brain._execute_browser_agent()`. The LLM decides which MCP tool to call, the tool
executes against the live browser, and the observation is fed back for the next decision.

## Runtime Files

- **Agent Spec**: [browser.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/browser.agent.md)
  — System prompt sections: Backstory, Reasoning Format, Stealth Behavior, Observation Rules,
  Overlay & Popup Handling, Form Handling, Error Recovery, Completion/Failure Rules, Safety Rules,
  Recovery Protocol, Page Analysis.
- **Orchestrator**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — `Brain` class, `_execute_browser_agent()`, `call_model()`, `_call_tool()`.
- **Stage loader**: [spec_loader.py](file:///d:/Project/SciParser/Backend/src/agents/spec_loader.py)
  — `build_system_prompt(spec, stage=...)` selects only relevant sections per stage (plan/execute/recover).

## How It's Activated

Every browser task flows through this agent after Agent 1 (Analysis) returns `READY`.
The LangGraph graph is compiled fresh per run inside `_execute_browser_agent()`.

## Key Patterns

- **Stage-scoped system prompts**: The system message changes between `plan`, `execute`, and
  `recover` stages — only relevant spec sections are included per stage (see `_STAGE_SECTION_MAP`
  in `spec_loader.py`). This keeps the prompt small and enables provider prefix caching.
- **Observation compression**: Raw tool outputs are compressed via `_compress_observation_for_llm()`
  before entering LLM history (max 12,000 chars, duplicate line removal).
- **Tool message collapse**: Older tool messages are replaced with a short placeholder after
  `NUM_RECENT_TOOL_MESSAGES_TO_KEEP_FULL` (6) to prevent prompt bloat.
- **Nudge re-invocation**: If the LLM writes "I will now X" without a tool call, it's
  re-invoked with a nudge message to emit the actual tool call.

## Common Issues

- **Token bloat**: Large page dumps accumulate across turns. The `SUMMARIZE_HISTORY_TOKEN_THRESHOLD`
  (60,000 tokens) triggers history summarization. If runs are expensive, check this threshold.
- **Navigation cooldown**: After 3 consecutive failures on one domain, navigation is blocked
  for 60s (`MAX_NAV_FAILURES`, `NAV_COOLDOWN_SECONDS`).
- **Prefix cache invalidation**: Never mutate an earlier message's content — append new context
  as a trailing `HumanMessage` instead (see `.agents/memory/mutating-message-breaks-prefix-cache.md`).
