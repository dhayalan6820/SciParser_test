"""
mcp_tool_manager.py

Two MCP servers, clear ownership:

  browser-use  →  all browser / DOM / navigation actions
  tavily       →  all general web search and content research

The agent picks the right tool automatically based on the task:
  - "go to frontier.com and check availability" → browser-use
  - "search for the latest iPhone price"        → tavily
  - "find jobs on LinkedIn and apply"           → browser-use
  - "what is the capital of France"             → tavily
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import traceback
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool routing — which tools belong to which server
# ---------------------------------------------------------------------------

# Tools from browser-use that are kept (browser/DOM actions only)
_BROWSER_TOOL_KEYWORDS = (
    "browser",
    "navigate",
    "click",
    "type",
    "fill",
    "scroll",
    "screenshot",
    "page",
    "tab",
    "element",
    "select",
    "input",
    "submit",
    "extract",
    "wait",
    "dialog",
    "keyboard",
    "mouse",
    "hover",
    "drag",
    "drop",
    "focus",
    "check",
    "uncheck",
    "upload",
    "download",
    "refresh",
    "back",
    "forward",
    "close_tab",
    "open_tab",
    "switch_tab",
    "get_text",
    "get_html",
    "get_url",
    "run_js",
    "evaluate",
    "execute",
    "agent",
    "use_agent",
    "retry",
)

# Tools from browser-use that must be dropped — Tavily handles these
_BROWSER_EXCLUDED_KEYWORDS = (
    "tavily",
    "web_search",
    "search_web",
    "internet_search",
    "google_search",
    "bing_search",
    "duckduckgo",
    "serpapi",
    "search",
)

# Tools from Tavily that are kept
_TAVILY_TOOL_KEYWORDS = (
    "tavily",
    "search",
    "extract",
    "crawl",
    "map",
    "research",
    "web",
    "news",
    "query",
)

# Tools from Tavily that must be dropped
_TAVILY_EXCLUDED_KEYWORDS = (
    "browser",
    "navigate",
    "click",
    "screenshot",
    "playwright",
)


def _is_browser_tool(tool: BaseTool) -> bool:
    name = tool.name.lower()
    for kw in _BROWSER_EXCLUDED_KEYWORDS:
        if kw in name:
            return False
    for kw in _BROWSER_TOOL_KEYWORDS:
        if kw in name:
            return True
    logger.warning(
        f"browser-use tool '{tool.name}' matched no keyword — excluded. "
        "Add it to _BROWSER_TOOL_KEYWORDS if it should be active."
    )
    return False


def _is_tavily_tool(tool: BaseTool) -> bool:
    name = tool.name.lower()
    for kw in _TAVILY_EXCLUDED_KEYWORDS:
        if kw in name:
            return False
    for kw in _TAVILY_TOOL_KEYWORDS:
        if kw in name:
            return True
    logger.warning(
        f"Tavily tool '{tool.name}' matched no keyword — excluded. "
        "Add it to _TAVILY_TOOL_KEYWORDS if it should be active."
    )
    return False


_SERVER_FILTERS = {
    "browser-use": _is_browser_tool,
    "tavily":      _is_tavily_tool,
}


# ---------------------------------------------------------------------------
# Port helper
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Exception helpers
# ---------------------------------------------------------------------------

def _unwrap_exception_group(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        leaves: list[BaseException] = []
        for sub in exc.exceptions:
            leaves.extend(_unwrap_exception_group(sub))
        return leaves
    return [exc]


def _root_cause_message(exc: BaseException) -> str:
    leaves = _unwrap_exception_group(exc)
    parts = []
    for leaf in leaves:
        seen: set[int] = set()
        current: Optional[BaseException] = leaf
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            current = current.__cause__ or (
                current.__context__
                if not current.__suppress_context__
                else None
            )
        parts.append(f"{type(leaf).__name__}: {leaf}")
    return " | ".join(parts) if parts else str(exc)


# ---------------------------------------------------------------------------
# MCPToolManager
# ---------------------------------------------------------------------------

class MCPToolManager:
    """
    Two MCP servers under one manager:

      browser-use  →  browser navigation, clicking, form filling, screenshots
      tavily       →  web search, content extraction, research queries

    The LLM agent sees all tools from both servers and picks the right one
    automatically based on the task. No manual routing needed in calling code.
    """

    @property
    def stream_manager(self):
        return getattr(self.client, "stream_manager", None)

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cdp_url: Optional[str] = None,
        port: Optional[int] = None,
    ):
        if getattr(self, "_initialized_base", False):
            return

        self._port = port if port else _find_free_port()
        self.cdp_url = cdp_url or f"http://localhost:{self._port}"

        bridge_path = os.path.join(
            os.path.dirname(__file__), "browser_use_bridge.py"
        )

        base_temp_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "temp")
        )
        user_data_dir = os.path.join(base_temp_dir, f"user_{self._port}")
        os.makedirs(user_data_dir, exist_ok=True)

        browser_env = {
            **os.environ,
            "PYTHONPATH": os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            ),
            "OPENAI_API_KEY":               os.getenv("OPENROUTER_API_KEY", ""),
            "OPENAI_BASE_URL":              "https://openrouter.ai/api/v1",
            "OPENAI_API_BASE":              "https://openrouter.ai/api/v1",
            "BROWSER_USE_MODEL":            "google/gemini-3-flash-preview",
            "BROWSER_USE_CDP_PORT":         str(self._port),
            "BROWSER_USER_DATA_DIR":        user_data_dir,
            "BROWSER_USE_HEADLESS":         "true",
            "BROWSER_USE_DISABLE_SECURITY": "true",
            # Clear stale parent-env values
            "BROWSER_CDP_URL":              "",
            "MCP_BROWSER_CDP_URL":          "",
            "BROWSER_USE_CONFIG_DIR":       "",
        }

        self.config = config or {
            # ── Server 1: browser-use — all browser / DOM actions ──────────
            "browser-use": {
                "command": "python",
                "args": [bridge_path],
                "env": browser_env,
                "transport": "stdio",
            },
            # ── Server 2: Tavily — all search / research queries ────────────
            "tavily": {
                "command": "npx",
                "args": ["-y", "tavily-mcp@latest"],
                "env": {
                    **os.environ,
                    "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
                },
                "transport": "stdio",
            },
        }

        self.client = MultiServerMCPClient(self.config)
        self.stack = AsyncExitStack()
        self._tools: Optional[List[BaseTool]] = None
        self._initialized = False
        self._initialized_base = True
        self._browser_endpoint = self.cdp_url

        logger.info(
            f"MCPToolManager created — port={self._port}  "
            f"cdp={self.cdp_url}  user_data={user_data_dir}"
        )

    # ── endpoint helpers ────────────────────────────────────────────────────

    async def set_browser_endpoint(self, endpoint: str) -> None:
        self._browser_endpoint = endpoint

    async def get_browser_endpoint(self) -> Optional[str]:
        return self._browser_endpoint

    # ── initialize ──────────────────────────────────────────────────────────

    async def initialize(self, _retry: bool = True) -> None:
        """
        Connect to both MCP servers, apply per-server tool filters,
        and expose the merged tool list to the agent.
        """
        if self._initialized:
            return

        logger.info(
            f">>> Starting MCP servers — port={self._port}  cdp={self.cdp_url}"
        )

        all_tools: List[BaseTool] = []

        try:
            for server_name in self.config:
                try:
                    async with asyncio.timeout(60):
                        session = await self.stack.enter_async_context(
                            self.client.session(
                                server_name, auto_initialize=True
                            )
                        )
                        raw_tools = await load_mcp_tools(session)

                except asyncio.TimeoutError:
                    raise Exception(
                        f"MCP server '{server_name}' timed out during startup (60s). "
                        f"Check that the server process starts and responds to the "
                        f"MCP 'initialize' handshake within 60 s."
                    )

                # Apply per-server filter
                filter_fn = _SERVER_FILTERS.get(server_name)
                if filter_fn:
                    kept    = [t for t in raw_tools if filter_fn(t)]
                    dropped = [t.name for t in raw_tools if not filter_fn(t)]
                else:
                    # Unknown server — keep everything, warn
                    kept    = raw_tools
                    dropped = []
                    logger.warning(
                        f"No filter defined for server '{server_name}' — "
                        "all tools kept. Add a filter to _SERVER_FILTERS."
                    )

                if dropped:
                    logger.info(
                        f"  [{server_name}] Dropped {len(dropped)} tool(s): "
                        + ", ".join(dropped)
                    )

                logger.info(
                    f"  [{server_name}] Active tools ({len(kept)}): "
                    + ", ".join(t.name for t in kept)
                )
                all_tools.extend(kept)

            if not all_tools:
                raise Exception(
                    "No tools were loaded from any MCP server. "
                    "Check browser_use_bridge.py, TAVILY_API_KEY env var, "
                    "and the keyword filters in mcp_tool_manager.py."
                )

            self._tools = all_tools
            self._initialized = True

            browser_count = sum(1 for t in all_tools if _is_browser_tool(t))
            search_count  = sum(1 for t in all_tools if _is_tavily_tool(t))
            logger.info(
                f">>> MCP Ready — {len(all_tools)} tools total | "
                f"{browser_count} browser (browser-use) | "
                f"{search_count} search (tavily)"
            )

        except BaseException as exc:
            logger.error(">>> MCP Initialization Failed — full traceback:")
            logger.error(traceback.format_exc())
            root_msg = _root_cause_message(exc)
            logger.error(f">>> Root cause(s): {root_msg}")

            await self.stack.aclose()
            self._initialized = False
            self._tools = None

            if _retry:
                logger.warning(">>> Retrying MCP initialization once (2 s delay)...")
                await asyncio.sleep(2)
                await self.initialize(_retry=False)
                return

            raise Exception(f"MCP Server failed to start: {root_msg}") from exc

    # ── get_tools ───────────────────────────────────────────────────────────

    async def get_tools(self) -> List[BaseTool]:
        """All tools — browser + search — for the agent."""
        if not self._initialized:
            await self.initialize()
        return self._tools or []

    async def get_browser_tools(self) -> List[BaseTool]:
        """Only browser-use tools."""
        return [t for t in await self.get_tools() if _is_browser_tool(t)]

    async def get_search_tools(self) -> List[BaseTool]:
        """Only Tavily search tools."""
        return [t for t in await self.get_tools() if _is_tavily_tool(t)]

    # ── close ───────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Idempotent — safe to call multiple times."""
        if not self._initialized:
            return
        logger.info(f">>> Closing MCP Session — port={self._port}")
        try:
            await self.stack.aclose()
        except Exception as exc:
            logger.warning(f">>> Error during MCP close: {exc!r}")
        finally:
            self._initialized = False
            self._tools = None