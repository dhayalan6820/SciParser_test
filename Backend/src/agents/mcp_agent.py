import asyncio
import logging
import sys
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class MCPToolManager:
    """
    Manages the MCP Server connection. Supports dynamic page-level CDP endpoints for multi-user isolation.
    """
    def __init__(self, config: Dict[str, Any] = None, cdp_url: Optional[str] = None):
        # Accept direct WebSocket or HTTP CDP URL
        self.cdp_url = cdp_url or "http://localhost:9222"
        
        # Use npx.cmd on Windows for reliable subprocess execution
        npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
        
        self.config = config or {
            "playwright": {
                "command": npx_cmd,
                "args": [
                    "-y", 
                    "@playwright/mcp@latest", 
                    f"--cdp-endpoint={self.cdp_url}"
                ],
                "transport": "stdio",
            }
        }
        self.client = MultiServerMCPClient(self.config)
        self.stack = AsyncExitStack()
        self._tools = None
        self._initialized = False

    async def initialize(self):
        """Starts the MCP session by iterating through servers and loading tools."""
        if self._initialized:
            return
        
        logger.info(f"Initializing MCP for {self.cdp_url}")
        try:
            # MultiServerMCPClient 0.1.0+ uses get_tools() to trigger internal initialization
            self._tools = await self.client.get_tools()
            self._initialized = True
            logger.info(f"MCP initialized successfully with {len(self._tools)} tools.")
        except Exception as e:
            logger.error(f"Failed to initialize MCP: {e}")
            self._initialized = False
            raise

    async def get_tools(self) -> List[BaseTool]:
        if not self._initialized:
            try:
                await self.initialize()
            except Exception as e:
                logger.error(f"Lazy initialization of MCP failed: {e}")
                return [] # Return empty list instead of crashing
        return self._tools or []

    async def close(self):
        """Only call this when the session is explicitly destroyed."""
        if self._initialized:
            try:
                # No longer using stack for the client itself
                pass
            finally:
                self._initialized = False
