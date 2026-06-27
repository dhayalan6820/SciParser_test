import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MCPToolManager:
    """
    Manages the MCP Server connection using langchain_mcp_adapters. 
    Supports dynamic page-level CDP endpoints for multi-user isolation.
    """
    @property
    def stream_manager(self):
        return getattr(self.client, 'stream_manager', None)

    def __init__(self, config: Dict[str, Any] = None, cdp_url: Optional[str] = None, port: Optional[int] = None):
        if hasattr(self, '_initialized_base') and self._initialized_base:
            return
            
        # Accept direct WebSocket or HTTP CDP URL
        self.cdp_url = cdp_url or (f"http://localhost:{port}" if port else "http://localhost:9222")
        
        # Configure the browser-use MCP server via the local bridge script
        # This ensures the browser is launched with the correct CDP port and config
        bridge_path = os.path.join(os.path.dirname(__file__), "browser_use_bridge.py")
        
        # Create a unique user data directory for this user/session to ensure isolation
        # and prevent "two browsers" or profile lock issues.
        base_temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
        user_data_dir = os.path.join(base_temp_dir, f"user_{port}")
        os.makedirs(user_data_dir, exist_ok=True)

        self.config = config or {
            "browser-use": {
                "command": "python",
                "args": [bridge_path],
                "env": {
                    **os.environ,
                    "PYTHONPATH": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
                    "OPENAI_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
                    "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                    "OPENAI_API_BASE": "https://openrouter.ai/api/v1",
                    "BROWSER_USE_MODEL": "google/gemini-3-flash-preview",
                    "MCP_BROWSER_CDP_URL": self.cdp_url,
                    "BROWSER_CDP_URL": self.cdp_url, # Standard env var for some MCP servers
                    "BROWSER_USE_CDP_PORT": str(port) if port else "9222",
                    "BROWSER_USER_DATA_DIR": user_data_dir, # Pass unique profile dir
                    "MCP_BROWSER_USE_OWN_BROWSER": "true",
                    "BROWSER_USE_HEADLESS": os.getenv("BROWSER_USE_HEADLESS", "false"),
                    "BROWSER_USE_DISABLE_SECURITY": "true"
                },
                "transport": "stdio",
            }
        }
        
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

