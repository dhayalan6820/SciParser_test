import os
import asyncio
import logging
import socket
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def _find_free_port() -> int:
    """Ask the OS for an unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class MCPToolManager:
    """
    Manages the MCP Server connection using langchain_mcp_adapters.
    Each instance owns one browser-use bridge subprocess + one Chrome process,
    fully isolated from every other user by a dynamically-assigned port.
    """

    @property
    def stream_manager(self):
        return getattr(self.client, "stream_manager", None)

    def __init__(
        self,
        config: Dict[str, Any] = None,
        cdp_url: Optional[str] = None,
        port: Optional[int] = None,
    ):
        if hasattr(self, "_initialized_base") and self._initialized_base:
            return

        # Always resolve to a real free port — never fall back to a shared 9222
        self._port = port if port else _find_free_port()

        self.cdp_url = cdp_url or f"http://localhost:{self._port}"

        bridge_path = os.path.join(os.path.dirname(__file__), "browser_use_bridge.py")

        # Isolated user-data dir: one Chrome profile per session port
        base_temp_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "temp")
        )
        user_data_dir = os.path.join(base_temp_dir, f"user_{self._port}")
        os.makedirs(user_data_dir, exist_ok=True)

        # Build a clean env for the subprocess — explicit values override anything
        # inherited from the parent process so no two users ever share a port.
        subprocess_env = {
            **os.environ,
            "PYTHONPATH": os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            ),
            "OPENAI_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENAI_API_BASE": "https://openrouter.ai/api/v1",
            "BROWSER_USE_MODEL": "google/gemini-3-flash-preview",
            # Port — the single source of truth for this user's Chrome instance
            "BROWSER_USE_CDP_PORT": str(self._port),
            "BROWSER_USER_DATA_DIR": user_data_dir,
            # Headless + security-off for server-side automation
            "BROWSER_USE_HEADLESS": "true",
            "BROWSER_USE_DISABLE_SECURITY": "true",
            # Remove any stale CDP config from parent env so the bridge always
            # starts fresh for this port
            "BROWSER_CDP_URL": "",
            "MCP_BROWSER_CDP_URL": "",
            "BROWSER_USE_CONFIG_DIR": "",
        }

        self.config = config or {
            "browser-use": {
                "command": "python",
                "args": [bridge_path],
                "env": subprocess_env,
                "transport": "stdio",
            }
        }

        self.client = MultiServerMCPClient(self.config)
        self.stack = AsyncExitStack()
        self._tools = None
        self._initialized = False
        self._initialized_base = True
        self._browser_endpoint = self.cdp_url

        logger.info(
            f"MCPToolManager created — port={self._port}  cdp={self.cdp_url}  "
            f"user_data={user_data_dir}"
        )

    async def set_browser_endpoint(self, endpoint: str):
        self._browser_endpoint = endpoint

    async def get_browser_endpoint(self) -> Optional[str]:
        return self._browser_endpoint

    async def initialize(self):
        """Starts the MCP session ONCE and keeps it open in the background."""
        if self._initialized:
            return

        logger.info(f">>> Starting MCP Server — port={self._port}  cdp={self.cdp_url}")
        all_tools = []
        try:
            for server_name in self.config:
                try:
                    async with asyncio.timeout(30):
                        session = await self.stack.enter_async_context(
                            self.client.session(server_name, auto_initialize=True)
                        )
                        server_tools = await load_mcp_tools(session)
                        all_tools.extend(server_tools)
                except asyncio.TimeoutError:
                    raise Exception(
                        f"MCP Server '{server_name}' timed out during startup."
                    )

            self._tools = all_tools
            self._initialized = True
            logger.info(f">>> MCP Session Ready — {len(self._tools)} tools active.")
        except Exception as e:
            logger.error(f">>> MCP Initialization Failed: {e}", exc_info=True)
            error_msg = str(e)
            if hasattr(e, "exceptions") and e.exceptions:
                error_msg = (
                    f"{error_msg} "
                    f"(Sub-errors: {', '.join([str(ex) for ex in e.exceptions])})"
                )
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
            logger.info(f">>> Closing MCP Session — port={self._port}")
            await self.stack.aclose()
            self._initialized = False
            self._tools = None
