import asyncio
import base64
import os
import json
import re
import uuid
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from langchain_core.messages import (
    HumanMessage, 
    AIMessage, 
    SystemMessage, 
    ToolMessage
)

from langchain_core.tools import BaseTool 
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Database and Utilities
from src.database.chat_db import AsyncSessionLocal, Message, ChatSession, AgentExecutionLog, ToolExecutionLog
from src.utils.logger import logger
from src import config
from src.agents.mcp_agent import MCPToolManager
from src.utils.session_manager import SessionManager
from src.services.memory_service import MemoryService
from src.services.obstacle_handler import (
    detect_captcha_type,
    detect_obstacle,
    ObstacleMatch,
    ObstacleInputNeeded,
    build_input_form,
)

# ATAG Models
from src.services.ATAG import (
    AgentState, 
    ATAGProcessor, 
    serialize_state
)
from src.agents import spec_loader


def _build_browser_static_prompt() -> str:
    """Builds the Browser agent's static system prompt from browser.agent.md.

    This is the single place the 20-section persona/playbook is assembled —
    editing browser.agent.md changes agent behavior on the next request, with
    no code change or redeploy required. Cached at module import time since
    the prompt is identical across every run and step (see caching note at
    its call site in _execute_tool_graph).
    """
    spec = spec_loader.load_spec("browser")
    return spec_loader.build_system_prompt(spec)


def _detect_captcha(observation_text: str) -> Optional[str]:
    """Return CAPTCHA type string if a known CAPTCHA signal is present, else None.

    Thin wrapper kept for backward compatibility (existing tests call this by
    name) — the canonical detector now lives in the generic obstacle-handling
    framework (`src.services.obstacle_handler`) alongside the other obstacle
    detectors (e.g. OTP), so detection logic isn't duplicated per type.
    """
    return detect_captcha_type(observation_text)


def _extract_form_answer(user_message: str) -> str:
    """Pull the raw value out of a NEEDS_INPUT form submission like
    'Verification Code: 123456' — falls back to the full message if no
    'Label: value' pattern is found."""
    m = re.search(r":\s*(.+)$", (user_message or "").strip())
    return m.group(1).strip() if m else (user_message or "").strip()


class DatabaseManager:
    """Manages transaction-scoped database operations securely to prevent locking connection pools."""
    
    async def log_agent_execution(self, user_id: str, chat_id: str, stage: str, name: str, status: str, input_data: Any = None, output_data: Any = None, error: str = None, token_usage: Dict[str, int] = None, cost: float = None):
        async with AsyncSessionLocal() as db:
            try:
                log = AgentExecutionLog(
                    user_id=user_id,
                    chat_id=chat_id,
                    agent_stage=stage,
                    stage_name=name,
                    status=status,
                    input_data=json.dumps(input_data) if input_data else None,
                    output_data=json.dumps(output_data) if output_data else None,
                    error_message=error,
                    token_usage=json.dumps(token_usage) if token_usage else None,
                    cost=str(cost) if cost is not None else None
                )
                db.add(log)
                await db.commit()
                return log.id
            except Exception as e:
                logger.error(f"Error logging agent execution: {e}")

    async def log_tool_execution(self, chat_id: str, agent_id: str, tool_name: str, status: str, tool_input: Any = None, tool_output: Any = None, error: str = None):
        async with AsyncSessionLocal() as db:
            try:
                log = ToolExecutionLog(
                    chat_id=chat_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    status=status,
                    tool_input=json.dumps(tool_input) if tool_input else None,
                    tool_output=json.dumps(tool_output) if tool_output else None,
                    error_message=error
                )
                db.add(log)
                await db.commit()
                return log.id
            except Exception as e:
                logger.error(f"Error logging tool execution: {e}")

    async def get_or_create_chat_session(self, user_id: str, chat_id: str) -> ChatSession:
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(ChatSession).where(ChatSession.id == chat_id))
                session = result.scalar_one_or_none()
                if session:
                    db.expunge(session)
                    return session
                
                new_session = ChatSession(
                    id=chat_id,
                    user_id=user_id,
                    title="New Chat",
                    state_data=json.dumps({})
                )
                db.add(new_session)
                await db.commit()
                await db.refresh(new_session)
                db.expunge(new_session)
                return new_session
            except IntegrityError:
                await db.rollback()
                result = await db.execute(select(ChatSession).where(ChatSession.id == chat_id))
                session = result.scalar_one_or_none()
                if session:
                    db.expunge(session)
                    return session
                raise Exception(f"Failed to create or retrieve session for chat_id={chat_id}, user_id={user_id}")
            except Exception as e:
                logger.error(f"Error getting/creating session: {e}")
                raise


def _sanitize_browser_observation(observation: Any, tool_call: Dict[str, Any]) -> Any:
    """
    Inspect a browser tool observation and replace known error/proxy pages
    with a clean, actionable error string.

    IMPORTANT: Only flag observations that match SPECIFIC known-bad patterns.
    Do NOT flag legitimate website HTML — the old approach used `is_html_page`
    which incorrectly blocked real page content from reaching the agent.
    """
    text = str(observation)
    url_attempted = tool_call.get("args", {}).get("url", "")

    # --- Known-bad pattern matching (order matters — most specific first) ---

    # 1. Replit proxy "couldn't reach this app" page
    if re.search(r"couldn't reach|couldn\u2019t reach|We couldn't reach|couldn\u2019t connect", text, re.IGNORECASE):
        reason = "Replit proxy blocked the request — this URL is unreachable inside the sandbox."

    # 2. Browser-level connection errors (typically in error page text or tool output)
    elif re.search(r'ERR_NAME_NOT_RESOLVED|ERR_CONNECTION_REFUSED|ERR_CONNECTION_TIMED_OUT|ERR_TUNNEL_CONNECTION_FAILED', text):
        reason = "DNS/connection error — the host could not be reached."

    # 3. Verizon / ISP / enterprise bot-protection "Access denied" pages
    elif re.search(r'Access\s+denied.*(?:Verizon|Security\s+Policy|Information\s+Security)|(?:Verizon|Security\s+Policy).*Access\s+denied', text, re.IGNORECASE | re.DOTALL):
        reason = "The website blocked automated browser access (Verizon/enterprise security policy). Try searching for an alternative URL."

    # 4. Cloudflare / generic bot-challenge page (only if it's a full HTML block)
    elif re.search(r'<!DOCTYPE|<html', text, re.IGNORECASE) and re.search(r'403\s+Forbidden', text, re.IGNORECASE):
        reason = "The server returned 403 Forbidden."

    elif re.search(r'<!DOCTYPE|<html', text, re.IGNORECASE) and re.search(r'404\s+Not\s+Found', text, re.IGNORECASE):
        reason = "The server returned 404 Not Found."

    # 5. Replit proxy error page signature (CSS background color used in the Replit error page)
    elif re.search(r'background:\s*#1c2333', text, re.IGNORECASE):
        reason = "Replit internal proxy error page returned — this URL is blocked inside the sandbox."

    else:
        # No known error pattern — pass the observation through unchanged.
        # Legitimate website HTML, accessibility-tree output, etc. must NOT be blocked.
        return observation

    # Build a short human-readable text snippet from any HTML in the observation
    snippet = re.sub(r'<[^>]+>', ' ', text)
    snippet = re.sub(r'\s+', ' ', snippet).strip()[:200]

    clean_error = (
        f"[Navigation Error] {reason}"
        + (f" URL attempted: {url_attempted}" if url_attempted else "")
        + f" Page text: \"{snippet}\""
        + " — Try a different URL or use web search to find an accessible alternative."
    )

    logger.warning(f"Browser observation sanitized for tool '{tool_call.get('name')}': {reason}")
    return clean_error


class Brain:
    """
    Orchestrates the Multi-Agent System (Agent 1, Agent 2, Agent 3) using LangGraph and LangChain.
    """
    def __init__(self, stream_manager=None):
        self.stream_manager = stream_manager
        self.session_manager = SessionManager(stream_manager=stream_manager)
        self.db_manager = DatabaseManager()
        self.atag_processor: Optional[ATAGProcessor] = None
        self.llm = None
        self.search_tool = None
        self.initialized = False
        self.checkpointer = MemorySaver()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.active_plans: Dict[str, List[Dict]] = {}
        # Real (unredacted) confirmed_inputs for a paused obstacle run, kept
        # ONLY in memory for the lifetime of this process — never written to
        # the database. Personal/account data must never be persisted; if the
        # process restarts before the run resumes, we deliberately fall back
        # to asking the user again rather than reading a stale value back
        # from disk. Keyed by chat_id, popped (single-use) on resume.
        self.pending_confirmed_inputs: Dict[str, Dict[str, Any]] = {}
        # Cooperative cancellation: chat_ids explicitly stopped by the user
        self.cancelled_chats: set = set()
        # In-memory tool log buffer: chat_id → list of tool events (capped at 200)
        self.tool_log_buffer: Dict[str, List[Dict]] = {}
        # Cognitive memory service (initialized after LLM is ready)
        self.memory_service: Optional[MemoryService] = None

    def buffer_tool_event(self, chat_id: str, event: Dict[str, Any]):
        """Append a tool event to the in-memory buffer (max 200 per chat)."""
        if chat_id not in self.tool_log_buffer:
            self.tool_log_buffer[chat_id] = []
        self.tool_log_buffer[chat_id].append(event)
        if len(self.tool_log_buffer[chat_id]) > 200:
            self.tool_log_buffer[chat_id] = self.tool_log_buffer[chat_id][-200:]

    def get_live_tool_logs(self, chat_id: str) -> List[Dict]:
        return list(self.tool_log_buffer.get(chat_id, []))

    def clear_live_tool_logs(self, chat_id: str):
        self.tool_log_buffer.pop(chat_id, None)

    async def _evaluate_captcha_outcome(
        self,
        captcha_state: Dict[str, Any],
        observation: Any,
        user_id: str,
        task_domain: str,
    ) -> None:
        """Evaluate whether the previous CAPTCHA bypass attempt succeeded.

        Pops the ``captcha_state["pending"]`` entry (if present), inspects
        *observation* for lingering CAPTCHA signals, and updates procedural
        memory accordingly.  A MemoryReflection lesson is written on failure.

        This is extracted from the ``_call_tool`` closure so that it can be
        unit-tested independently of the full agent graph.
        """
        if not captcha_state.get("pending") or not self.memory_service:
            return

        _prev_captcha = captcha_state.pop("pending")
        _still_has_captcha = bool(_detect_captcha(str(observation)))
        _obs_is_error = str(observation)[:500].startswith("Error")
        _captcha_resolved = not _still_has_captcha and not _obs_is_error

        try:
            await self.memory_service._update_procedural(
                user_id,
                _prev_captcha["skill_name"],
                task_domain,
                [],
                success=_captcha_resolved,
            )
            if not _captcha_resolved:
                await self.memory_service.store_reflection(
                    user_id,
                    task_domain,
                    (
                        f"CAPTCHA skill '{_prev_captcha['skill_name']}' failed to bypass "
                        f"{_prev_captcha['captcha_type']} CAPTCHA on {task_domain}. "
                        f"The CAPTCHA was still present after executing the stored steps. "
                        f"Try a different bypass approach or wait longer before retrying."
                    ),
                    category="CAPTCHA",
                    severity="HIGH",
                )
                logger.info(
                    f"[CAPTCHA] Recorded FAILURE for skill '{_prev_captcha['skill_name']}' "
                    f"on domain '{task_domain}' — confidence decreased."
                )
            else:
                logger.info(
                    f"[CAPTCHA] Recorded SUCCESS for skill '{_prev_captcha['skill_name']}' "
                    f"on domain '{task_domain}' — confidence increased."
                )
        except Exception as _cap_upd_err:
            captcha_state["pending"] = _prev_captcha
            logger.warning(f"[CAPTCHA] outcome update failed (non-fatal): {_cap_upd_err}")

    async def initialize(self):
        """Eagerly initializes execution LLMs, search utilities, and subprocess processors."""
        if self.initialized:
            return
        
        logger.info("Initializing multi-agent orchestrator system...")
        api_key = config.OPENROUTER_API_KEY
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        self.llm = ChatOpenAI(
            model=config.OPENROUTER_MODEL,
            openai_api_key=api_key,
            base_url=config.OPENROUTER_BASE_URL,
            temperature=0.3,
            max_tokens=16384,
            default_headers={"x-or-cache": "1"},
        )
        
        # Specialized model for code generation
        self.code_llm = ChatOpenAI(
            model=config.OPENROUTER_MODEL,
            openai_api_key=api_key,
            base_url=config.OPENROUTER_BASE_URL,
            temperature=0.1,
            max_tokens=8192,
            default_headers={"x-or-cache": "1"},
        )

        self.search_tool = TavilySearch(max_results=3)
        self.atag_processor = ATAGProcessor(self.llm)
        self.code_processor = ATAGProcessor(self.code_llm, tavily_api_key=config.TAVILY_API_KEY)

        # Cognitive memory service
        self.memory_service = MemoryService(llm=self.llm)
        await self.memory_service.seed_captcha_skills()

        self.initialized = True
        logger.info("Multi-agent orchestrator initialization complete.")

    def _compress_screenshot(self, png_bytes: bytes, max_width: int = 1280, quality: int = 80) -> str:
        """Resize to max_width and encode as JPEG to keep WS payload within proxy limits."""
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(png_bytes))
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    async def _stream_browser_frames(self, user_id: str, chat_id: str, stop_event: asyncio.Event):
        """
        Capture screenshots from Chrome via raw CDP HTTP + WebSocket (aiohttp).

        Replaces the old Playwright connect_over_cdp approach, which only saw
        contexts created by the *same* Playwright session.  Raw CDP /json lists
        ALL page targets regardless of which client created them, so we reliably
        see pages opened by the bridge subprocess's browser-use agent.
        """
        import aiohttp
        import json as json_lib
        from urllib.parse import urlparse

        session_obj = self.session_manager.get_session(user_id)
        mcp_manager = session_obj.get("mcp_manager")
        if not mcp_manager:
            logger.warning(f"No MCP manager for user {user_id}, live preview disabled.")
            return

        cdp_url = getattr(mcp_manager, "cdp_url", None)
        if not cdp_url:
            logger.warning(f"No CDP URL for user {user_id}, live preview disabled.")
            return

        parsed = urlparse(cdp_url)
        host = parsed.hostname or config.BROWSER_DEFAULT_CDP_HOST
        port = parsed.port
        json_endpoint = f"http://{host}:{port}/json"

        logger.info(f"Starting raw-CDP screenshot stream: user={user_id} chat={chat_id} port={port}")

        msg_id_counter = [0]

        async def _get_page_ws_url() -> Optional[str]:
            """Return the WS debugger URL of the first available page target."""
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.get(
                        json_endpoint,
                        timeout=aiohttp.ClientTimeout(total=config.CDP_JSON_TIMEOUT_SECONDS),
                    ) as resp:
                        targets = await resp.json(content_type=None)
                for t in targets:
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        return t["webSocketDebuggerUrl"]
            except Exception as exc:
                logger.debug(f"CDP /json failed for user {user_id}: {exc}")
            return None

        async def _take_screenshot(ws_url: str) -> Optional[str]:
            """Issue Page.captureScreenshot over CDP and return base64 JPEG string."""
            msg_id_counter[0] += 1
            mid = msg_id_counter[0]
            cmd = json_lib.dumps({
                "id": mid,
                "method": "Page.captureScreenshot",
                "params": {"format": "jpeg", "quality": 75, "captureBeyondViewport": False},
            })
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.ws_connect(
                        ws_url,
                        timeout=aiohttp.ClientTimeout(total=config.CDP_SCREENSHOT_TIMEOUT_SECONDS),
                    ) as ws:
                        await ws.send_str(cmd)
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json_lib.loads(msg.data)
                                if data.get("id") == mid:
                                    if "result" in data:
                                        return data["result"].get("data")
                                    logger.debug(f"CDP screenshot error: {data.get('error')}")
                                    return None
                            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                                break
            except Exception as exc:
                logger.debug(f"CDP screenshot WS failed for user {user_id}: {exc}")
            return None

        def _read_mouse_state() -> Optional[dict]:
            """Read the bridge's mouse-state temp file for this user's CDP port."""
            try:
                import time as _time
                state_path = f"/tmp/agent_mouse_{port}.json"
                p = Path(state_path)
                if p.exists():
                    data = json.loads(p.read_text())
                    if _time.time() - data.get("ts", 0) < 30:
                        return data
            except Exception:
                pass
            return None

        async def _broadcast_frame(b64: str):
            # At screenshot cadence, also emit a mouse event so the frontend
            # overlay stays in sync even when the 150ms loop is behind.
            mouse_state = _read_mouse_state()
            if mouse_state and self.stream_manager:
                await self.stream_manager.broadcast_mouse(
                    {
                        "chat_id": chat_id,
                        "x": mouse_state["x"],
                        "y": mouse_state["y"],
                        "event": mouse_state.get("event", "move"),
                        "vpW": mouse_state.get("vpW", 1280),
                        "vpH": mouse_state.get("vpH", 800),
                    },
                    user_id,
                )
            # Ensure the frame has the data-URL prefix the frontend expects
            if not b64.startswith("data:"):
                b64 = f"data:image/jpeg;base64,{b64}"
            logger.info(
                f"Broadcasting browser frame: user={user_id} chat={chat_id} len={len(b64)}"
            )
            if self.stream_manager:
                await self.stream_manager.broadcast_frame(
                    {"chat_id": chat_id, "frame": b64}, user_id
                )

        # ── High-frequency mouse event loop (~7 fps, independent of screenshots) ──
        async def _mouse_event_loop() -> None:
            """Poll mouse state at ~150 ms intervals; broadcast on any change."""
            last_ts: float = 0.0
            while not stop_event.is_set():
                try:
                    ms = _read_mouse_state()
                    if ms and ms.get("ts", 0.0) != last_ts:
                        last_ts = ms["ts"]
                        if self.stream_manager:
                            await self.stream_manager.broadcast_mouse(
                                {
                                    "chat_id": chat_id,
                                    "x":       ms["x"],
                                    "y":       ms["y"],
                                    "event":   ms.get("event", "move"),
                                    "vpW":     ms.get("vpW", 1280),
                                    "vpH":     ms.get("vpH", 800),
                                },
                                user_id,
                            )
                except Exception as exc:
                    logger.debug(f"Mouse event loop error for user {user_id}: {exc}")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.15)
                    break
                except asyncio.TimeoutError:
                    pass

        mouse_loop_task = asyncio.create_task(_mouse_event_loop())

        # ── Main capture loop ─────────────────────────────────────────────────────
        try:
            while not stop_event.is_set():
                try:
                    ws_url = await _get_page_ws_url()
                    if ws_url:
                        b64 = await _take_screenshot(ws_url)
                        if b64:
                            await _broadcast_frame(b64)
                    # If no page yet, silently wait and retry next tick
                except Exception as exc:
                    logger.error(f"Error in raw-CDP frame capture for user {user_id}: {exc}")

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                    break
                except asyncio.TimeoutError:
                    pass
        finally:
            mouse_loop_task.cancel()
            try:
                await mouse_loop_task
            except asyncio.CancelledError:
                pass

        # ── Final frame after task completes ─────────────────────────────────────
        try:
            ws_url = await _get_page_ws_url()
            if ws_url:
                b64 = await _take_screenshot(ws_url)
                if b64:
                    # Delete the mouse state file so the final frame has no cursor dot
                    try:
                        Path(f"/tmp/agent_mouse_{port}.json").unlink(missing_ok=True)
                    except Exception:
                        pass
                    await _broadcast_frame(b64)
                    logger.info(f"Sent final browser frame for user {user_id}")
        except Exception as exc:
            logger.debug(f"Could not send final frame for user {user_id}: {exc}")

    @staticmethod
    def _is_reset_intent(message: str) -> bool:
        """Return True if the message expresses an intent to start fresh / forget prior work."""
        lower = message.lower().strip()
        _RESET_PATTERNS = [
            "start over", "start fresh", "start again", "start from scratch",
            "go back to the beginning", "reset", "forget what you did",
            "forget everything", "clear the session", "new task",
            "ignore what you did", "scratch that", "discard previous",
            "discard what you did", "begin again", "wipe the slate",
        ]
        return any(pat in lower for pat in _RESET_PATTERNS)

    @staticmethod
    def _is_credential_override_intent(message: str) -> bool:
        """Return True if the message signals the user wants to swap the
        account/credential being used, rather than continue with whatever was
        confirmed earlier in the conversation.

        This is a best-effort heuristic used to add a stronger directive to
        Agent 1 (Input Understanding) so it does not silently reuse stale
        credentials from `history_context` — the model is always told the
        current message wins on conflicts, but this flag makes that explicit
        for the common "switch account" phrasing so it isn't left to chance.
        """
        lower = message.lower().strip()
        _OVERRIDE_PATTERNS = [
            "different account", "another account", "other account",
            "new account", "switch account", "switch accounts",
            "different email", "another email", "different username",
            "another username", "different login", "another login",
            "different credentials", "new credentials", "not that account",
            "wrong account", "use this account instead", "use this email instead",
            "instead use", "actually use", "actually, use", "try a different",
            "try another account", "not that email", "wrong email",
        ]
        return any(pat in lower for pat in _OVERRIDE_PATTERNS)

    @staticmethod
    def _redact_confirmed_inputs(confirmed_inputs: Dict[str, Any]) -> Dict[str, str]:
        """Return a version of confirmed_inputs safe to write to durable
        storage (AgentExecutionLog, ChatSession.session_state).

        User-provided account/credential data must never be persisted to
        disk — only kept in memory for as long as the current run needs it.
        Every value is replaced with a redaction marker; only the field
        names are kept so logs/audits can still show *what kind* of input
        was used (e.g. "email", "password") without ever storing the value
        itself.
        """
        if not confirmed_inputs:
            return {}
        return {k: "[REDACTED]" for k in confirmed_inputs.keys()}

    # ── Generic secret-value redaction (Task #118) ──────────────────────────
    # Sensitive values (passwords, OTP/verification codes, card/CVV numbers,
    # PINs, etc.) must never reach ANY durable table — not just the
    # confirmed_inputs blanket redaction above, but also free-text fields
    # like Message.content and ToolExecutionLog.tool_input/tool_output. The
    # helpers below detect likely-sensitive field names generically (rather
    # than hardcoding one field) and scrub known secret values out of
    # arbitrary text before it is persisted.

    _SENSITIVE_KEY_PATTERN = re.compile(
        r"password|passwd|pwd|(?:^|[-_ ])otp(?:[-_ ]|$)|one[-_ ]?time[-_ ]?(?:code|pin|password)"
        r"|verification[-_ ]?code|security[-_ ]?code|auth(?:entication)?[-_ ]?code"
        r"|(?:^|[-_ ])cvv(?:[-_ ]|$)|(?:^|[-_ ])cvc(?:[-_ ]|$)|card[-_ ]?(?:number|num)"
        r"|(?:^|[-_ ])pin(?:[-_ ]|$)|(?:^|[-_ ])ssn(?:[-_ ]|$)|\bsecret\b|\btoken\b",
        re.IGNORECASE,
    )

    _LABELED_SECRET_PATTERN = re.compile(
        r"(password|passwd|pwd|otp|one[-_ ]?time[-_ ]?(?:code|pin|password)|"
        r"verification[-_ ]?code|security[-_ ]?code|auth(?:entication)?[-_ ]?code|"
        r"cvv|cvc|card[-_ ]?(?:number|num)|pin|ssn)\s*[:=]\s*(\S+)",
        re.IGNORECASE,
    )

    OBSTACLE_ANSWER_PLACEHOLDER_TEMPLATE = "[REDACTED — {label} value provided, not stored]"

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        """Return True if a confirmed_input field name looks like it holds a
        password/OTP/card-style secret rather than an ordinary task detail."""
        return bool(key) and bool(cls._SENSITIVE_KEY_PATTERN.search(str(key)))

    @classmethod
    def _extract_sensitive_values(cls, confirmed_inputs: Optional[Dict[str, Any]]) -> List[str]:
        """Pull out the literal values of any sensitive-looking fields from a
        confirmed_inputs dict, so they can be scrubbed out of free-text logs
        wherever they appear (not just the field they were originally
        collected under)."""
        if not confirmed_inputs:
            return []
        values = []
        for k, v in confirmed_inputs.items():
            if v and cls._is_sensitive_key(k):
                values.append(str(v))
        return values

    @staticmethod
    def _redact_secret_values_in_text(text: Any, secret_values: List[str]) -> Any:
        """Replace every literal occurrence of a known secret value inside
        text with a redaction marker. Non-string input is returned as-is.
        Values shorter than 3 chars are skipped to avoid mass-redacting
        common short substrings by accident."""
        if not isinstance(text, str) or not secret_values:
            return text
        scrubbed = text
        for val in sorted({v for v in secret_values if v and len(v) >= 3}, key=len, reverse=True):
            if val in scrubbed:
                scrubbed = scrubbed.replace(val, "[REDACTED]")
        return scrubbed

    @classmethod
    def _mask_labeled_secrets(cls, text: str) -> str:
        """Best-effort scrub of free-text chat messages for the common
        'Label: value' disclosure pattern (e.g. 'password: hunter2',
        'CVV: 123'), used as defense-in-depth before ANY user message is
        persisted — independent of whether we already know this turn is
        answering an obstacle/credential form."""
        if not text:
            return text
        return cls._LABELED_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}: [REDACTED]", text)

    def _extract_domain_from_task(self, user_message: str, confirmed_inputs: Dict[str, Any]) -> str:
        """Extract primary domain from confirmed inputs or raw message."""
        # Try confirmed inputs first
        for key in ("website", "url", "site"):
            val = confirmed_inputs.get(key, "")
            if val:
                return MemoryService.extract_domain(str(val))
        # Fall back to scanning the user message for a URL/domain
        return MemoryService.extract_domain(user_message)

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates the cost of an LLM call based on OpenRouter pricing (approximate)."""
        # Pricing per 1M tokens (approximate for Gemini 3 Flash Preview)
        prices = {
            "google/gemini-3-flash-preview": {"input": 0.1, "output": 0.4},
            "moonshotai/kimi-k2.7-code": {"input": 0.5, "output": 1.5},
            "default": {"input": 0.1, "output": 0.4}
        }
        
        p = prices.get(model, prices["default"])
        cost = (input_tokens / 1_000_000 * p["input"]) + (output_tokens / 1_000_000 * p["output"])
        return round(cost, 6)

    async def _execute_tool_graph(self, graph_input: Dict[str, Any], tools: List[BaseTool], user_id: str, chat_id: str, task_summary: str, confirmed_inputs: Dict[str, Any], update_ui_func=None, memory_block: str = "", obstacle_answer: Optional[str] = None) -> Dict[str, Any]:
        """Executes a LangGraph tool-calling graph for the given input and tools."""

        # `tools` is the LIVE, MCP-discovered tool list for this session (see
        # get_tools() at the call sites) — never a hardcoded list. It is
        # filtered through browser.agent.md's `tool_filter` glob pattern
        # before binding, so adding a new MCP server automatically makes its
        # tools available here whenever the pattern matches (default "*" =
        # every discovered tool), with zero code changes.
        browser_spec = spec_loader.load_spec("browser")
        filtered_tools = spec_loader.filter_tools(tools, browser_spec.tool_filter)

        # Bind tools to the LLM
        llm_with_tools = self.llm.bind_tools(filtered_tools)

        # Build the static system message ONCE per execution — never rebuilt per step.
        # The 20-section prompt (~2500 tokens) is identical on every call, so Google
        # Gemini's implicit prefix cache hits it after the first step.
        static_sys_msg = SystemMessage(content=_build_browser_static_prompt())

        # Domain for the current run (used by CAPTCHA outcome tracking below)
        _task_domain = self._extract_domain_from_task(task_summary, confirmed_inputs)

        # Mutable dict shared across _call_tool invocations to track the last detected
        # CAPTCHA so we can evaluate whether it was bypassed on the next observation.
        # Shape when set: {"captcha_type": str, "skill_name": str}
        _captcha_state: Dict[str, Any] = {}

        # Known secret values for THIS run (sensitive confirmed_inputs fields +
        # any obstacle answer, e.g. an OTP code, just submitted) — scrubbed out
        # of ToolExecutionLog rows before they're persisted. The LLM still sees
        # the real values in `observation`/`llm_observation` below; only the
        # durable-storage copy is redacted.
        _run_secret_values: List[str] = self._extract_sensitive_values(confirmed_inputs)
        if obstacle_answer:
            _run_secret_values.append(str(obstacle_answer))

        # Define the logic for the agent node
        async def call_model(state: AgentState):
            messages = state["messages"]
            execution_history = state.get("execution_history", [])
            
            # Build small dynamic context (~200 tokens) — task + memory only.
            # The 20-section static prompt lives in static_sys_msg and is never rebuilt.
            memory_summary = ""
            if execution_history:
                memory_summary = "\nEXECUTION MEMORY (What happened so far):\n"
                for entry in execution_history:
                    status_text = "SUCCESS" if entry["status"] == "SUCCESS" else "FAILED"
                    memory_summary += f"- {status_text} {entry['tool']}: {entry['result'][:100]}...\n"

            memory_prefix = f"{memory_block}\n\n---\n\n" if memory_block else ""
            dynamic_context = (
                f"{memory_prefix}"
                f"TASK: {task_summary}\n"
                f"CONFIRMED INPUTS: {json.dumps(confirmed_inputs)}"
                f"{memory_summary}"
            )

            # --- DEAD CODE MARKER START (kept for grep reference only) ---
            # system_message_content f-string removed; static prompt is built by _build_browser_static_prompt() from browser.agent.md
            # --- DEAD CODE MARKER END ---

            # Strip any stale SystemMessages from LangGraph state, then prepend the
            # cached static system message.  Inject dynamic context as a prefix on the
            # LAST HumanMessage so the current task description is always adjacent to
            # the mission objective that was just submitted.  Injecting into raw_messages[0]
            # (the oldest message) caused the context to overwrite the first message while
            # leaving the new mission objective unmodified at the end of the chain.
            raw_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            last_human_idx = next(
                (i for i in range(len(raw_messages) - 1, -1, -1)
                 if isinstance(raw_messages[i], HumanMessage)),
                None
            )
            if last_human_idx is not None:
                raw_messages[last_human_idx] = HumanMessage(
                    content=f"## TASK CONTEXT\n{dynamic_context}\n\n---\n\n{raw_messages[last_human_idx].content}"
                )
            current_messages = [static_sys_msg] + raw_messages

            # Token Management & Summarization (80% Rule)
            full_text = "".join([m.content for m in current_messages if isinstance(m.content, str)])
            estimated_tokens = self.atag_processor._estimate_tokens(full_text)

            if estimated_tokens > 600000:
                logger.info(f"Token count ({estimated_tokens}) exceeded limit. Summarizing history...")
                summary = await self.atag_processor.summarize_context(execution_history, "History summarized due to token limit.")
                summary_msg = HumanMessage(content=f"SUMMARY OF PREVIOUS ACTIONS:\n{summary}")
                new_history = [static_sys_msg, summary_msg]
                if isinstance(current_messages[-1], HumanMessage):
                    new_history.append(current_messages[-1])
                current_messages = new_history
                logger.info("Conversation history summarized and compressed.")

            response = await llm_with_tools.ainvoke(current_messages)

            # Guard: if the model wrote a pending-action statement but produced no tool call,
            # re-invoke once with a nudge so the graph doesn't terminate prematurely.
            if not response.tool_calls and response.content:
                _pending_patterns = [
                    r"\bI will now\b", r"\bI'll now\b", r"\bI am going to\b",
                    r"\bI'm going to\b", r"\bLet me now\b", r"\bNext[,\s]+I will\b",
                    r"\bI should now\b", r"\bI need to\b", r"\bI'll select\b",
                    r"\bI'll click\b", r"\bI'll type\b", r"\bI'll navigate\b",
                ]
                if any(re.search(p, response.content, re.IGNORECASE) for p in _pending_patterns):
                    logger.info("Detected incomplete-action response (no tool call). Re-invoking with nudge.")
                    _nudge = HumanMessage(
                        content="You described an action you intend to take but did not call any tool. "
                                "Please call the appropriate browser tool NOW to execute that action."
                    )
                    response = await llm_with_tools.ainvoke(current_messages + [response, _nudge])

            # Capture token usage and cost
            token_usage = {}
            cost = 0.0
            if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
                usage = response.response_metadata["token_usage"]
                token_usage = {
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0)
                }
                cost = self._calculate_cost(self.llm.model_name, token_usage["input"], token_usage["output"])
                token_usage["cost"] = cost

            # Broadcast thinking to UI
            if response.content:
                # Clean up any leaked internal tool markers (common in some OpenRouter models)
                clean_content = re.sub(r"<｜tool▁.*?｜>", "", response.content)
                clean_content = re.sub(r"MMMM+.*", "", clean_content).strip()
                
                # Broadcast condensed, markdown-free reasoning to UI
                if self.stream_manager and clean_content:
                    # Strip THOUGHT:/INSTRUCTION: markers
                    thought_text = re.sub(r"(?i)^THOUGHT\s*:\s*", "", clean_content.strip())
                    thought_text = re.sub(r"(?i)\bINSTRUCTION\s*:.*$", "", thought_text, flags=re.DOTALL).strip()
                    # Strip markdown formatting characters so the UI renders clean prose
                    thought_text = re.sub(r"#{1,6}\s+", "", thought_text)           # headers
                    thought_text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", thought_text)  # bold/italic
                    thought_text = re.sub(r"_{1,2}([^_\n]+)_{1,2}", r"\1", thought_text)    # underscores
                    thought_text = re.sub(r"`{1,3}[^`\n]*`{1,3}", "", thought_text)         # code spans
                    thought_text = re.sub(r"^[-*+]\s+", "", thought_text, flags=re.MULTILINE) # bullets
                    thought_text = re.sub(r"^\d+\.\s+", "", thought_text, flags=re.MULTILINE) # numbered lists
                    # Collapse blank lines and cap at 6 lines
                    lines = [l.rstrip() for l in thought_text.splitlines() if l.strip()]
                    thought_text = "\n".join(lines[:6]).strip()
                    if thought_text:
                        await self.stream_manager.broadcast_thought(chat_id, thought_text)
                
                if clean_content:
                    # Update Task 2 Details (Main Chat)
                    if update_ui_func:
                        await update_ui_func(1, "in-progress", details=clean_content, token_usage=token_usage, cost=cost)
                
            return {"messages": [response]}

        # Define the function to carry out tool interactions
        async def _call_tool(state: AgentState):
            tool_map = {tool.name: tool for tool in filtered_tools}
            last_message = state["messages"][-1]
            execution_history = state.get("execution_history", [])
            
            new_messages = []
            for tool_call in last_message.tool_calls:
                tool = tool_map.get(tool_call["name"])
                
                # 1. Buffer + broadcast tool START to UI
                _tool_start_event = {
                    "type": "tool_start",
                    "tool": tool_call["name"],
                    "args": tool_call["args"],
                    "tool_call_id": tool_call["id"],
                }
                self.buffer_tool_event(chat_id, _tool_start_event)
                if self.stream_manager:
                    await self.stream_manager.broadcast_frame(
                        json.dumps(_tool_start_event),
                        user_id,
                        is_tool=True
                    )

                if not tool:
                    observation = f"Error: Tool {tool_call['name']} not found."
                else:
                    try:
                        # Use tool args as-is — injecting chat_id breaks MCP browser tools
                        # that have strict schemas (browser_get_state, browser_screenshot, etc.)
                        tool_args = tool_call["args"]
                        
                        # 2. Execute the actual tool (Playwright or Tavily) SEQUENTIALLY
                        observation = await tool.ainvoke(tool_args)

                        # --- Sanitize Replit proxy / network error pages ------
                        # When Chrome navigates to an unreachable URL, Replit's
                        # reverse-proxy serves its own HTML error page.  That raw
                        # HTML must never reach the LLM as-is; replace it with a
                        # clean, actionable error so the agent can recover.
                        observation = _sanitize_browser_observation(observation, tool_call)

                    except Exception as e:
                        observation = f"Error executing tool: {str(e)}"

                # ── CAPTCHA outcome evaluation ────────────────────────────────────────
                # Delegated to Brain._evaluate_captcha_outcome for testability.
                await self._evaluate_captcha_outcome(
                    _captcha_state, observation, user_id, _task_domain
                )

                # ── CAPTCHA detection (runs after try/except, observation always set) ──
                try:
                    _captcha_type = _detect_captcha(str(observation))
                    if _captcha_type and self.memory_service:
                        _skill = await self.memory_service.get_captcha_skill(user_id, _captcha_type)
                        if _skill:
                            _steps_txt = json.dumps(_skill.get("steps", []), indent=2)[:1200]
                            _captcha_note = (
                                f"\n\n[CAPTCHA_DETECTED: {_captcha_type}]\n"
                                f"A {_captcha_type} CAPTCHA is present on this page.\n"
                                f"Stored skill: {_skill.get('summary', '')}\n"
                                f"Steps to follow:\n{_steps_txt}\n"
                                f"Execute these steps now to bypass the CAPTCHA before continuing."
                            )
                            observation = str(observation) + _captcha_note
                            # Track this CAPTCHA so we can evaluate the outcome next turn
                            _captcha_state["pending"] = {
                                "captcha_type": _captcha_type,
                                "skill_name": f"captcha_{_captcha_type}",
                            }
                        else:
                            observation = str(observation) + (
                                f"\n\n[CAPTCHA_DETECTED: {_captcha_type}]\n"
                                f"No stored skill found — attempt manual bypass."
                            )
                except Exception as _ce:
                    logger.warning(f"CAPTCHA detection error (non-fatal): {_ce}")

                # ── Obstacle detection (generic framework) — human-input types like OTP ──
                # CAPTCHA is handled above (agent attempts to self-solve). Obstacles that
                # can only be resolved by a human (requires_human_input=True) pause the run
                # here so it can be surfaced via the NEEDS_INPUT form and resumed later.
                try:
                    if not _captcha_type:
                        _obstacle = detect_obstacle(str(observation))
                        if _obstacle and _obstacle.requires_human_input:
                            if self.memory_service:
                                try:
                                    # Remember that this site/flow uses this obstacle type so
                                    # future runs recognize and pause on it immediately. This
                                    # never stores the code/secret itself — only that the
                                    # pattern exists on this domain.
                                    await self.memory_service._update_procedural(
                                        user_id, _obstacle.skill_name, _task_domain, [], success=True,
                                    )
                                except Exception:
                                    pass
                            raise ObstacleInputNeeded(_obstacle, _task_domain)
                except ObstacleInputNeeded:
                    raise
                except Exception as _oe:
                    logger.warning(f"Obstacle detection error (non-fatal): {_oe}")

                status = "SUCCESS" if "Error" not in str(observation) else "FAILED"

                # Clean observation for logs (remove large base64 data)
                clean_obs = re.sub(r'\[SCREENSHOT\].*?\[/SCREENSHOT\]', '[Image Data]', str(observation), flags=re.DOTALL)

                # Scrub any known secret values (passwords, OTP codes, card/CVV, etc.)
                # out of BOTH the tool args and the observation text before they are
                # persisted to ToolExecutionLog. Tool args can be a dict of typed
                # field->value pairs (e.g. {"selector": ..., "text": "123456"}) — scrub
                # every string value, not just ones under a "sensitive-looking" key,
                # since a generic "text"/"value" arg is exactly how a password or OTP
                # gets typed into a form field.
                _safe_tool_input = tool_call["args"]
                if _run_secret_values and isinstance(_safe_tool_input, dict):
                    _safe_tool_input = {
                        k: self._redact_secret_values_in_text(v, _run_secret_values)
                        for k, v in _safe_tool_input.items()
                    }
                _safe_tool_output = self._redact_secret_values_in_text(clean_obs[:1000], _run_secret_values)

                # 3. Log the REAL result to DB
                await self.db_manager.log_tool_execution(
                    chat_id=chat_id,
                    agent_id="3",
                    tool_name=tool_call["name"],
                    status=status,
                    tool_input=_safe_tool_input,
                    tool_output=_safe_tool_output # Increased limit but kept clean
                )

                # --- NEW: Truncate observation for LLM history to prevent token overflow ---
                llm_observation = str(observation)
                if len(llm_observation) > 30000:
                    llm_observation = llm_observation[:30000] + "... [TRUNCATED DUE TO SIZE TO PREVENT CRASH]"

                # --- NEW: Explicit cleanup if browser was closed ---
                if tool_call["name"] in ["browser_close_session", "browser_close_all"] and status == "SUCCESS":
                    logger.info(f"Browser closed by tool call. Cleaning up session for user {user_id}")
                    session_obj = self.session_manager.get_session(user_id)
                    if session_obj.get("mcp_manager"):
                        # Don't await close here to avoid deadlock if we're inside a tool call, 
                        # but mark it as None so it's not reused.
                        session_obj["mcp_manager"] = None
                
                # 4. Buffer + broadcast tool OUTPUT to UI
                _tool_out_event = {
                    "type": "tool_output",
                    "tool": tool_call["name"],
                    "output": clean_obs[:500],
                    "tool_call_id": tool_call["id"],
                    "status": status,
                }
                self.buffer_tool_event(chat_id, _tool_out_event)
                if self.stream_manager:
                    await self.stream_manager.broadcast_frame(
                        json.dumps(_tool_out_event),
                        user_id,
                        is_tool=True
                    )
                
                new_messages.append(ToolMessage(content=llm_observation, tool_call_id=tool_call["id"]))
                execution_history.append({"tool": tool_call["name"], "status": status, "result": llm_observation[:500]})
            
            return {"messages": new_messages, "execution_history": execution_history}

        # Define the graph
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", _call_tool)

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            lambda x: "tools" if x["messages"][-1].tool_calls else END,
            {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "agent")

        app = workflow.compile(checkpointer=self.checkpointer)
        
        try:
            # Execute the graph with a thread_id for persistence
            config = {"configurable": {"thread_id": chat_id}}
            final_state = await app.ainvoke(graph_input, config=config)
            return final_state
        finally:
            pass

    async def process_chat_message(
        self,
        user_message_content: str,
        user_id: str,
        chat_id: str,
        
    ) -> str:
        """Adapts request parameters to run inside the stateful Multi-Agent Workflow."""
        if not self.initialized:
            await self.initialize()

        # Create a task for the message processing to allow cancellation
        task = asyncio.create_task(self.process_message(user_id, user_message_content, chat_id))
        self.active_tasks[chat_id] = task
        
        try:
            result = await task
        except asyncio.CancelledError:
            logger.info(f"Task for chat_id {chat_id} was cancelled.")
            return json.dumps({"status": "CANCELLED", "message": "Process stopped by user."})
        finally:
            self.active_tasks.pop(chat_id, None)
        
        if isinstance(result, dict):
            # If ATAG returned NEEDS_INPUT, return the form
            if result.get("status") == "NEEDS_INPUT":
                return json.dumps({"status": "NEEDS_INPUT", "form": result.get("form")})
            return result.get("execution_result") or result.get("message") or "Agent completed with no summary."
        return str(result)

    async def stop_process(self, chat_id: str, user_id: str = None):
        """Stops an active agent process and closes the browser (without destroying the session)."""
        # Mark as cancelled so process_message exits at its next checkpoint
        self.cancelled_chats.add(chat_id)

        task = self.active_tasks.get(chat_id)
        if task:
            task.cancel()
            logger.info(f"Cancellation signal sent to task for chat_id {chat_id}")
            self.active_tasks.pop(chat_id, None)

            # Clear the stale plan so reconnecting clients don't rehydrate a "running" plan
            self.active_plans.pop(chat_id, None)

            # Close the browser process but keep the session alive for reuse
            if user_id:
                try:
                    await self.session_manager.close_browser(user_id)
                    logger.info(f"Browser closed for user {user_id} via stop_process.")
                except Exception as e:
                    logger.warning(f"Browser close error during stop: {e}")

            return True
        # Even if no active task found, flag was set (guards stale tasks)
        # Also clear stale plan so reconnect doesn't rehydrate it
        self.active_plans.pop(chat_id, None)
        return False

    async def process_message(self, user_id: str, user_message: str, chat_id: str) -> Dict[str, Any]:
        """
        Runs Agent 1 (Analysis) -> Agent 2 (Strategy) -> Agent 3 (Execution) with UI updates and Critic retries.
        """
        # --- NEW: Limit parallel tasks per user ---
        if self.session_manager.get_active_count(user_id) >= 2:
            return {
                "success": False, 
                "message": "You have reached the limit of 2 parallel automation tasks. Please wait for one to finish."
            }
        
        self.session_manager.add_active_chat(user_id, chat_id)

        current_plan = [
            {"id": "1", "title": "Task 1: Analysis", "description": "Understanding user intent", "status": "pending", "priority": "high", "level": 0, "dependencies": [], "subtasks": [], "details": None},
            {"id": "2", "title": "Task 2: Execution", "description": "Running browser tools", "status": "pending", "priority": "high", "level": 0, "dependencies": ["1"], "subtasks": [], "details": None}
        ]

        async def update_ui(idx, status, input_data=None, output_data=None, error=None, details=None, token_usage=None, cost=None):
            # Ensure idx is within bounds of current_plan
            if idx < len(current_plan):
                current_plan[idx]["status"] = status
                if details:
                    current_plan[idx]["details"] = details
                
                if token_usage:
                    current_plan[idx]["token_usage"] = token_usage
                
                stage_name = current_plan[idx]["title"]
            else:
                stage_name = f"Stage {idx + 1}"
            
            await self.db_manager.log_agent_execution(
                user_id=user_id,
                chat_id=chat_id,
                stage=str(idx + 1),
                name=stage_name,
                status=status.upper(),
                input_data=input_data,
                output_data=output_data,
                error=error,
                token_usage=token_usage,
                cost=cost
            )
            if self.stream_manager:
                await self.stream_manager.broadcast_plan(chat_id, current_plan)
            
            # Store for rehydration
            self.active_plans[chat_id] = current_plan

        try:
            if not self.initialized: await self.initialize()
            session = await self.db_manager.get_or_create_chat_session(user_id, chat_id)
            
            # Initialize stream variables to None for finally block safety
            stop_stream = None
            stream_task = None
            
            # --- NEW: Fetch Chat History for Context ---
            prior_session_state: dict = {}
            async with AsyncSessionLocal() as db:
                stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
                res = await db.execute(stmt)
                history_msgs = res.scalars().all()
                
                # Convert DB messages to LangChain format
                chat_history = []
                for m in history_msgs:
                    if m.role == "user":
                        chat_history.append(HumanMessage(content=m.content))
                    else:
                        chat_history.append(AIMessage(content=m.content))

                # Load persisted session state (what the agent accomplished last turn)
                sess_stmt = select(ChatSession).where(ChatSession.id == chat_id)
                sess_res = await db.execute(sess_stmt)
                sess_row = sess_res.scalar_one_or_none()
                if sess_row and sess_row.session_state:
                    try:
                        prior_session_state = json.loads(sess_row.session_state)
                    except Exception:
                        prior_session_state = {}

                # --- Reset-intent detection ---
                # If the user wants to start fresh, wipe the prior session state so
                # the agent does not inherit the previous URL / accomplishment summary.
                if prior_session_state and self._is_reset_intent(user_message):
                    prior_session_state = {}
                    if sess_row:
                        sess_row.session_state = None
                        await db.commit()
                    logger.info(f"[brain] Reset intent detected for chat {chat_id} — session_state cleared.")

                # ── Obstacle resume check ───────────────────────────────────────
                # If the previous turn paused mid-run for human input (e.g. an OTP
                # code), this message is that answer — resume the paused run
                # instead of treating it as a brand-new task.
                pending_obstacle = prior_session_state.pop("pending_obstacle", None) if prior_session_state else None
                _obstacle_attempt_count = (pending_obstacle or {}).get("attempt", 0)

                # Add current message to DB — but never persist the raw value if this
                # message is directly answering an obstacle form (OTP/verification
                # code, etc.): those values are single-use/expire and must never be
                # readable from chat history, or a later turn's Agent-1 pass can
                # mistake a stale code sitting in history_context for a still-valid
                # credential and try to reuse it instead of asking for a fresh one.
                if pending_obstacle:
                    _obstacle_label = pending_obstacle.get("obstacle_type", "verification")
                    _stored_content = self.OBSTACLE_ANSWER_PLACEHOLDER_TEMPLATE.format(label=_obstacle_label)
                else:
                    # Defense-in-depth: scrub any explicit "label: value" secret
                    # disclosures (password/OTP/card/etc.) even outside the obstacle
                    # flow, e.g. when a credential-input form answer is typed back.
                    _stored_content = self._mask_labeled_secrets(user_message)
                human_msg = Message(
                    message_id=str(uuid.uuid4()),
                    chat_id=chat_id,
                    user_id=user_id,
                    role="user",
                    content=_stored_content,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(human_msg)
                await db.commit()

            graph_output: Dict[str, Any] = {}   # ensure exists for finally write-back
            memory_block = ""

            if pending_obstacle:
                # Resuming a run that paused for human input (e.g. an OTP code) —
                # skip Agent 1 entirely and reuse the task context captured when
                # the run paused, so the user's answer isn't misread as a new task.
                #
                # The real confirmed_inputs (account/credential values) were never
                # written to the database — only an in-memory cache and a redacted
                # placeholder in session_state. If the cache is gone (e.g. the
                # process restarted while paused), we deliberately do NOT fall back
                # to the redacted placeholder; instead we drop out of the resume
                # path and let the normal Agent-1 flow ask the user again.
                _cached_inputs = self.pending_confirmed_inputs.pop(chat_id, None)
                if _cached_inputs is None:
                    logger.info(
                        f"[brain] No in-memory credential cache for chat {chat_id} on resume "
                        f"(process likely restarted) — asking the user again instead of using "
                        f"the redacted placeholder."
                    )
                    pending_obstacle = None

            if pending_obstacle:
                task_summary = pending_obstacle["task_summary"]
                confirmed_inputs = _cached_inputs
                discovery_strategy = pending_obstacle.get("discovery_strategy", "direct_execution")
                domain = pending_obstacle.get("site_domain") or self._extract_domain_from_task(task_summary, confirmed_inputs)
                await update_ui(0, "completed", details="Resuming after obstacle input was provided.")
                if self.memory_service:
                    try:
                        mem_ctx = await self.memory_service.retrieve(user_id, domain, task_summary)
                        memory_block = mem_ctx.to_prompt_block()
                    except Exception as _me:
                        logger.warning(f"[Memory] retrieve error (non-fatal): {_me}")
            else:
                # --- Agent 1: Analysis (Now with history context) ---
                # Mask any explicit "label: value" secret disclosures before this
                # goes into AgentExecutionLog — same defense-in-depth as the
                # Message.content scrub above.
                await update_ui(0, "in-progress", input_data={"message": self._mask_labeled_secrets(user_message)})

                # Construct a context string from history for Agent 1
                history_context = "\n".join([f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in chat_history[-5:]])
                # Append prior browser state so the analysis agent knows what was already done
                if prior_session_state:
                    history_context += (
                        f"\n\nPREVIOUS SESSION STATE: The agent previously completed: "
                        f"{prior_session_state.get('accomplishment_summary', '')} "
                        f"The browser is currently on: {prior_session_state.get('last_url', 'unknown page')}."
                    )
                override_intent = self._is_credential_override_intent(user_message)
                if override_intent:
                    logger.info(f"[brain] Credential override intent detected for chat {chat_id} — instructing Agent 1 to ignore stale history values.")
                understanding = await self.atag_processor.run_input_understanding(
                    user_message, history_context=history_context, override_intent=override_intent
                )

                if understanding.get("status") == "NEEDS_INPUT":
                    form_data = understanding.get("form")
                    await update_ui(0, "completed", output_data=understanding, details=f"Missing critical inputs. Form requested.")

                    # Save the NEEDS_INPUT message to DB with form data
                    async with AsyncSessionLocal() as db:
                        ai_msg = Message(
                            message_id=str(uuid.uuid4()),
                            chat_id=chat_id,
                            user_id=user_id,
                            role="ai",
                            content=form_data.get("description", "I need more information to proceed."),
                            form_data=json.dumps(form_data),
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(ai_msg)
                        await db.commit()

                    return {"status": "NEEDS_INPUT", "form": form_data}

                task_summary = understanding.get("task_summary", "Processing...")
                confirmed_inputs = understanding.get("confirmed_inputs", {})
                discovery_strategy = understanding.get("discovery_strategy", "direct_execution")

                # Retroactively scrub the just-stored Message.content using the
                # ground-truth sensitive values Agent-1 itself extracted into
                # confirmed_inputs (e.g. password/card fields). This catches free-
                # text disclosures the label:value regex above can't reliably parse
                # (e.g. "use hunter2 as the password") without guessing at secret
                # detection ourselves — we trust Agent-1's own field extraction.
                _post_understanding_secrets = self._extract_sensitive_values(confirmed_inputs)
                if _post_understanding_secrets and any(v in _stored_content for v in _post_understanding_secrets if v):
                    _redacted_stored_content = self._redact_secret_values_in_text(_stored_content, _post_understanding_secrets)
                    async with AsyncSessionLocal() as db:
                        upd_stmt = select(Message).where(Message.message_id == human_msg.message_id)
                        upd_res = await db.execute(upd_stmt)
                        upd_row = upd_res.scalar_one_or_none()
                        if upd_row:
                            upd_row.content = _redacted_stored_content
                            await db.commit()

                # ── Memory routing: extract domain + retrieve relevant memories ──
                domain = self._extract_domain_from_task(user_message, confirmed_inputs)
                if self.memory_service:
                    try:
                        mem_ctx = await self.memory_service.retrieve(user_id, domain, task_summary)
                        memory_block = mem_ctx.to_prompt_block()
                        if memory_block:
                            logger.info(f"[Memory] Injecting {len(memory_block)} chars for domain '{domain}'")
                    except Exception as _me:
                        logger.warning(f"[Memory] retrieve error (non-fatal): {_me}")

                await update_ui(
                    0,
                    "completed",
                    output_data={**understanding, "confirmed_inputs": self._redact_confirmed_inputs(confirmed_inputs)},
                    details=f"Task Summary: {task_summary}",
                )
                # --- NEW: Update Session Title based on Task Summary ---
                async with AsyncSessionLocal() as db:
                    stmt = select(ChatSession).where(ChatSession.id == chat_id)
                    res = await db.execute(stmt)
                    session_db = res.scalar_one_or_none()
                    if session_db and (session_db.title == "New Chat" or len(session_db.title) < 5):
                        session_db.title = task_summary[:100]
                        await db.commit()
            # --- Agent 2: Execution (with Retries & AI Thinking) ---
            retry_count = 0
            max_retries = 3
            last_error = None
            obstacle_paused = False
            final_response = None
            all_tool_calls = [] # Track all tool calls for saving to DB

            # 1. Get the user's private session
            session_obj = self.session_manager.get_session(user_id)
            user_port = session_obj.get("port")
            
            # 2. Initialize MCP manager — create fresh if missing OR if previous init failed
            existing_mgr = session_obj.get("mcp_manager")
            if existing_mgr and not getattr(existing_mgr, "_initialized", False):
                # Previous init failed — close the dead manager and replace it
                logger.info(f"Replacing dead MCP manager for user {user_id} (prev _initialized=False)...")
                try:
                    await existing_mgr.close()
                except Exception:
                    pass
                session_obj["mcp_manager"] = None

            # Pre-flight proxy check — verify the proxy is reachable and show exit IP
            _proxy_url_preflight = session_obj.get("proxy_url")
            if _proxy_url_preflight:
                from urllib.parse import urlparse as _pf_up, urlunparse as _pf_uu
                def _mask_proxy(url: str) -> str:
                    try:
                        _p = _pf_up(url)
                        if _p.password:
                            netloc = f"{_p.username}:***@{_p.hostname}"
                            if _p.port:
                                netloc += f":{_p.port}"
                            return _pf_uu((_p.scheme, netloc, _p.path, _p.params, _p.query, _p.fragment))
                    except Exception:
                        pass
                    return url

                try:
                    async with httpx.AsyncClient(proxy=_proxy_url_preflight, timeout=config.PROXY_TEST_TIMEOUT_SECONDS) as _pc:
                        _ip_resp = await _pc.get(config.IP_CHECK_URL)
                    _ip_resp.raise_for_status()
                    _exit_ip = _ip_resp.json().get("ip")
                    if not _exit_ip:
                        raise ValueError("No IP in ipify response")
                    logger.info(f"Proxy pre-flight OK for user {user_id} — exit IP: {_exit_ip}")
                    if self.stream_manager:
                        await self.stream_manager.broadcast_thought(
                            chat_id,
                            f"Proxy active — exit IP: {_exit_ip}",
                        )
                except Exception as _proxy_err:
                    logger.warning(
                        f"Proxy pre-flight failed for user {user_id} "
                        f"({_mask_proxy(_proxy_url_preflight)}): {_proxy_err}. "
                        "Falling back to direct connection."
                    )
                    if self.stream_manager:
                        await self.stream_manager.broadcast_thought(
                            chat_id,
                            f"Proxy unreachable. Falling back to direct datacenter connection.",
                        )
                    # Clear proxy and close any existing manager so this run uses a direct connection
                    session_obj["proxy_url"] = None
                    _dead_mgr = session_obj.get("mcp_manager")
                    if _dead_mgr:
                        try:
                            await _dead_mgr.close()
                        except Exception:
                            pass
                        session_obj["mcp_manager"] = None

            if not session_obj.get("mcp_manager"):
                logger.info(f"Preparing MCP manager for user {user_id} on port {user_port}...")
                ua_index = session_obj.get("ua_index", 0)
                user_cdp_url = session_obj.get("cdp_url")  # set when user connects their own browser
                user_proxy_url = session_obj.get("proxy_url")  # residential proxy URL
                user_browser_engine = session_obj.get("browser_engine")  # None if not explicitly set; MCPToolManager falls back to env then "camoufox"
                if user_cdp_url:
                    logger.info(f"Using user-provided CDP URL for {user_id}: {user_cdp_url}")
                    session_obj["mcp_manager"] = MCPToolManager(
                        cdp_url=user_cdp_url,
                        user_agent_index=ua_index,
                        own_browser=False,
                        proxy_url=user_proxy_url,
                        browser_engine=user_browser_engine,
                    )
                else:
                    session_obj["mcp_manager"] = MCPToolManager(port=user_port, user_agent_index=ua_index, proxy_url=user_proxy_url, browser_engine=user_browser_engine)

            mcp_manager = session_obj["mcp_manager"]
            
            # 3. Discover tools ONCE outside the retry loop to save time
            # If user's external browser is unreachable, fall back to cloud browser automatically.
            try:
                all_tools = await mcp_manager.get_tools()
            except Exception as _cdp_err:
                user_cdp_url = session_obj.get("cdp_url")
                if user_cdp_url:
                    logger.warning(
                        f"External CDP browser at {user_cdp_url} is unreachable ({_cdp_err}). "
                        "Clearing CDP URL and falling back to cloud browser."
                    )
                    # Broadcast fallback notice to UI
                    if self.stream_manager:
                        await self.stream_manager.broadcast_thought(
                            chat_id,
                            "Your connected browser appears to be offline. Falling back to the cloud browser for this run.",
                        )
                    session_obj["cdp_url"] = None
                    try:
                        await mcp_manager.close()
                    except Exception:
                        pass
                    session_obj["mcp_manager"] = MCPToolManager(port=user_port, user_agent_index=session_obj.get("ua_index", 0), proxy_url=session_obj.get("proxy_url"), browser_engine=session_obj.get("browser_engine"))
                    mcp_manager = session_obj["mcp_manager"]
                    all_tools = await mcp_manager.get_tools()
                else:
                    raise
            if self.search_tool: 
                all_tools = list(all_tools) + [self.search_tool]
            
            logger.info(f"Discovered {len(all_tools)} tools for execution.")

            # Check whether the bridge fell back from Camoufox to Chrome and notify the user
            _fallback_flag = Path(f"/tmp/camoufox_fallback_{user_port}.json")
            if _fallback_flag.exists():
                _fallback_reason = None
                try:
                    _fallback_data = json.loads(_fallback_flag.read_text())
                    _fallback_reason = (_fallback_data.get("reason") or "").strip() or None
                except Exception:
                    pass
                try:
                    _fallback_flag.unlink()
                except Exception:
                    pass
                logger.warning(
                    f"[brain] Camoufox → Chrome fallback detected for user {user_id}, "
                    f"notifying chat {chat_id} (reason: {_fallback_reason or 'unknown'})"
                )
                if self.stream_manager:
                    _reason_suffix = f" ({_fallback_reason})" if _fallback_reason else ""
                    await self.stream_manager.broadcast_notification(
                        chat_id,
                        "camoufox_fallback",
                        (
                            "Stealth browser (Camoufox) couldn't start"
                            f"{_reason_suffix}, so this run automatically switched to "
                            "regular headless Chrome instead. Bot-detection evasion may be "
                            "reduced for this run — change the default engine anytime in Settings."
                        ),
                    )

            # Start direct-CDP screenshot stream (no MCP tools needed)
            self.clear_live_tool_logs(chat_id)  # fresh slate for this execution
            stop_stream = asyncio.Event()
            stream_task = asyncio.create_task(self._stream_browser_frames(user_id, chat_id, stop_stream))

            # Set on the first retry-loop iteration if this run is resuming from an
            # obstacle answer (e.g. an OTP code) — threaded into _execute_tool_graph
            # so it can scrub the raw value out of ToolExecutionLog rows. Initialized
            # here so it's always defined at the _execute_tool_graph call site below,
            # regardless of which branch (resume vs. fresh) executes on a given retry.
            _otp_answer_for_redaction: Optional[str] = None

            while retry_count < max_retries:
                # --- Cooperative cancellation: exit cleanly if user pressed Stop ---
                if chat_id in self.cancelled_chats:
                    self.cancelled_chats.discard(chat_id)
                    logger.info(f"[Cooperative cancel] Exiting process loop for chat_id {chat_id}")
                    raise asyncio.CancelledError("Stopped by user")

                try:
                    await update_ui(1, "in-progress", input_data={"task_summary": task_summary, "confirmed_inputs": self._redact_confirmed_inputs(confirmed_inputs), "retry": retry_count})
                    
                    # --- Execution via MCP Tool Graph (Standardized) ---
                    logger.info(f"Executing via MCP Tool Graph (Attempt {retry_count + 1})...")
                    
                    # 1. Generate the mission objective (with prior browser state if available)
                    prior_context_str = ""
                    if prior_session_state:
                        prior_context_str = (
                            "## CURRENT BROWSER STATE\n"
                            f"The agent has already completed: {prior_session_state.get('accomplishment_summary', '')}\n"
                            f"The browser is currently on: {prior_session_state.get('last_url', 'unknown page')}\n"
                            "IMPORTANT: Continue from this state. Do NOT re-navigate to the start URL or redo "
                            "steps that have already been completed. Pick up exactly where the previous "
                            "message left off."
                        )
                    reasoning = ""
                    plan_data = []

                    if pending_obstacle and retry_count == 0:
                        # Resuming after the user answered an obstacle prompt (e.g. an
                        # OTP code) — feed their answer straight into the graph instead
                        # of re-planning from scratch.
                        _otp_answer = _extract_form_answer(user_message)
                        _otp_answer_for_redaction = _otp_answer
                        mission_objective = (
                            f"The user was asked for a '{pending_obstacle.get('obstacle_type', 'verification')}' "
                            f"and responded: '{_otp_answer}'. Enter this into the corresponding field on the "
                            f"current page (e.g. the verification/OTP code field) and submit/continue. "
                            f"Then proceed with the original task: {task_summary}."
                        )
                        pending_obstacle = None  # only bypass planning on this first resumed attempt
                    else:
                        mission_objective = await self.atag_processor.run_execution_generation(
                            user_message, task_summary, confirmed_inputs, discovery_strategy,
                            prior_context=prior_context_str
                        )

                    if "REASONING:" in mission_objective and "PLAN:" in mission_objective:
                        try:
                            parts = re.split(r"REASONING:|PLAN:|MISSION OBJECTIVE:", mission_objective)
                            if len(parts) >= 4:
                                reasoning = parts[1].strip()
                                plan_str = parts[2].strip()
                                mission_objective = parts[3].strip()
                                
                                json_match = re.search(r"\[.*\]", plan_str, re.DOTALL)
                                if json_match:
                                    plan_data = json.loads(json_match.group(0))
                                    # --- FIX: Ensure unique IDs to prevent React key warnings ---
                                    # We re-index the plan starting from 2 (since Analysis is 1)
                                    for i, task in enumerate(plan_data):
                                        task["id"] = str(i + 2)
                                    current_plan = [current_plan[0]] + plan_data
                                    if self.stream_manager:
                                        await self.stream_manager.broadcast_plan(chat_id, current_plan)
                        except Exception as e:
                            logger.error(f"Failed to parse reasoning/plan: {e}")

                    # Update UI to show we are starting execution
                    if len(current_plan) > 1:
                        await update_ui(1, "in-progress", details="Executing mission steps via MCP...")

                    # 2. Execute via MCP Tool Graph
                    graph_input = {"messages": [HumanMessage(content=mission_objective)]}
                    graph_output = await self._execute_tool_graph(
                        graph_input, all_tools, user_id, chat_id, task_summary, confirmed_inputs, update_ui_func=update_ui, memory_block=memory_block,
                        obstacle_answer=_otp_answer_for_redaction
                    )
                    
                    # Capture tool calls from the graph execution — this list is
                    # persisted verbatim to Message.tool_calls below, so it must go
                    # through the exact same value-based secret scrub as
                    # ToolExecutionLog (sensitive confirmed_inputs values + the
                    # current obstacle answer), or a typed password/OTP surfaces in
                    # the messages table even though ToolExecutionLog is clean.
                    if "execution_history" in graph_output:
                        _msg_secret_values = self._extract_sensitive_values(confirmed_inputs)
                        if _otp_answer_for_redaction:
                            _msg_secret_values.append(str(_otp_answer_for_redaction))
                        for entry in graph_output["execution_history"]:
                            all_tool_calls.append({
                                "id": str(uuid.uuid4()),
                                "tool_name": entry["tool"],
                                "tool_input": {}, # Input is not easily available here, but we have the result
                                "tool_output": self._redact_secret_values_in_text(entry["result"][:1000], _msg_secret_values),
                                "status": entry["status"],
                                "created_at": datetime.now(timezone.utc).isoformat()
                            })

                    final_msg = graph_output["messages"][-1].content
                    if "Error" not in final_msg and "failed" not in final_msg.lower():
                        final_response = final_msg
                        # Mark all steps as completed
                        for i in range(1, len(current_plan)):
                            await update_ui(i, "completed")
                        
                        await update_ui(1, "completed", output_data={"response": final_response}, details="Task completed successfully via MCP.")

                        # --- Persist session state for multi-turn continuity ---
                        try:
                            exec_history = graph_output.get("execution_history", [])
                            # Find the last URL from any navigation tool result
                            last_url = prior_session_state.get("last_url", "")
                            for entry in exec_history:
                                tool_name = entry.get("tool", "")
                                result_text = entry.get("result", "")
                                if tool_name in ("browser_navigate", "browser_go_back", "browser_go_forward") and result_text:
                                    # Extract URL from result text if present
                                    url_match = re.search(r'https?://[^\s\'"]+', result_text)
                                    if url_match:
                                        last_url = url_match.group(0).rstrip(".,)")
                            # Build a brief accomplishment summary from successful steps
                            success_steps = [
                                e["tool"] for e in exec_history if e.get("status") == "SUCCESS"
                            ]
                            accomplishment = f"{task_summary}. Steps completed: {', '.join(success_steps[:8])}."
                            new_session_state = {
                                "last_url": last_url,
                                "accomplishment_summary": accomplishment[:500],
                                "ts": datetime.now(timezone.utc).timestamp(),
                            }
                            async with AsyncSessionLocal() as db:
                                upd_stmt = select(ChatSession).where(ChatSession.id == chat_id)
                                upd_res = await db.execute(upd_stmt)
                                upd_row = upd_res.scalar_one_or_none()
                                if upd_row:
                                    upd_row.session_state = json.dumps(new_session_state)
                                    await db.commit()
                            logger.info(f"[SessionState] Saved for chat {chat_id}: url={last_url}")
                        except Exception as _ss_err:
                            logger.warning(f"[SessionState] save error (non-fatal): {_ss_err}")

                        break
                    else:
                        raise Exception(f"Execution failed: {final_msg}")

                except ObstacleInputNeeded as obstacle_exc:
                    # Track how many times this run has paused for human input — if the
                    # user's answer didn't resolve it and we hit the SAME obstacle again,
                    # stop asking forever and explain clearly instead.
                    _obstacle_attempt_count += 1
                    if _obstacle_attempt_count > 2:
                        logger.warning(
                            f"[Obstacle] '{obstacle_exc.match.skill_name}' on {obstacle_exc.site_domain} "
                            f"still unresolved after {_obstacle_attempt_count} attempts — giving up gracefully."
                        )
                        final_response = (
                            f"I got stuck on a {obstacle_exc.match.category} step on {obstacle_exc.site_domain} — "
                            f"the code you provided may not have worked, or the site needs a fresh one. Please "
                            f"try the task again with a new/rechecked code."
                        )
                        if self.memory_service:
                            try:
                                await self.memory_service._update_procedural(
                                    user_id, obstacle_exc.match.skill_name, obstacle_exc.site_domain, [], success=False,
                                )
                                await self.memory_service.store_reflection(
                                    user_id,
                                    obstacle_exc.site_domain,
                                    (
                                        f"Obstacle '{obstacle_exc.match.skill_name}' on {obstacle_exc.site_domain} "
                                        f"was not resolved after {_obstacle_attempt_count} user-provided answers."
                                    ),
                                    category="OTP" if obstacle_exc.match.category == "otp" else obstacle_exc.match.category.upper(),
                                    severity="MEDIUM",
                                )
                            except Exception:
                                pass
                        # No further resume will happen for this run — drop any
                        # cached credentials so they don't linger in memory.
                        self.pending_confirmed_inputs.pop(chat_id, None)
                        await update_ui(1, "failed", details=final_response)
                        break

                    form_data = build_input_form(obstacle_exc.match, obstacle_exc.site_domain)
                    await update_ui(1, "completed", details=f"Paused — needs {obstacle_exc.match.category} input from the user.")

                    # Keep the real account/credential values in memory ONLY for
                    # the resume step — they must never be written to the
                    # database. Only a redacted placeholder goes into
                    # session_state so a reader of the DB can see the run is
                    # paused without ever seeing the personal data involved.
                    self.pending_confirmed_inputs[chat_id] = confirmed_inputs
                    _pending_obstacle_state = {
                        "obstacle_type": obstacle_exc.match.obstacle_type,
                        "obstacle_category": obstacle_exc.match.category,
                        "skill_name": obstacle_exc.match.skill_name,
                        "site_domain": obstacle_exc.site_domain,
                        "task_summary": task_summary,
                        "confirmed_inputs": self._redact_confirmed_inputs(confirmed_inputs),
                        "discovery_strategy": discovery_strategy,
                        "attempt": _obstacle_attempt_count,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    async with AsyncSessionLocal() as db:
                        upd_stmt = select(ChatSession).where(ChatSession.id == chat_id)
                        upd_res = await db.execute(upd_stmt)
                        upd_row = upd_res.scalar_one_or_none()
                        if upd_row:
                            _existing_state = {}
                            if upd_row.session_state:
                                try:
                                    _existing_state = json.loads(upd_row.session_state)
                                except Exception:
                                    _existing_state = {}
                            _existing_state["pending_obstacle"] = _pending_obstacle_state
                            upd_row.session_state = json.dumps(_existing_state)
                            await db.commit()

                    async with AsyncSessionLocal() as db:
                        ai_msg = Message(
                            message_id=str(uuid.uuid4()),
                            chat_id=chat_id,
                            user_id=user_id,
                            role="ai",
                            content=form_data.get("description", "I need more information to proceed."),
                            form_data=json.dumps(form_data),
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(ai_msg)
                        await db.commit()

                    obstacle_paused = True
                    return {"status": "NEEDS_INPUT", "form": form_data}

                except Exception as e:
                    retry_count += 1
                    last_error = str(e)
                    logger.warning(f"Execution attempt {retry_count} failed: {last_error}")
                    
                    if retry_count < max_retries:
                        await update_ui(1, "in-progress", details=f"Attempt {retry_count} failed. Resetting browser with new identity and retrying…")

                        # --- Browser reset: close stale session, rotate user agent, reopen ---
                        logger.info(f"[Retry] Closing browser for user {user_id} before retry {retry_count + 1}...")
                        await self.session_manager.close_browser(user_id)

                        # Rotate user agent for the fresh browser so the site sees a different client
                        next_ua = (session_obj.get("ua_index", 0) + 1) % 5
                        session_obj["ua_index"] = next_ua
                        logger.info(f"[Retry] Starting fresh browser with user-agent index {next_ua}...")
                        session_obj["mcp_manager"] = MCPToolManager(port=user_port, user_agent_index=next_ua, proxy_url=session_obj.get("proxy_url"), browser_engine=session_obj.get("browser_engine"))
                        mcp_manager = session_obj["mcp_manager"]

                        # Re-discover tools from the fresh session
                        all_tools = await mcp_manager.get_tools()
                        if self.search_tool:
                            all_tools = list(all_tools) + [self.search_tool]

                        logger.info(f"Running Critic to revise strategy for attempt {retry_count + 1}...")
                        critic_input_message = f"The previous execution attempt failed with error: {last_error}. Please analyze the current page state and provide a refined strategy to achieve the goal: {task_summary}. Confirmed inputs: {json.dumps(confirmed_inputs)}"
                        revised_strategy = await self.atag_processor.run_critic(user_message, critic_input_message, last_error)
                        
                        initial_execution_message = HumanMessage(content=revised_strategy)
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"All {max_retries} attempts failed.")
                        await update_ui(1, "failed", error=last_error, details=f"All {max_retries} attempts failed. Last error: {last_error}")
                        final_response = f"I attempted the task {max_retries} times but encountered persistent errors. Last error: {last_error}"

            ai_msg_id = str(uuid.uuid4())
            # Ensure chat session row exists before inserting a message (FK guard)
            await self.db_manager.get_or_create_chat_session(user_id, chat_id)
            async with AsyncSessionLocal() as db:
                ai_msg = Message(
                    message_id=ai_msg_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    role="ai",
                    content=final_response,
                    plan_data=json.dumps(current_plan),
                    tool_calls=json.dumps(all_tool_calls),
                    created_at=datetime.now(timezone.utc)
                )
                db.add(ai_msg)
                await db.commit()

            return {
                "success": True,
                "execution_result": final_response,
                "plan": current_plan,
                "message": {
                    "id": ai_msg_id,
                    "log_id": str(uuid.uuid4()),
                    "role": "ai",
                    "content": final_response,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            
            # --- NEW: Unwrap ExceptionGroup (Python 3.11+) or TaskGroup errors ---
            error_detail = str(e)
            if "TaskGroup" in error_detail or "sub-exception" in error_detail:
                try:
                    # If it's a PEP 654 ExceptionGroup
                    if hasattr(e, 'exceptions') and e.exceptions:
                        error_detail = f"Multiple errors occurred: {', '.join([str(ex) for ex in e.exceptions])}"
                    # Fallback for anyio TaskGroup strings
                    elif "1 sub-exception" in error_detail:
                        logger.warning("Detected anyio TaskGroup error, attempting to extract root cause.")
                except:
                    pass

            # Ensure current_plan exists before using it
            if 'current_plan' in locals():
                await update_ui(len(current_plan) - 1, "failed", error=error_detail, details=f"Overall task failed: {error_detail}")
            return {"success": False, "message": f"An unexpected error occurred: {error_detail}"}
        finally:
            # Safely cleanup stream tasks if they were initialized.
            # IMPORTANT: give the stream task enough time to finish the final-frame
            # capture (which takes up to ~11 s: 3 s for CDP /json + 8 s for screenshot).
            # The old 1.0 s timeout killed the task before the results-page frame
            # could ever be sent, leaving the preview stuck on the first/homepage frame.
            if 'stop_stream' in locals() and stop_stream:
                stop_stream.set()
            if 'stream_task' in locals() and stream_task:
                try:
                    await asyncio.wait_for(stream_task, timeout=15.0)
                except Exception:
                    pass
            self.session_manager.remove_active_chat(user_id, chat_id)
            self.active_tasks.pop(chat_id, None)
            self.active_plans.pop(chat_id, None)
            # Always clear the cooperative-cancel flag so the next message in this
            # thread isn't immediately killed (handles the CancelledError path where
            # the discard above was never reached)
            self.cancelled_chats.discard(chat_id)

            # ── Memory write-back (non-fatal — never blocks cleanup) ──────────
            # Skip storing an episode when the run merely paused for obstacle input
            # (e.g. waiting on an OTP code) — it hasn't failed, it's still in flight.
            if self.memory_service and not ('obstacle_paused' in locals() and obstacle_paused):
                try:
                    _outcome = "FAIL"
                    if 'final_response' in locals() and final_response and \
                            "attempted the task" not in str(final_response) and \
                            "encountered persistent errors" not in str(final_response):
                        _outcome = "SUCCESS"
                    _compact_steps: List[Dict] = []
                    if 'graph_output' in locals() and isinstance(graph_output, dict):
                        for _e in graph_output.get("execution_history", []):
                            if _e.get("status") == "SUCCESS":
                                _compact_steps.append({"tool": _e.get("tool", "")})
                    _d = domain if 'domain' in locals() else "general"
                    _ts = task_summary if 'task_summary' in locals() else user_message[:200]
                    await self.memory_service.store_episode(
                        user_id=user_id,
                        domain=_d,
                        task_summary=_ts,
                        outcome=_outcome,
                        key_steps=_compact_steps,
                    )
                    await self.memory_service.apply_decay(user_id)
                    logger.info(f"[Memory] Stored {_outcome} episode for domain '{_d}'")
                except Exception as _mem_err:
                    logger.warning(f"[Memory] write-back error (non-fatal): {_mem_err}")

    async def _save_session_state(self, chat_id: str, updated_state: dict):
        """Safely commits processed state dictionaries back into short-lived database queries."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatSession).where(ChatSession.id == chat_id))
            session_db = result.scalar_one()
            session_db.state_data = serialize_state(updated_state)
            session_db.updated_at = datetime.utcnow()
            await db.commit()

    async def shutdown(self):
        """Shutdown helper invoked on lifespan exit."""
        await self.session_manager.shutdown_all()


# ============================================================
# INSTANTIATE GLOBAL EXPORTS FOR COMPATIBILITY
# ============================================================
brain = Brain()
agent_manager = brain # Export both for compatibility
