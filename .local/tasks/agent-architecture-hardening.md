# Agent Architecture Hardening (MCP-only tools, Verifier, Observer, Recovery tree, Config/State schemas, Stage-based prompt loading)

## What & Why
The browser-automation agent (`Backend/src/agents/`, `Backend/src/services/brain.py`) has a tool that bypasses the MCP registry, no explicit per-action verification, no structured observation step, only partial recovery branching, and no formal config/state/tools/workflow schemas. This task closes those gaps so all tools are sourced from MCP, actions are verified immediately after execution, page state is observed in a structured way, recovery covers more failure categories, and operational settings/state/tool contracts are documented and machine-consumable — while keeping behavior (agent.md-style specs) separate from operational config (config.json/tools.json/workflows.json).

## Done looks like
- No tool definitions outside the MCP registry; any tool the agent can call is discoverable via `mcp_servers.json` / the MCP client, with no local `@tool`/`StructuredTool` shortcuts left in the codebase.
- After every tool call, an explicit verification check confirms the action's expected effect occurred before the next planning step runs, and a `validation_result` is available to the planner/critic.
- A structured observation step runs each turn, producing a state object (elements, loading/modal/captcha/login/error flags) that obstacle detection and planning read instead of regex over raw text.
- Recovery has distinct branches for timeout, browser crash, session expired, unexpected redirect, wrong page, permission denied, and element missing, in addition to the existing CAPTCHA/OTP/generic-critic paths.
- `config.json` and `state.json` schemas exist, documenting model/temperature/max tokens/timeouts/retry limits/browser config, and the runtime state fields (current_url, current_goal, browser_status, execution_time, validation_result, etc.), backed by the existing env/config plumbing.
- `tools.json` documents the MCP-sourced tool contracts (description, parameters, validation, error codes, rate limits/permissions) as a reviewable artifact, and `workflows.json` documents the Observe → Plan → Execute → Verify → Recover → Complete loop as an explicit task-graph/state-transition document.
- Prompt assembly loads only the spec sections relevant to the active stage (Plan/Execute/Observe/Verify/Recover) instead of one full prompt per agent type regardless of stage.
- Full backend test suite passes, plus a live multi-step browser automation run demonstrating: MCP-only tool usage, an observed verification catching a bad action, and no regression in task success or token usage versus the current baseline.

## Out of scope
- Adding brand-new tool capabilities (e.g. real web search) — only fixing the sourcing pattern for whatever tools exist today.
- Changing the underlying browser engine or MCP transport.
- UI/dashboard changes.

## Steps
1. **Remove non-MCP tool** — Delete or properly re-route the standalone Tavily tool so every callable tool is sourced via the MCP registry; audit for any other non-MCP tool definitions and fix them the same way.
2. **Structured Observer step** — Add an explicit per-turn observation step producing a structured state object, and switch obstacle detection to read from it instead of raw-text regex.
3. **Per-action Verifier step** — Add an explicit post-action verification check that confirms the expected effect of the last tool call and surfaces a validation result to the planning/critic logic.
4. **Expanded recovery decision tree** — Add distinct recovery branches for the additional failure categories (timeout, crash, session expiry, redirect, wrong page, permission denied, missing element), documented as `recovery.md`.
5. **Config/state/tools/workflow schemas** — Introduce `config.json`, `state.json`, `tools.json`, and `workflows.json` as documented, reviewable artifacts consistent with the existing env config and LangGraph state, without duplicating or conflicting with them.
6. **Stage-based spec loading** — Update prompt assembly so each stage loads only its relevant spec sections plus the new config schema, building on the existing token-reduction work.
7. **Verification** — Run the full backend test suite and one live multi-step automation run confirming MCP-only tool usage, working verifier/observer/recovery behavior, and no regression in success rate or token usage.

## Relevant files
- `Backend/src/agents/tavily_agent.py`
- `Backend/src/agents/mcp_agent.py`
- `Backend/src/agents/mcp_servers.example.json`
- `Backend/src/agents/spec_loader.py`
- `Backend/src/agents/specs/browser.agent.md`
- `Backend/src/agents/specs/planner.agent.md`
- `Backend/src/services/brain.py`
- `Backend/src/services/obstacle_handler.py`
- `Backend/src/services/memory_service.py`
- `Backend/src/config.py`
- `Backend/src/agents/ATAG.py`
