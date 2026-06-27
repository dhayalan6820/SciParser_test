# session_manager.py
import asyncio
import socket
from typing import Dict, Any
from src.utils.logger import logger

def find_free_port() -> int:
    """Dynamically finds an available free port on the host machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class SessionManager:
    """
    Manages session-isolated browser states and ports for multi-user support.
    """
    def __init__(self, stream_manager=None):
        self.stream_manager = stream_manager
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """Retrieves or initializes an isolated state container for a user."""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "mcp_manager": None,
                "port": find_free_port(),
                "cdp_url": None, # Can be set externally to connect to existing browser
                "active_chat_ids": set() # Track active chat IDs for this user
            }
        return self.sessions[user_id]

    def add_active_chat(self, user_id: str, chat_id: str):
        session = self.get_session(user_id)
        session["active_chat_ids"].add(chat_id)

    def remove_active_chat(self, user_id: str, chat_id: str):
        if user_id in self.sessions:
            self.sessions[user_id]["active_chat_ids"].discard(chat_id)

    def get_active_count(self, user_id: str) -> int:
        if user_id in self.sessions:
            return len(self.sessions[user_id]["active_chat_ids"])
        return 0

    async def shutdown_session(self, user_id: str):
        """Cleanly releases and stops processes allocated to a user."""
        if user_id in self.sessions:
            session = self.sessions[user_id]
            
            # Close MCP manager if it exists (this stops the browser-use bridge and its browser)
            if session.get("mcp_manager"):
                try:
                    await session["mcp_manager"].close()
                    logger.info(f"[User {user_id}] MCP manager closed.")
                except Exception as e:
                    logger.error(f"[User {user_id}] Error closing MCP manager: {e}")
            
            del self.sessions[user_id]
            logger.info(f"Session for user {user_id} fully cleaned up.")

    async def shutdown_all(self):
        """Triggers clean release across all running sessions."""
        for uid in list(self.sessions.keys()):
            await self.shutdown_session(uid)
