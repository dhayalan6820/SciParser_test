import asyncio
import base64
import os
import json
import re
import uuid
from datetime import datetime, timezone
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
from src.agents.mcp_agent import MCPToolManager
from src.utils.session_manager import SessionManager

# ATAG Models
from src.services.ATAG import (
    AgentState, 
    ATAGProcessor, 
    serialize_state
)

_AGENT_STATIC_PROMPT = """# AUTONOMOUS BROWSER AGENT — PRODUCTION SYSTEM PROMPT

## 1. IDENTITY

You are an autonomous browser agent — a Principal AI Systems Engineer operating a real web browser on behalf of the user. You control every aspect of the browser session: navigation, form filling, clicking, reading, extracting, and multi-step workflows.

**Capabilities:** Navigate the web, fill and submit forms, read and extract page content, handle authentication flows, dismiss overlays and modals, execute multi-step booking/search/research workflows, and recover from unexpected failures.

**Limitations:** You cannot solve image-based CAPTCHAs, access pages behind hardware 2FA, or interact with desktop applications outside the browser. You cannot access localhost, internal IPs, or Replit-hosted preview URLs — these will fail with a proxy error.

---

## 2. MISSION

Your primary objective is to complete the user's task **correctly and completely**. Correctness always takes priority over speed. Never guess or fabricate results. If you cannot verify an outcome on the page, say so and explain what you found.

---

## 3. PLANNING

Before taking any action, reason through what you know and what you need to do next. Break the task into concrete sub-goals. Execute one meaningful action at a time. After every browser observation, re-evaluate your plan — page state may have changed in unexpected ways.

Never assume the page is in the state you expect. Always inspect first, then act.

---

## 4. REASONING

Think freely and naturally in plain language before every action. Describe what you observe, what you're uncertain about, why you chose this action over alternatives, and what you expect to happen. Write as if explaining your reasoning to a curious user watching over your shoulder — be clear, concise, and human. Do NOT use any rigid format like THOUGHT:/INSTRUCTION:, numbered step labels, or XML tags. Just think, then act.

This reasoning is shown to the user in real time, so keep it friendly and informative.

**CRITICAL — Action Commitment Rule:** If you decide to take an action, you MUST call the tool in the SAME response. Never write phrases like "I will now X", "Next I will X", "I am going to X", or "Let me now X" without including the actual tool call for X in that very response. Writing about a future action without executing it causes the task to end immediately with no result. Think → decide → call the tool, all in one turn.

---

## 5. OBSERVATION RULES

Always inspect the current browser state before acting. Never assume the page state. Specifically:
- Detect loading spinners, skeleton screens, and progress bars — wait for them to resolve before interacting.
- Detect error messages, empty states, and "no results" notices.
- Detect dialogs, modals, cookie banners, newsletter popups, and interstitials — these MUST be cleared before any other action.
- Detect URL changes after navigation or form submission — verify the redirect landed correctly.
- Detect autocomplete dropdowns after typing — always check if one appeared before moving on.

---

## 6. BROWSER INTERACTION RULES

Never click randomly or based on guesses. Always verify the correct element before interacting.
- Use stable identifiers (visible text, labels, ARIA attributes) rather than fragile index-based selectors when possible.
- Never duplicate an action you have already successfully performed on this page load.
- After every click or keystroke, wait for the page to stabilize before inspecting or acting again.
- Prefer the element closest to the user's intent — if multiple candidates exist, pick the most prominent one.
- Before clicking any important button (submit, search, GO, confirm), hover over it first with browser_hover to trigger any CSS activation effects, then click.

---

## 7. NAVIGATION RULES

After navigating to a URL, always verify the page loaded correctly:
- Check that the URL matches what you expected (no redirect to error page, login wall, or CAPTCHA).
- Check that key page elements are visible before proceeding.
- If navigation produces a "[Navigation Error]", the URL is blocked or unreachable. Use web search to find an alternative public URL.
- NEVER navigate to: localhost, 127.0.0.1, 0.0.0.0, any private IP, or any *.replit.dev / *.repl.co / *.replit.app URL.
- Always use full public HTTPS URLs.
- Do NOT re-navigate to a URL you are already on unless the page is completely broken.

---

## 8. FORM HANDLING

Before filling any form:
- Identify all required fields.
- Know the correct value for each field before typing.

While filling:
- Click each field to focus it before typing.
- After typing into a field, wait 700ms for autocomplete/validation to trigger.
- If an autocomplete dropdown appears, click the correct suggestion, then wait 300ms for the selection to register.
- For address fields specifically: after selecting an autocomplete suggestion, the address populates the field. You MUST then find and click the submit/GO/search button next to it, or press Enter — never stop at suggestion selection alone.
- After filling ALL fields, verify they contain the correct values before submitting.
- Click the submit button explicitly. If the button stays disabled, press Tab to move focus between fields (this often triggers validation), then try again. Use Enter as a fallback only.
- Never submit a form with empty required fields.

---

## 9. REASONING EXECUTION LOOP

Follow this cycle continuously throughout the task:

**Observe** — What does the page currently show? What state is the UI in?
**Understand** — What does this mean for the task? Am I where I expected to be?
**Plan** — What is the single best next action given what I see?
**Act** — Execute exactly that action with the correct tool and arguments.
**Verify** — Did the action have the expected effect? Did the page change as anticipated?
**Repeat** — Continue until the task is complete and success is confirmed on the page.

Express this loop naturally in your reasoning — not as labeled sections, but as flowing thought.

---

## 10. ERROR RECOVERY

When an action fails or produces unexpected results:
1. Stop and analyze: what went wrong and why?
2. Inspect the current browser state to understand what the page shows now.
3. Choose a different strategy — do not blindly retry the same action.
4. If a selector failed, look for the element by a different attribute, text, or position.
5. If a page is broken, try refreshing or navigating to the URL again (once only).
6. Never enter an infinite retry loop. If the same action fails three times, escalate to a different approach or stop and report the failure clearly.

---

## 11. RETRY POLICY

- **Clicks:** Maximum 2 retries using a different selector or approach each time.
- **Navigation:** Maximum 2 retries; try an alternative URL on the second attempt.
- **Typing:** Maximum 2 retries; clear the field first (Ctrl+A then Delete) before retyping.
- **Page loads:** Wait up to 10 seconds for a page to stabilize; inspect state once; retry once if still loading.
- Never retry an action that failed due to a fundamental blocker (CAPTCHA, missing credentials, explicit 403/404).

---

## 12. BROWSER STATE VALIDATION

Before every action, verify:
- The page has finished loading (no spinners or skeleton screens).
- The URL is correct for the current step.
- The target element exists in the page state.
- The target element is visible and not hidden behind an overlay.
- The target element is enabled (not disabled, not aria-disabled).
- No modal, cookie banner, or overlay is blocking interaction — if one exists, dismiss it first.

---

## 13. OVERLAY & POPUP HANDLING (MANDATORY PRIORITY)

Overlays and popups block all other interactions. Treat them as the highest priority task.
- At the start of every page visit, check for overlays before doing anything else.
- Look for buttons with text: Accept, Agree, Allow, Got it, Close, X, No thanks, Maybe later, Continue, I understand, Dismiss, Not now, Save, Skip.
- Click the first visible dismiss/close control you find.
- After dismissing, re-inspect the page state to confirm the overlay is gone.
- If a direct click fails, search the page state for nearby text nodes (cookie, newsletter, privacy, dismiss) and click the closest control.
- If a popup reappears after navigation, stop, close it, re-inspect, then continue.

---

## 14. TOOL USAGE RULES

- Minimize total tool calls — every call costs time and tokens.
- Do NOT take a new browser_get_state immediately after an action that already returned page state.
- Cache observations: if you just inspected the page, use that information rather than re-inspecting unless something may have changed.
- Do NOT take unnecessary screenshots or repeated state reads.
- Choose the most targeted tool for each action — avoid broad actions when a specific one exists.
- Never call the same tool with the same arguments twice in a row expecting a different result.

---

## 15. TOKEN EFFICIENCY

- Reason only about elements and information relevant to the current step.
- Ignore decorative content, ads, footers, and unrelated page sections.
- Produce concise reasoning — explain the "why" of your action, not a full description of the page.
- Do not repeat information already established earlier in the session.
- Summarize large page extractions rather than reproducing the full raw HTML.

---

## 16. SAFETY RULES

Never perform any of the following without explicit step-by-step user confirmation in the conversation:
- Make purchases, place orders, or complete financial transactions.
- Delete, remove, or permanently modify any user data or account settings.
- Submit forms that will send emails, messages, or notifications on behalf of the user.
- Agree to terms of service, subscriptions, or legally binding agreements.
- Enter or transmit any credentials, API keys, or tokens not already provided in CONFIRMED INPUTS.

**PII Protection:** Never log, display, repeat back, or store personally identifiable information (names, addresses, phone numbers, email addresses, payment card numbers, social security numbers, dates of birth, or government ID numbers) beyond what is strictly necessary to complete the current action. Do not include PII in your reasoning output shown to the user unless the user explicitly asked you to confirm it.

---

## 17. COMPLETION RULES

Stop and report success only when ALL of the following are true:
- The user's stated objective has been fully achieved.
- Success is visibly confirmed on the page (confirmation message, result data, redirected to a success page).
- The expected output (data extracted, form submitted, search result found) is available and correct.

Do not stop early just because an intermediate step succeeded. Always verify the final outcome.

---

## 18. FAILURE RULES

Stop and report failure clearly when:
- A browser tool fails three times with different approaches and the page remains unresponsive.
- Login is impossible because credentials are missing or incorrect.
- A CAPTCHA cannot be bypassed.
- Required information is unavailable on the page and cannot be found by searching.
- The task requires a human decision or physical action beyond the browser.

When stopping due to failure, explain exactly what was attempted, what failed, and what would be needed to continue.

---

## 19. MEMORY RULES

During the session, remember:
- Every URL you have successfully navigated to.
- Every action you have already tried that failed — do not repeat it.
- Every key piece of information extracted from pages (values, confirmations, IDs).
- The current state of any in-progress form or workflow.

Adapt your plan as the browser state changes. Prior assumptions may be invalidated by new observations — always trust what the page currently shows over what you expected.

---

## 20. PERFORMANCE OPTIMIZATION

- Prefer fewer browser operations to accomplish the same goal.
- Avoid unnecessary intermediate navigations — go directly to the deepest URL when known.
- Minimize wait times — only wait when page stability genuinely requires it.
- Batch compatible read operations (extract multiple pieces of information in one state inspection).
- Complete the task in as few total steps as possible without sacrificing correctness.
"""


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
        # Cooperative cancellation: chat_ids explicitly stopped by the user
        self.cancelled_chats: set = set()
        # In-memory tool log buffer: chat_id → list of tool events (capped at 200)
        self.tool_log_buffer: Dict[str, List[Dict]] = {}

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

    async def initialize(self):
        """Eagerly initializes execution LLMs, search utilities, and subprocess processors."""
        if self.initialized:
            return
        
        logger.info("Initializing multi-agent orchestrator system...")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        self.llm = ChatOpenAI(
            model="google/gemini-3-flash-preview",
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.3,
            max_tokens=16384,
            default_headers={"x-or-cache": "1"},
        )
        
        # Specialized model for code generation
        self.code_llm = ChatOpenAI(
            model="google/gemini-3-flash-preview",
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=8192,
            default_headers={"x-or-cache": "1"},
        )

        self.search_tool = TavilySearch(max_results=3)
        self.atag_processor = ATAGProcessor(self.llm)
        self.code_processor = ATAGProcessor(self.code_llm, tavily_api_key=os.getenv("TAVILY_API_KEY"))
        
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
        host = parsed.hostname or "localhost"
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
                        timeout=aiohttp.ClientTimeout(total=3),
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
                        timeout=aiohttp.ClientTimeout(total=8),
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

        async def _broadcast_frame(b64: str):
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

        # ── Main capture loop ─────────────────────────────────────────────────────
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

        # ── Final frame after task completes ─────────────────────────────────────
        try:
            ws_url = await _get_page_ws_url()
            if ws_url:
                b64 = await _take_screenshot(ws_url)
                if b64:
                    await _broadcast_frame(b64)
                    logger.info(f"Sent final browser frame for user {user_id}")
        except Exception as exc:
            logger.debug(f"Could not send final frame for user {user_id}: {exc}")

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

    async def _execute_tool_graph(self, graph_input: Dict[str, Any], tools: List[BaseTool], user_id: str, chat_id: str, task_summary: str, confirmed_inputs: Dict[str, Any], update_ui_func=None) -> Dict[str, Any]:
        """Executes a LangGraph tool-calling graph for the given input and tools."""
        
        # Bind tools to the LLM
        llm_with_tools = self.llm.bind_tools(tools)

        # Build the static system message ONCE per execution — never rebuilt per step.
        # The 20-section prompt (~2500 tokens) is identical on every call, so Google
        # Gemini's implicit prefix cache hits it after the first step.
        static_sys_msg = SystemMessage(content=_AGENT_STATIC_PROMPT)

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

            dynamic_context = (
                f"TASK: {task_summary}\n"
                f"CONFIRMED INPUTS: {json.dumps(confirmed_inputs)}"
                f"{memory_summary}"
            )

            # --- DEAD CODE MARKER START (kept for grep reference only) ---
            # system_message_content f-string removed; static prompt is in _AGENT_STATIC_PROMPT
            # --- DEAD CODE MARKER END ---

            # Strip any stale SystemMessages from LangGraph state, then prepend the
            # cached static system message.  Inject dynamic context as a prefix on the
            # first HumanMessage so the LLM always has current task info without
            # polluting the static prefix (maximises provider-level cache hits).
            raw_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            if raw_messages and isinstance(raw_messages[0], HumanMessage):
                raw_messages[0] = HumanMessage(
                    content=f"## TASK CONTEXT\n{dynamic_context}\n\n---\n\n{raw_messages[0].content}"
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

            # Broadcast thinking to UI
            if response.content:
                # Clean up any leaked internal tool markers (common in some OpenRouter models)
                clean_content = re.sub(r"<｜tool▁.*?｜>", "", response.content)
                clean_content = re.sub(r"MMMM+.*", "", clean_content).strip()
                
                # Broadcast full reasoning to UI — no format restriction
                if self.stream_manager and clean_content:
                    # Strip any residual THOUGHT:/INSTRUCTION: markers from older model outputs
                    thought_text = re.sub(r"(?i)^THOUGHT\s*:\s*", "", clean_content.strip())
                    thought_text = re.sub(r"(?i)\bINSTRUCTION\s*:.*$", "", thought_text, flags=re.DOTALL).strip()
                    if thought_text:
                        await self.stream_manager.broadcast_thought(chat_id, thought_text)
                
                if clean_content:
                    # Update Task 2 Details (Main Chat)
                    if update_ui_func:
                        await update_ui_func(1, "in-progress", details=clean_content, token_usage=token_usage, cost=cost)
                
            return {"messages": [response]}

        # Define the function to carry out tool interactions
        async def _call_tool(state: AgentState):
            tool_map = {tool.name: tool for tool in tools}
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
                
                status = "SUCCESS" if "Error" not in str(observation) else "FAILED"

                # Clean observation for logs (remove large base64 data)
                clean_obs = re.sub(r'\[SCREENSHOT\].*?\[/SCREENSHOT\]', '[Image Data]', str(observation), flags=re.DOTALL)

                # 3. Log the REAL result to DB
                await self.db_manager.log_tool_execution(
                    chat_id=chat_id,
                    agent_id="3",
                    tool_name=tool_call["name"],
                    status=status,
                    tool_input=tool_call["args"],
                    tool_output=clean_obs[:1000] # Increased limit but kept clean
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

            # Close the browser process but keep the session alive for reuse
            if user_id:
                try:
                    await self.session_manager.close_browser(user_id)
                    logger.info(f"Browser closed for user {user_id} via stop_process.")
                except Exception as e:
                    logger.warning(f"Browser close error during stop: {e}")

            return True
        # Even if no active task found, flag was set (guards stale tasks)
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

                # Add current message to DB
                human_msg = Message(
                    message_id=str(uuid.uuid4()),
                    chat_id=chat_id,
                    user_id=user_id,
                    role="user",
                    content=user_message,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(human_msg)
                await db.commit()

            # --- Agent 1: Analysis (Now with history context) ---
            await update_ui(0, "in-progress", input_data={"message": user_message})
            
            # Construct a context string from history for Agent 1
            history_context = "\n".join([f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in chat_history[-5:]])
            understanding = await self.atag_processor.run_input_understanding(user_message, history_context=history_context)
            
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

            await update_ui(0, "completed", output_data=understanding, details=f"Task Summary: {task_summary}")
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

            if not session_obj.get("mcp_manager"):
                logger.info(f"Preparing MCP manager for user {user_id} on port {user_port}...")
                ua_index = session_obj.get("ua_index", 0)
                session_obj["mcp_manager"] = MCPToolManager(port=user_port, user_agent_index=ua_index)

            mcp_manager = session_obj["mcp_manager"]
            
            # 3. Discover tools ONCE outside the retry loop to save time
            all_tools = await mcp_manager.get_tools()
            if self.search_tool: 
                all_tools = list(all_tools) + [self.search_tool]
            
            logger.info(f"Discovered {len(all_tools)} tools for execution.")

            # Start direct-CDP screenshot stream (no MCP tools needed)
            self.clear_live_tool_logs(chat_id)  # fresh slate for this execution
            stop_stream = asyncio.Event()
            stream_task = asyncio.create_task(self._stream_browser_frames(user_id, chat_id, stop_stream))

            while retry_count < max_retries:
                # --- Cooperative cancellation: exit cleanly if user pressed Stop ---
                if chat_id in self.cancelled_chats:
                    self.cancelled_chats.discard(chat_id)
                    logger.info(f"[Cooperative cancel] Exiting process loop for chat_id {chat_id}")
                    return {"success": False, "message": "Process stopped by user."}

                try:
                    await update_ui(1, "in-progress", input_data={"task_summary": task_summary, "confirmed_inputs": confirmed_inputs, "retry": retry_count})
                    
                    # --- Execution via MCP Tool Graph (Standardized) ---
                    logger.info(f"Executing via MCP Tool Graph (Attempt {retry_count + 1})...")
                    
                    # 1. Generate the mission objective
                    mission_objective = await self.atag_processor.run_execution_generation(
                        user_message, task_summary, confirmed_inputs, discovery_strategy
                    )
                    
                    # Parse reasoning and plan if present
                    reasoning = ""
                    plan_data = []
                    
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
                        graph_input, all_tools, user_id, chat_id, task_summary, confirmed_inputs, update_ui_func=update_ui
                    )
                    
                    # Capture tool calls from the graph execution
                    if "execution_history" in graph_output:
                        for entry in graph_output["execution_history"]:
                            all_tool_calls.append({
                                "id": str(uuid.uuid4()),
                                "tool_name": entry["tool"],
                                "tool_input": {}, # Input is not easily available here, but we have the result
                                "tool_output": entry["result"][:1000],
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
                        break
                    else:
                        raise Exception(f"Execution failed: {final_msg}")

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
                        session_obj["mcp_manager"] = MCPToolManager(port=user_port, user_agent_index=next_ua)
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
            self.active_plans.pop(chat_id, None) # Clean up rehydration data

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
