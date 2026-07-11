# SciParser AI — Project Rules

## Architecture Overview

SciParser AI is a multi-agent browser automation system. Understanding the agent pipeline
is critical before modifying any component.

### Agent Pipeline (request lifecycle)

```
User Message
    │
    ▼
Agent 1: Input Understanding (planner.agent.md → ATAG.py)
    │  Classifies intent, extracts confirmed_inputs, decides READY vs NEEDS_INPUT
    │
    ▼
Agent 2: Mission Planning (planner.agent.md → ATAG.py)
    │  Generates numbered MISSION OBJECTIVE for the Browser agent
    │
    ▼
Agent 3: Browser Execution (browser.agent.md → brain.py LangGraph loop)
    │  Executes MCP tool calls in a ReAct loop with per-observation detectors:
    │
    │  ┌─ Observer (observer.py) ─── parses raw observation → ObservedState
    │  ├─ CAPTCHA detector (obstacle_handler.py)
    │  ├─ Address agent (address_agent.py) ─── only if address in confirmed_inputs
    │  ├─ Calendar agent (calendar_agent.py) ─── only if date in confirmed_inputs
    │  ├─ Login agent (login_agent.py) ─── only if credentials in confirmed_inputs
    │  ├─ Booking agent (booking_agent.py) ─── only if multi-step flow detected
    │  ├─ Aggregator agent (aggregator_agent.py) ─── only if extraction task
    │  ├─ Verifier (verifier.py) ─── checks if action had expected effect
    │  └─ Recovery classifier (recovery.py) ─── pre-classifies failures
    │
    ▼
Result → streamed to frontend via WebSocket
```

### File Organization

```
Backend/src/
├── config.py              ← Single source of truth for ALL env vars
├── main.py                ← FastAPI routes + WebSocket handlers
├── agents/
│   ├── spec_loader.py     ← Parses *.agent.md → AgentSpec objects
│   ├── browser_use_bridge.py  ← MCP bridge subprocess (launches browser)
│   ├── mcp_agent.py       ← MCPToolManager (tool discovery via MCP)
│   ├── mcp_servers.json   ← Additional MCP server configs
│   └── specs/             ← Runtime agent specs (loaded by spec_loader.py)
│       ├── browser.agent.md
│       ├── planner.agent.md
│       ├── aggregator.agent.md
│       ├── address.agent.md
│       ├── calendar.agent.md
│       ├── login.agent.md
│       ├── booking.agent.md
│       ├── coder.agent.md
│       └── recovery.md
├── services/
│   ├── brain.py           ← Main orchestrator (Brain class, LangGraph)
│   ├── ATAG.py            ← Agent 1+2 processor + context summarization
│   ├── chat_service.py    ← Chat persistence layer
│   ├── memory_service.py  ← Cognitive memory (episodic/semantic/procedural)
│   ├── observer.py        ← Structured page-state parser
│   ├── verifier.py        ← Per-action verification
│   ├── recovery.py        ← Deterministic failure pre-classification
│   ├── obstacle_handler.py ← CAPTCHA/OTP/interstitial detection
│   ├── address_agent.py   ← Address autocomplete handler
│   ├── calendar_agent.py  ← Date-picker handler
│   ├── login_agent.py     ← Login form handler
│   ├── booking_agent.py   ← Multi-step flow handler
│   └── aggregator_agent.py ← Data extraction/pagination handler
└── utils/
    ├── logger.py
    ├── session_manager.py
    ├── llm_instrumentation.py
    ├── llm_wrapper.py
    └── validator.py
```

## Critical Conventions

### 1. All tools come from MCP — no exceptions
The browser agent's tool list is sourced EXCLUSIVELY from `MCPToolManager.get_tools()`.
Never add a `@tool` decorator or `StructuredTool` to brain.py. To add a tool capability,
either add it to `browser_use_bridge.py` (patched onto the MCP server) or register a new
MCP server in `mcp_servers.json`.

### 2. Agent specs are loaded by spec_loader.py
Files in `Backend/src/agents/specs/*.agent.md` use YAML frontmatter + markdown body.
`spec_loader.py` parses them into `AgentSpec` objects. The `build_system_prompt(spec, stage=...)`
function selects only the sections relevant to the current stage (plan/execute/recover),
not the full spec on every turn.

**NEVER move these files** — `spec_loader.py` expects them at `Backend/src/agents/specs/`.

### 3. Deterministic agents are support layers, not orchestrators
`address_agent.py`, `calendar_agent.py`, `login_agent.py`, `booking_agent.py`, and
`aggregator_agent.py` are injected INTO the browser agent's tool loop (inside `_call_tool`
in `brain.py`). They append guidance text to the observation string — they do NOT make
their own tool calls or run their own LLM passes.

### 4. Config is centralized
Every environment variable is read in `Backend/src/config.py`. No other module should
call `os.getenv()` for application config. The only exception is `browser_use_bridge.py`
which reads per-session overrides injected by MCPToolManager.

### 5. Credentials are never persisted
User-provided passwords, OTPs, card numbers, and verification codes are kept ONLY in
process memory (`Brain.pending_confirmed_inputs`). They are redacted before any database
write. See `never-persist-credentials.md` in `.agents/memory/`.

### 6. Browser stealth is mandatory
Every browser session must inject anti-detection stealth JS. The current implementation
is in `browser_use_bridge.py` (`STEALTH_JS` constant). When using the user's real Chrome
via CDP, most stealth patches are unnecessary since the fingerprint is already genuine.

## Anti-Patterns to Avoid

- **DO NOT** add tool calls outside the MCP boundary
- **DO NOT** hardcode URLs or selectors in Python — they go in the `.agent.md` spec or are discovered dynamically
- **DO NOT** duplicate detection logic — use `ObservedState` flags from `observer.py`
- **DO NOT** mutate earlier messages in the LangGraph chain — append new context as trailing messages (breaks prefix cache otherwise; see `mutating-message-breaks-prefix-cache.md`)
- **DO NOT** write credentials or OTPs to the database — always redact first
- **DO NOT** move files from `Backend/src/agents/specs/` — spec_loader.py depends on that path
