import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool

from src import config

logger = logging.getLogger(__name__)

_EXTRA_SERVERS_PATH = config.MCP_SERVERS_JSON_PATH


def load_extra_mcp_servers() -> Dict[str, Any]:
    """
    Loads additional MCP server definitions from `Backend/src/agents/mcp_servers.json`.

    This is the ONLY place a new MCP server needs to be registered — no other
    code change is required. Each top-level key is a server name, mapped to a
    standard langchain-mcp-adapters server config dict, e.g.:

        {
          "my_new_server": {
            "command": "python",
            "args": ["/path/to/server.py"],
            "env": {"SOME_KEY": "value"},
            "transport": "stdio"
          }
        }

    Every tool exposed by every configured server is aggregated together by
    `get_tools()`, so agent specs (`*.agent.md`) simply reference tools by
    name/pattern (`tool_filter`) — they never need to know which server a
    tool came from. Adding a server here means its tools become available to
    any agent whose `tool_filter` matches them (or that uses `tool_filter: "*"`).
    """
    if not os.path.exists(_EXTRA_SERVERS_PATH):
        return {}
    try:
        with open(_EXTRA_SERVERS_PATH, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning(f"{_EXTRA_SERVERS_PATH} must contain a JSON object of server_name -> config; ignoring.")
            return {}
        return data
    except Exception as e:
        logger.warning(f"Failed to load extra MCP servers from {_EXTRA_SERVERS_PATH}: {e}")
        return {}


def find_free_port() -> int:
    """Dynamically finds an available free port on the host machine."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class MCPToolManager:
    """
    Manages the MCP Server connection using langchain_mcp_adapters. 
    Supports dynamic page-level CDP endpoints for multi-user isolation.
    """
    @property
    def stream_manager(self):
        return getattr(self.client, 'stream_manager', None)

    def __init__(self, mcp_config: Dict[str, Any] = None, cdp_url: Optional[str] = None, port: Optional[int] = None, user_agent_index: int = 0, own_browser: bool = True, proxy_url: Optional[str] = None, browser_engine: Optional[str] = None, user_id: Optional[str] = None):
        if hasattr(self, '_initialized_base') and self._initialized_base:
            return

        # Dynamic port assignment for multi-user isolation
        self.port = port or find_free_port()
        self.user_id = user_id

        # Accept direct WebSocket or HTTP CDP URL
        self.cdp_url = cdp_url or f"http://{config.BROWSER_DEFAULT_CDP_HOST}:{self.port}"

        # Configure the browser-use MCP server via the local bridge script
        # This ensures the browser is launched with the correct CDP port and config
        bridge_path = config.BROWSER_USE_BRIDGE_PATH

        # Create a unique user data directory for this user/session to ensure isolation
        # and prevent "two browsers" or profile lock issues.
        base_temp_dir = config.TEMP_DIR_PATH
        user_data_dir = os.path.join(base_temp_dir, f"user_{self.port}")
        os.makedirs(user_data_dir, exist_ok=True)

        # NOTE: the vars below marked "per-session override" are intentional
        # inter-process passthrough values, not stray hardcoded config. Each
        # call to __init__ launches a dedicated browser_use_bridge.py
        # subprocess for one user session, and these values must vary per
        # session (different CDP endpoint/port/profile dir/proxy per user).
        # They are read back out on the bridge side via the matching
        # config.browser_*_override() accessors in src/config.py, which
        # documents this contract from that end too.
        self.config = mcp_config or {
            "browser-use": {
                "command": "python",
                "args": [bridge_path],
                "env": {
                    **os.environ,
                    "PYTHONPATH": config.BACKEND_ROOT,
                    "OPENAI_API_KEY": config.OPENROUTER_API_KEY or os.getenv("OPENAI_API_KEY", ""),
                    "OPENROUTER_API_KEY": config.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", ""),
                    "OPENAI_BASE_URL": config.OPENROUTER_BASE_URL or os.getenv("OPENAI_BASE_URL", ""),
                    "OPENAI_API_BASE": config.OPENROUTER_BASE_URL or os.getenv("OPENAI_API_BASE", ""),
                    "BROWSER_USE_MODEL": config.OPENROUTER_MODEL,
                    "LLM_EXTRACTION_MODEL": os.getenv("LLM_EXTRACTION_MODEL", "openai/gpt-4o-mini-2024-07-18"),
                    "MCP_BROWSER_CDP_URL": self.cdp_url,  # per-session override
                    "BROWSER_CDP_URL": self.cdp_url, # Standard env var for some MCP servers
                    "BROWSER_USE_CDP_PORT": str(self.port),  # per-session override
                    "BROWSER_USER_DATA_DIR": user_data_dir, # per-session override — unique profile dir per user
                    "MCP_BROWSER_USE_OWN_BROWSER": "true" if own_browser else "false",  # per-session override
                    "BROWSER_PROXY_URL": proxy_url or "",  # per-session override
                    "BROWSER_ENGINE": browser_engine or config.BROWSER_ENGINE,
                    "BROWSER_USE_SYSTEM_CHROME": "true" if config.BROWSER_USE_SYSTEM_CHROME else "false",
                    "BROWSER_USE_PROFILE_DIR": config.BROWSER_PROFILE_DIRECTORY,
                    "BROWSER_USE_REAL_CHROME": "true" if config.BROWSER_USE_REAL_CHROME else "false",
                    "BROWSER_EXECUTABLE_PATH": config.BROWSER_EXECUTABLE_PATH,
                    "BROWSER_PROFILE_DIRECTORY": config.BROWSER_PROFILE_DIRECTORY,
                    "BROWSER_USE_HEADLESS": "false" if config.BROWSER_USE_SYSTEM_CHROME or config.BROWSER_USE_REAL_CHROME else os.getenv("BROWSER_USE_HEADLESS", "false"),
                    "BROWSER_USE_DISABLE_SECURITY": "true",
                    "BROWSER_USER_AGENT_INDEX": str(user_agent_index),
                    "BROWSER_USE_KEEP_ALIVE": os.getenv("BROWSER_USE_KEEP_ALIVE", "true"),
                    "BROWSER_USE_USER_ID": user_id or "system",
                    "BACKEND_API_URL": "http://localhost:8000",
                },
                "transport": "stdio",
            }
        }

        # Merge in any additional MCP servers declared in mcp_servers.json.
        # This is what makes tool discovery extensible: dropping a new server
        # config into that file is enough to expose its tools to every agent
        # (subject to each agent spec's tool_filter) — no code change here.
        extra_servers = load_extra_mcp_servers()
        if extra_servers:
            overlapping = set(extra_servers) & set(self.config)
            if overlapping:
                logger.warning(f"mcp_servers.json redefines built-in server name(s) {overlapping}; built-in config takes precedence.")
                extra_servers = {k: v for k, v in extra_servers.items() if k not in overlapping}
            self.config = {**self.config, **extra_servers}
            logger.info(f">>> Loaded {len(extra_servers)} additional MCP server(s) from mcp_servers.json: {list(extra_servers.keys())}")

        self.client = MultiServerMCPClient(self.config)
        self.stack = AsyncExitStack()
        self._tools = None
        self._initialized = False
        self._initialized_base = True
        self._browser_endpoint = self.cdp_url

    async def set_browser_endpoint(self, endpoint: str):
        self._browser_endpoint = endpoint

    async def get_browser_endpoint(self) -> Optional[str]:
        return self._browser_endpoint

    async def initialize(self):
        """Starts the MCP session ONCE and keeps it open in the background."""
        if self._initialized:
            return

        logger.info(f">>> Starting MCP Server connecting to {self.cdp_url}...")
        all_tools = []
        try:
            for server_name in self.config:
                # Initialize session for each configured server with a timeout
                try:
                    async with asyncio.timeout(30): # 30 second timeout for server startup
                        session = await self.stack.enter_async_context(
                            self.client.session(server_name, auto_initialize=True)
                        )
                        # Load tools from the session using the adapter helper
                        server_tools = await load_mcp_tools(session)
                        all_tools.extend(server_tools)
                except asyncio.TimeoutError:
                    raise Exception(f"MCP Server '{server_name}' timed out during startup.")

            self._tools = all_tools
            self._initialized = True
            logger.info(f">>> MCP Session Ready. {len(self._tools)} tools active.")
        except Exception as e:
            logger.error(f">>> MCP Initialization Failed: {e}", exc_info=True)
            # Unwrap ExceptionGroup if possible
            error_msg = str(e)
            if hasattr(e, 'exceptions') and e.exceptions:
                error_msg = f"{error_msg} (Sub-errors: {', '.join([str(ex) for ex in e.exceptions])})"

            await self.stack.aclose()
            self._initialized = False
            raise Exception(f"MCP Server failed to start: {error_msg}")

    async def get_tools(self) -> List[BaseTool]:
        if not self._initialized:
            await self.initialize()
        return self._tools or []

    async def close(self):
        """Only call this when the entire session is being destroyed."""
        if self._initialized:
            logger.info(f">>> Closing MCP Session for {self.cdp_url}...")
            await self.stack.aclose()
            self._initialized = False
            self._tools = None

