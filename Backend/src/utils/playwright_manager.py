# playwright_manager.py
import os
import asyncio
import socket
from typing import Dict, Any
from playwright.async_api import async_playwright, Page
from src.utils.logger import logger

os.environ.pop("DEBUG", None)

def find_free_port() -> int:
    """Dynamically finds an available free port on the host machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class PlaywrightSessionManager:
    """
    Manages session-isolated Playwright browser contexts, remotable CDPs,
    and automatic page screencasts.
    """
    def __init__(self, stream_manager=None):
        self.stream_manager = stream_manager
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def get_session(self, thread_id: str) -> Dict[str, Any]:
        """Retrieves or initializes an isolated browser state container for a session."""
        if thread_id not in self.sessions:
            self.sessions[thread_id] = {
                "playwright": None,
                "browser": None,
                "context": None,
                "page": None,
                "mcp_manager": None,
                "browser_launched": False,
                "streaming_mode": "Inactive",
                "last_frame_time": 0.0,
                "active_cdp": None,
                "port": find_free_port()
            }
        return self.sessions[thread_id]

    async def ensure_browser_launched(self, thread_id: str):
        """Launches a dedicated browser context for the requested session thread."""
        async with self._lock:
            session = self.get_session(thread_id)
            page = session.get("page")

            if page is not None:
                try:
                    await page.title()
                    return
                except Exception:
                    logger.info(f"[Session {thread_id}] Closed tab detected. Cleaning state...")
                    await self.shutdown_session(thread_id)

            logger.info(f"[Session {thread_id}] Launching browser on remote port: {session['port']}")
            try:
                session["playwright"] = await async_playwright().start()
                
                # Launch Chromium with debugging enabled
                session["browser"] = await session["playwright"].chromium.launch(
                    headless=False,
                    args=[
                        "--start-maximized",
                        f"--remote-debugging-port={session['port']}",
                        "--remote-allow-origins=*"
                    ]
                )
                
                UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                session["context"] = await session["browser"].new_context(
                    no_viewport=True,
                    accept_downloads=True,
                    user_agent=UA,
                    locale="en-US",
                    permissions=["geolocation", "notifications"]
                )
                
                session["page"] = await session["context"].new_page()
                session["page"].on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
                
                # Attach live screencast tracker
                await self._start_live_stream(session, thread_id)
                session["browser_launched"] = True
                logger.info(f"[Session {thread_id}] Dedicated browser successfully mounted.")
            except Exception as e:
                logger.error(f"[Session {thread_id}] Failed to launch browser: {e}")
                await self.shutdown_session(thread_id)
                raise

    async def _start_live_stream(self, session: Dict[str, Any], thread_id: str):
        """Initiates CDP screencasting on the initial page and listens to subsequent tabs."""
        if not self.stream_manager:
            return

        async def attach_screencast(target_page: Page):
            try:
                if session.get("active_cdp"):
                    try:
                        await session["active_cdp"].send("Page.stopScreencast")
                        await session["active_cdp"].detach()
                    except Exception:
                        pass
                
                cdp = await target_page.context.new_cdp_session(target_page)
                session["active_cdp"] = cdp
                
                await cdp.send("Page.startScreencast", {
                    "format": "jpeg",
                    "quality": 55,
                    "maxWidth": 1280,
                    "maxHeight": 720,
                    "everyNthFrame": 1
                })
                
                async def on_screencast_frame(event):
                    try:
                        base64_data = event.get("data")
                        if base64_data and self.stream_manager:
                            asyncio.create_task(self.stream_manager.broadcast_frame(base64_data, thread_id))
                        await cdp.send("Page.screencastFrameAck", {"sessionId": event.get("sessionId")})
                    except Exception:
                        pass
                
                cdp.on("Page.screencastFrame", on_screencast_frame)
                logger.info(f"[Session {thread_id}] Screencast streaming successfully attached.")
            except Exception as e:
                logger.error(f"[Session {thread_id}] Screencast connection failure: {e}")

        # Hook to active page
        if session.get("page"):
            await attach_screencast(session["page"])

        # Listen to context to bind dynamically to new tab creation
        session["context"].on("page", lambda new_page: asyncio.create_task(attach_screencast(new_page)))

    async def shutdown_session(self, chat_id: str):
        """Cleanly releases and stops browser processes allocated to a thread."""
        if chat_id in self.sessions:
            session = self.sessions[chat_id]
            
            # Close MCP Manager if it exists in the session
            if "mcp_manager" in session:
                await session["mcp_manager"].close()
            
            # Close browser
            if session.get("browser"):
                await session["browser"].close()
            
            del self.sessions[chat_id]
            logger.info(f"Session {chat_id} fully cleaned up.")

    async def shutdown_all(self):
        """Triggers clean release across all running sessions."""
        for tid in list(self.sessions.keys()):
            await self.shutdown_session(tid)