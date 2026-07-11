---
name: mcp-tools
description: >
  MCP (Model Context Protocol) tool discovery and browser bridge subsystem —
  manages the MCP server lifecycle, tool loading, multi-user isolation via
  per-session CDP ports, and the browser_use_bridge subprocess.
---

## What It Does

The MCP system is how the browser agent gets its tools. Instead of hardcoding tool
functions in Python, tools are discovered dynamically from MCP servers at runtime:
1. **MCPToolManager** launches one `browser_use_bridge.py` subprocess per user session
2. The bridge starts a browser and runs an MCP server over stdio
3. `langchain_mcp_adapters` converts MCP tools into LangChain `BaseTool` objects
4. These tools are bound to the LLM for the LangGraph ReAct loop

## Runtime Files

- **Tool Manager**: [mcp_agent.py](file:///d:/Project/SciParser/Backend/src/agents/mcp_agent.py)
  — `MCPToolManager` class: `__init__()` (configures bridge subprocess env),
  `initialize()` (starts MCP sessions, loads tools), `get_tools()`, `close()`.
- **Bridge Subprocess**: [browser_use_bridge.py](file:///d:/Project/SciParser/Backend/src/agents/browser_use_bridge.py)
  — `run_bridge()`: launches browser via browser-use `BrowserSession`, patches
  `BrowserUseServer` with custom tools (key_press, wait), starts MCP stdio server.
- **Extra Servers Config**: [mcp_servers.json](file:///d:/Project/SciParser/Backend/src/agents/mcp_servers.json)
  — Additional MCP servers beyond the built-in browser-use server. Currently empty (`{}`).
- **Server Example**: [mcp_servers.example.json](file:///d:/Project/SciParser/Backend/src/agents/mcp_servers.example.json)
  — Template for adding new MCP servers.
- **Session Manager**: [session_manager.py](file:///d:/Project/SciParser/Backend/src/utils/session_manager.py)
  — Manages per-user session lifecycle, browser open/close, MCP manager lifecycle.

## How It's Activated

`Brain.process_message()` ensures an `MCPToolManager` exists for the user's session via
`SessionManager`. On first use, `mcp_manager.initialize()` is called, which starts the
bridge subprocess and discovers all available tools.

## Key Patterns

- **Per-session isolation**: Each user session gets a unique CDP port (`find_free_port()`),
  a unique `BROWSER_USER_DATA_DIR` subdirectory, and its own bridge subprocess.
- **Env injection**: MCPToolManager passes per-session config to the subprocess via
  environment variables (`MCP_BROWSER_CDP_URL`, `BROWSER_USE_CDP_PORT`, `BROWSER_USER_DATA_DIR`,
  `BROWSER_PROXY_URL`, `MCP_BROWSER_USE_OWN_BROWSER`).
- **Custom tools**: The bridge monkey-patches `BrowserUseServer` to add `browser_key_press`
  and `browser_wait` tools that aren't in the standard browser-use MCP server.
- **Tool extensibility**: Adding a new MCP server in `mcp_servers.json` automatically
  exposes its tools to all agents whose `tool_filter` matches (usually `"*"`).
- **Logging isolation**: ALL logging in the bridge subprocess is redirected to stderr —
  stdout is reserved for MCP JSON-RPC messages.

## Common Issues

- **Bridge startup timeout**: The MCP session has a 30-second timeout. If the browser
  takes too long to launch (e.g., first run downloading Chromium), it fails.
- **Profile lock errors**: Two sessions using the same `user_data_dir` cause Chrome to
  error. The per-port subdirectory naming prevents this.
- **Broken pipe**: If any non-JSON output reaches stdout (logging, print statements),
  the MCP transport breaks with `anyio.BrokenResourceError`.
