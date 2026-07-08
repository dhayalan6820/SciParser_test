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
        # Per-user locks serializing close_browser calls. Multiple callers can
        # legitimately race to close the same browser (stop_process, the
        # tool-graph's cleanup finally block, and an explicit POST
        # /browser/close from the frontend can all fire around the same
        # cancellation). Without serialization, a second caller can grab the
        # `mcp` reference before the first sets it to None and then call
        # mcp.close() concurrently from a different asyncio task than the one
        # that entered its AsyncExitStack, raising "Attempted to exit cancel
        # scope in a different task than it was entered in".
        self._close_locks: Dict[str, asyncio.Lock] = {}

    def _get_close_lock(self, user_id: str) -> asyncio.Lock:
        lock = self._close_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._close_locks[user_id] = lock
        return lock

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """Retrieves or initializes an isolated state container for a user."""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "mcp_manager": None,
                "port": find_free_port(),
                "cdp_url": None,          # Can be set externally to connect to existing browser
                "proxy_url": None,        # Residential/HTTP proxy URL (http://user:pass@host:port)
                "browser_engine": None,   # "camoufox" or "chrome" (None = use default)
                "active_chat_ids": set()  # Track active chat IDs for this user
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

    async def close_browser(self, user_id: str):
        """Close the browser/MCP process for a user but keep the session alive for reuse.

        Use this for the 'Close Browser' button and 'Stop Process' — it stops
        the browser process and marks mcp_manager as None so it will be
        re-initialised on the next task, without destroying the whole session.
        """
        if user_id not in self.sessions:
            return
        # Serialize concurrent closers for this user — see the comment on
        # self._close_locks in __init__ for why this is required.
        async with self._get_close_lock(user_id):
            session = self.sessions[user_id]
            mcp = session.get("mcp_manager")
            if mcp is None:
                return
            # Clear the reference before awaiting the close so any concurrent
            # caller that queued up behind this lock sees mcp_manager is
            # already gone once it acquires the lock, instead of trying to
            # close the same (already-closing) manager a second time.
            session["mcp_manager"] = None
            try:
                # Enforce a hard timeout so a stuck MCP manager (e.g. mid-
                # tool-call deadlock) can't hang the stop/close operation.
                await asyncio.wait_for(mcp.close(), timeout=5.0)
                logger.info(f"[User {user_id}] Browser process closed.")
            except asyncio.TimeoutError:
                logger.warning(f"[User {user_id}] Browser close timed out after 5s — forcing None.")
            except Exception as e:
                logger.error(f"[User {user_id}] Error closing browser: {e}")

    async def shutdown_session(self, user_id: str):
        """Fully destroy a user session (called at server shutdown or on explicit full-cleanup)."""
        if user_id in self.sessions:
            await self.close_browser(user_id)
            del self.sessions[user_id]
            logger.info(f"Session for user {user_id} fully cleaned up.")

    async def shutdown_all(self):
        """Triggers clean release across all running sessions."""
        for uid in list(self.sessions.keys()):
            await self.shutdown_session(uid)
