import asyncio
import os
import uuid
import re
import traceback
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends import (
    CompositeBackend,
    FilesystemBackend,
    StateBackend,
)
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    ModelFallbackMiddleware,
)
from src.utils.logger import logger
from src.agents.mcp_agent import MCPToolManager
from src import config
from src.utils.session_manager import SessionManager
from src.database.chat_db import AsyncSessionLocal, Message, ChatSession, ToolExecutionLog, User, BudgetLimit, AlertNotification, AgentExecutionLog
from sqlalchemy import select, update
from src.services.tool_selector import ToolSelector
from langchain_core.tools import StructuredTool
from datetime import datetime, timezone
import json

class DatabaseManager:
    # Minimal stub just for main.py compatibility
    async def get_or_create_chat_session(self, user_id: str, chat_id: str):
        pass

def suggest_chat_title(message: str) -> str:
    if not message:
        return "New Chat"
    
    clean = message.strip()
    
    # 1. Extract domain from URL
    url_match = re.search(r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})', clean, re.IGNORECASE)
    domain = url_match.group(1) if url_match else ""
    
    # Remove URLs
    clean = re.sub(r'https?://[^\s]+', '', clean).strip()
    
    # 2. Clean prefixes
    clean = re.sub(r'^(please\s+)?(go\s+to|navigate\s+to|open\s+the|open|check\s+out|visit|browse)\s+', '', clean, flags=re.IGNORECASE)
    
    # 3. Clean transitions
    clean = re.sub(r'^(and\s+)?(the\s+|a\s+|an\s+)?', '', clean, flags=re.IGNORECASE)
    
    if domain:
        clean_action = re.sub(r'^[.,;:!?\s]+|[.,;:!?\s]+$', '', clean)
        if not clean_action or len(clean_action) < 3:
            return f"Browse — {domain}"
        
        action_str = clean_action[0].upper() + clean_action[1:]
        if len(action_str) > 35:
            action_str = action_str[:32] + "..."
        return f"{action_str} — {domain}"
    
    # 4. No domain, take first sentence or segment
    end_match = re.search(r'[.:;!?\n]', clean)
    if end_match:
        clean = clean[:end_match.start()]
    
    clean = clean.strip()
    if not clean:
        return "New Chat"
    
    title_str = clean[0].upper() + clean[1:]
    if len(title_str) > 45:
        title_str = title_str[:42] + "..."
    return title_str

class CodeProcessor:
    def __init__(self, llm):
        self.llm = llm

    async def run_script_generation(
        self,
        title: str,
        execution_history: list,
        framework: str,
        tool_context: list,
        user_goal: str,
        plan_context: str,
        user_id: str,
        chat_id: str,
        assistant_response: str = "",
    ) -> str:
        from langchain_core.messages import SystemMessage
        import json

        # Set contextvars so TokenTrackingCallbackHandler records the LLM call
        # with the correct user_id / chat_id in the LlmRequest table.
        token_user = current_user_id.set(user_id)
        token_chat = current_chat_id.set(chat_id)
        try:
            return await self._generate_script_inner(
                title, execution_history, framework, tool_context,
                user_goal, plan_context, user_id, chat_id, assistant_response,
            )
        finally:
            current_user_id.reset(token_user)
            current_chat_id.reset(token_chat)

    async def _generate_script_inner(
        self, title, execution_history, framework, tool_context,
        user_goal, plan_context, user_id, chat_id, assistant_response: str = "",
    ) -> str:
        from langchain_core.messages import SystemMessage
        import json

        # ── Build a navigation-only breadcrumb list from tool logs ──────────
        # We strip the actual OUTPUT values to prevent the LLM from copying
        # scraped data as hardcoded constants into the generated script.
        nav_breadcrumbs = []
        for item in execution_history:
            tool = item.get("tool") or item.get("tool_name") or ""
            inp  = item.get("input") or {}
            status = item.get("status") or ""
            # Include the tool name + inputs (URLs, selectors) but NOT the output
            crumb = {"tool": tool, "input": inp, "status": status}
            nav_breadcrumbs.append(crumb)

        # Also strip output from tool_context
        nav_tool_context = [
            {"tool_name": item.get("tool_name", ""),
             "input":     item.get("input", {}),
             "note": "output omitted -- extract live from site"}
            for item in (tool_context or [])
        ]

        prompt = f"""You are an expert Python automation engineer specializing in Playwright for web scraping.

        YOUR TASK:
        Generate a fully functional, self-contained Python script using ONLY Playwright to visit and extract data from a list of target URLs sequentially.
        The script MUST NOT use browser-use or any AI agent. It must extract details directly from the page using standard CSS selectors.

        The script must automate the following goal on a DAILY schedule. You MUST align it strictly with the user's initial goals and format the output fields exactly as agreed in the AI's final response:

        GOAL (User Requirements): {user_goal}
        TITLE: {title}
        """

        if assistant_response:
            prompt += f"""\nAI ASSISTANT RESPONSE (use this as reference for output fields & structure):
        {assistant_response}\n"""

        if plan_context:
            prompt += f"""\nAGENT EXECUTION PLAN (use this to understand WHAT to collect):
            {plan_context}\n"""

        if nav_breadcrumbs:
            breadcrumb_str = json.dumps(nav_breadcrumbs, indent=2)
            prompt += f"""\nNAVIGATION BREADCRUMBS (tool calls showing HOW the agent navigated -- NOT data to copy):
        {breadcrumb_str}\n"""

        if nav_tool_context:
            tc_str = json.dumps(nav_tool_context, indent=2)
            prompt += f"""\nTOOL CONTEXT (navigation inputs and outputs showing exactly what was extracted and which CSS selectors correspond to each data field):
        {tc_str}\n"""

        prompt += """
        ==============================================================
        HOW TO USE CONTEXT DATA:
        - Navigation breadcrumbs = MAP of how the agent explored the site.
            Use the visited URLs to build TARGET_URLS.
        - Tool Context (especially outputs with `*_selector` properties) = Selector map showing exactly where the plan details are located in the DOM. Use these exact selectors in your Playwright locators.
        - DO NOT copy any values from outputs -- the script fetches FRESH data
            on every daily run.

        CRITICAL RULES -- VIOLATIONS WILL BREAK DAILY AUTOMATION:
        1. NEVER hardcode any prices, package names, plan details, speeds, fees,
            contract terms, or any other scraped values into the script.
        2. NEVER write static lists/dicts pre-filled with website data.
        3. ALL output values must be extracted LIVE at runtime.
        4. URLs from navigation breadcrumbs MAY be hardcoded as TARGET_URLS.
            That is the ONLY thing you may hardcode.
        5. Wrap every page interaction and extraction in try/except for robustness.
        6. NEVER use Unicode characters (arrows, em-dashes, etc.) in print()
            statements -- use only ASCII (e.g. -> instead of the arrow symbol).
        7. Stick STRICTLY to the user goal and the structure shown in the AI Assistant Response.
            Do NOT create any extra categories, include unsanctioned attributes, or make out-of-the-box assumptions.
        8. Write a clean, high-performance Playwright script. Execute inputs (e.g., typing address details, selecting inputs, clicking buttons) sequentially to reach the correct page state before attempting extraction.

        ==============================================================
        REQUIRED CODE STRUCTURE (Playwright only):

        ```
        import asyncio
        import json
        import os
        import sys
        from dotenv import load_dotenv
        from playwright.async_api import async_playwright

        load_dotenv()

        # Force UTF-8 stdout on Windows to avoid encoding errors
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        # -- Configuration ----------------------------------------------------------
        TARGET_URLS = [
            # Fill with actual URLs from navigation breadcrumbs
        ]

        async def playwright_extract(page, url: str) -> list[dict]:
            results = []
            try:
                # 1. Navigate to target URL
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2000)
                
                # 2. Perform any interactive steps (typing addresses, clicking search availability, form submits) 
                # required to see the plans, matching the user goal and navigation history.
                # E.g.
                # await page.fill("input[placeholder='Enter address']", "1017 Franklin St, Poplar Bluff, MO 63901")
                # await page.click(".suggestion-item")
                # await page.click("button#check-availability")
                # await page.wait_for_selector("your_selector")
                
                # 3. Extract the target plans/details using the exact CSS selectors 
                # (found in the tool_context *_selector fields)
                # E.g.
                # plans = await page.locator("your_plan_card_selector").all()
                # for plan in plans:
                #     name = await plan.locator("your_name_selector").inner_text()
                #     price = await plan.locator("your_price_selector").inner_text()
                #     results.append({"name": name.strip(), "price": price.strip()})
                pass
            except Exception as e:
                print(f"  [Playwright] Error on {url}: {e}")
            return results

        async def run():
            cdp_url = os.environ.get("BROWSER_CDP_URL")
            all_results = []

            async with async_playwright() as p:
                if cdp_url:
                    print(f"Connecting Playwright over CDP: {cdp_url}")
                    browser = await p.chromium.connect_over_cdp(cdp_url)
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                else:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    )
                
                page = await context.new_page()

                for url in TARGET_URLS:
                    print(f"\\n[Playwright] Scraping: {url}")
                    pw_results = await playwright_extract(page, url)
                    print(f"  -> Playwright found {len(pw_results)} item(s)")
                    all_results.extend(pw_results)

                await page.close()
                if not cdp_url:
                    await browser.close()

            print("\\n=== FINAL EXTRACTED DATA ===")
            print(json.dumps(all_results, indent=2))

        if __name__ == "__main__":
            asyncio.run(run())
        ```

        INSTRUCTIONS:
        1. Output ONLY the raw Python code. Do NOT wrap in markdown code blocks.
        2. Start directly with `import asyncio` -- no preamble text.
        3. Populate TARGET_URLS with actual URLs from navigation breadcrumbs.
        4. Implement custom, robust Playwright interaction steps to mimic user address input/checking availability.
        5. Extract fields strictly using Playwright locators based on the live CSS selectors from tool_context.
"""

        try:
            resp = await self.llm.ainvoke([SystemMessage(content=prompt)])
            code = resp.content.strip()
            # Clean up markdown code blocks if the LLM outputted them despite instructions
            if code.startswith("```python"):
                code = code.split("```python", 1)[-1]
            elif code.startswith("```"):
                code = code.split("```", 1)[-1]
            if code.endswith("```"):
                code = code.rsplit("```", 1)[0]
            code = code.strip()
            
            # Anti-hallucination fix for OpenRouter base URL & Model Prefix:
            code = code.replace('"https://api.openai.com/v1"', '"https://openrouter.ai/api/v1"')
            code = code.replace("'https://api.openai.com/v1'", "'https://openrouter.ai/api/v1'")
            code = code.replace('"gemini-3.1-flash-lite"', '"google/gemini-3.1-flash-lite"')
            code = code.replace("'gemini-3.1-flash-lite'", "'google/gemini-3.1-flash-lite'")
            # If the LLM already wrote openai/openai/gpt-4o-mini, fix it:
            code = code.replace('"openai/openai/', '"openai/')
            code = code.replace("'openai/openai/", "'openai/")
            
            return code
        except Exception as e:
            logger.error(f"Failed to generate automated script: {e}")
            return f"# Error generating automated script: {e}"

def get_model_pricing(model_name: str) -> tuple[float, float]:
    """Returns (input_cost_per_million, output_cost_per_million) for the given model."""
    name = model_name.lower()
    
    # Check Admin Config First
    if "brain" in globals():
        b = globals()["brain"]
        if hasattr(b, "admin_llm_config") and b.admin_llm_config:
            if name == b.admin_llm_config.get("model_name", "").lower():
                return b.admin_llm_config.get("input_cost", 0.1), b.admin_llm_config.get("output_cost", 0.4)
                
    if "gemini-3.5-flash" in name or "gemini-3-flash" in name or "gemini-3-flash-preview" in name:
        return 0.50, 3.50
    elif "gemini-1.5-pro" in name or "gemini-3-pro" in name:
        return 1.25, 5.00
    elif "gpt-4o-mini" in name:
        return 0.15, 0.60
    elif "gpt-4o" in name:
        return 2.50, 10.00
    elif "google/gemini-3.1-flash-lite" in name:
        return 0.25, 1.50
    elif "claude-3-haiku" in name:
        return 0.25, 1.25
    elif "minimax-m3" in name:
        return 0.30, 1.20
    elif "gpt-5.1-codex-mini" in name:
        return 0.20, 0.80
    # Default fallback to config settings
    from src import config
    return getattr(config, "LLM_INPUT_COST_PER_MILLION", 0.1), getattr(config, "LLM_OUTPUT_COST_PER_MILLION", 0.4)

import contextvars

current_user_id = contextvars.ContextVar("current_user_id", default="system")
current_chat_id = contextvars.ContextVar("current_chat_id", default=None)
current_agent_run_id = contextvars.ContextVar("current_agent_run_id", default=None)


from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

import time

class TokenTrackingCallbackHandler(AsyncCallbackHandler):
    def __init__(self, llm_instance):
        self.llm_instance = llm_instance
        self.start_times = {}

    async def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id, **kwargs: Any) -> None:
        self.start_times[run_id] = time.time()

    async def on_llm_end(self, response: LLMResult, *, run_id, **kwargs: Any) -> None:
        try:
            for generations in response.generations:
                for gen in generations:
                    message = getattr(gen, "message", None)
                    if not message:
                        continue
                    
                    prompt_tokens, completion_tokens = 0, 0
                    meta = getattr(message, "usage_metadata", None)
                    if meta and isinstance(meta, dict):
                        prompt_tokens = meta.get("input_tokens", 0) or 0
                        completion_tokens = meta.get("output_tokens", 0) or 0
                    else:
                        rm = getattr(message, "response_metadata", None) or {}
                        tu = rm.get("token_usage") or {}
                        if tu:
                            prompt_tokens = tu.get("prompt_tokens", 0) or 0
                            completion_tokens = tu.get("completion_tokens", 0) or 0
                    
                    if prompt_tokens == 0 and completion_tokens == 0:
                        content = getattr(message, "content", "")
                        if isinstance(content, str):
                            completion_tokens = len(content) // 4
                    
                    input_rate, output_rate = get_model_pricing(self.llm_instance.model_name)
                    cost = (prompt_tokens * input_rate + completion_tokens * output_rate) / 1000000.0
                    
                    # Accumulate
                    object.__setattr__(self.llm_instance, "accumulated_prompt_tokens", self.llm_instance.accumulated_prompt_tokens + prompt_tokens)
                    object.__setattr__(self.llm_instance, "accumulated_completion_tokens", self.llm_instance.accumulated_completion_tokens + completion_tokens)
                    object.__setattr__(self.llm_instance, "accumulated_cost", self.llm_instance.accumulated_cost + cost)
                    
                    # Write to database
                    from src.utils.llm_instrumentation import count_message_tokens, record_llm_request
                    user_id = current_user_id.get() or "system"
                    chat_id = current_chat_id.get()
                    agent_run_id = current_agent_run_id.get()
                    
                    category_tokens = {
                        "system_tokens": int(prompt_tokens * 0.20),
                        "user_tokens": int(prompt_tokens * 0.30),
                        "history_tokens": int(prompt_tokens * 0.50),
                    }
                    
                    start_time = self.start_times.pop(run_id, None)
                    latency_ms = int((time.time() - start_time) * 1000) if start_time else 0

                    await record_llm_request(
                        user_id=user_id,
                        chat_id=chat_id,
                        model=self.llm_instance.model_name,
                        source="chat" if chat_id else "system",
                        category_tokens=category_tokens,
                        input_tokens=prompt_tokens,
                        output_tokens=completion_tokens,
                        cost_usd=cost,
                        latency_ms=latency_ms
                    )
                    
                    # Output for subprocess parsing
                    print(f"[TOKEN_USAGE] {{\"prompt_tokens\": {prompt_tokens}, \"completion_tokens\": {completion_tokens}, \"model\": \"{self.llm_instance.model_name}\", \"user_id\": \"{user_id}\", \"chat_id\": \"{chat_id or ''}\", \"cost\": {cost}}}")
        except Exception as e:
            logger.warning(f"Error in TokenTrackingCallbackHandler: {e}")


class MemoryPruningLLM(ChatOpenRouter):
    accumulated_prompt_tokens: int = 0
    accumulated_completion_tokens: int = 0
    accumulated_cost: float = 0.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_accumulator()
        self.callbacks = [TokenTrackingCallbackHandler(self)]

    def reset_accumulator(self):
        object.__setattr__(self, "accumulated_prompt_tokens", 0)
        object.__setattr__(self, "accumulated_completion_tokens", 0)
        object.__setattr__(self, "accumulated_cost", 0.0)

    def _prune_messages(self, messages: Any) -> Any:
        if not isinstance(messages, list):
            return messages
        
        last_tool_idx = -1
        for idx, msg in enumerate(messages):
            if isinstance(msg, ToolMessage) or (hasattr(msg, "type") and msg.type == "tool"):
                last_tool_idx = idx
                
        pruned_msgs = []
        for idx, msg in enumerate(messages):
            if (isinstance(msg, ToolMessage) or (hasattr(msg, "type") and msg.type == "tool")) and idx != last_tool_idx:
                content = msg.content
                if isinstance(content, str):
                    if '"screenshot"' in content:
                        content = re.sub(r'"screenshot"\s*:\s*"[^"]+"', '"screenshot": "[Image Omitted from History]"', content)
                    if "[SCREENSHOT]" in content:
                        content = re.sub(r'\[SCREENSHOT\].*?\[/SCREENSHOT\]', '[Image Omitted from History]', content, flags=re.DOTALL)
                elif isinstance(content, list):
                    new_content = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                            new_content.append({"type": "text", "text": "[Image Omitted from History]"})
                        else:
                            new_content.append(block)
                    content = new_content
                
                msg_copy = msg.copy()
                msg_copy.content = content
                pruned_msgs.append(msg_copy)
            else:
                pruned_msgs.append(msg)
        return pruned_msgs

    async def ainvoke(self, input, config=None, **kwargs):
        input = self._prune_messages(input)
        return await super().ainvoke(input, config=config, **kwargs)

    def invoke(self, input, config=None, **kwargs):
        input = self._prune_messages(input)
        return super().invoke(input, config=config, **kwargs)

class ToolOutputSanitizer:
    @staticmethod
    def sanitize(res: Any) -> tuple[Any, str | None]:
        """
        Sanitizes raw tool output by extracting the visual artifact if present.
        Crucially, we do NOT strip the screenshot here, because MemoryPruningLLM
        will prune older screenshots before invoking the model, leaving the latest one intact.
        """
        import json
        import re
        b64_frame = None
        
        if isinstance(res, list):
            for block in res:
                if isinstance(block, dict):
                    b_type = block.get("type")
                    if b_type in ("image", "image_url"):
                        if b_type == "image_url":
                            url = block.get("image_url", {}).get("url", "")
                            b64_frame = url.split(",", 1)[-1] if url.startswith("data:image") else url
                        else:
                            b64_frame = block.get("data", "")
            return res, b64_frame
            
        # If it's a string, attempt JSON or regex replacement
        output_str = str(res)
        try:
            data = json.loads(output_str)
            if isinstance(data, dict) and "screenshot" in data:
                b64_frame = data["screenshot"]
        except Exception:
            # Fallback regex
            match = re.search(r'"screenshot"\s*:\s*"([^"]+)"', output_str)
            if match:
                b64_frame = match.group(1)
            
        return res, b64_frame

class SemanticCompressor:
    def __init__(self, tool_selector: ToolSelector):
        self.tool_selector = tool_selector

    async def compress(self, query: str, raw_text: str, max_chars: int = 8000) -> str:
        if not raw_text or len(raw_text) <= max_chars:
            return raw_text

        # 1. Segment text into overlapping chunks
        chunk_size = 2500
        overlap = 300
        chunks = []
        start = 0
        text_len = len(raw_text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(raw_text[start:end])
            if end == text_len:
                break
            start += chunk_size - overlap

        if not chunks:
            return raw_text[:max_chars]

        # 2. Get embeddings and compute similarities
        logger.info(f"[SemanticCompressor] Chunked raw content into {len(chunks)} fragments for RAG indexing.")
        try:
            query_vector = await self.tool_selector._get_embedding(query)
            chunk_matches = []
            for chunk in chunks:
                try:
                    chunk_vector = await self.tool_selector._get_embedding(chunk[:800]) # Embed beginning of chunk to keep it fast
                    similarity = self.tool_selector._cosine_similarity(query_vector, chunk_vector)
                except Exception:
                    similarity = self.tool_selector._fallback_similarity(query, chunk)
                chunk_matches.append((similarity, chunk))
        except Exception:
            # Fallback to keyword matching if embedding service fails
            chunk_matches = [(self.tool_selector._fallback_similarity(query, chunk), chunk) for chunk in chunks]

        # 3. Sort by similarity descending
        chunk_matches.sort(key=lambda x: x[0], reverse=True)

        # 4. Construct response snippet up to target character budget
        selected_fragments = []
        current_len = 0
        for similarity, chunk in chunk_matches:
            if current_len + len(chunk) > max_chars:
                # Add snippet partial if we have space, otherwise break
                remaining = max_chars - current_len
                if remaining > 300:
                    selected_fragments.append(chunk[:remaining] + "... [TRUNCATED]")
                break
            selected_fragments.append(chunk)
            current_len += len(chunk)

        summary = "\n\n=== [RELEVANT EXCERPT] ===\n".join(selected_fragments)
        ratio = (1.0 - (len(summary) / text_len)) * 100.0
        logger.info(f"[SemanticCompressor] Compressed raw observation from {text_len} to {len(summary)} chars (saved {ratio:.1f}% context tokens).")
        return summary

class Brain:
    def __init__(self, model_name: str = None):
        model_name = model_name or config.MAIN_MODEL
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.active_plans: Dict[str, Any] = {}
        self.active_users: set = set()
        self._latest_thoughts: Dict[str, str] = {}
        self.live_tool_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.session_manager = SessionManager(is_active_callback=self.is_user_active)
        self.db_manager = DatabaseManager()
        self.stream_manager = None
        self.admin_llm_config = None
        self.model_name = model_name
        self.llm = MemoryPruningLLM(
            model_name=self.model_name,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.8,
            max_retries=3,
            max_tokens=16384,
        )
        self.code_gen_llm = MemoryPruningLLM(
            model_name=config.CODE_GENERATION_MODEL,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.2,
            max_retries=3,
            max_tokens=16384,
        )
        self.tool_selector = ToolSelector(model_name=self.model_name)
        self.code_processor = CodeProcessor(self.code_gen_llm)
        self.semantic_compressor = SemanticCompressor(self.tool_selector)

    def is_user_active(self, user_id: str) -> bool:
        return user_id in self.active_users
        
    async def update_llm_config(self, model_name: str, input_cost: float, output_cost: float, context_window: int):
        self.admin_llm_config = {
            "model_name": model_name,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "context_window": context_window
        }
        self.model_name = model_name
        self.llm = MemoryPruningLLM(
            model_name=self.model_name,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.8,
            max_retries=3,
            max_tokens=16384,
        )
        self.tool_selector = ToolSelector(model_name=self.model_name)
        self.semantic_compressor = SemanticCompressor(self.tool_selector)
        logger.info(f"Dynamically updated main LLM to {model_name} (Input: ${input_cost}, Output: ${output_cost})")


    async def initialize(self):
        logger.info("Pre-initializing MCP tools and generating embeddings cache...")
        self.session_manager.start_sweeper()
        
        # Load Admin LLM config
        try:
            from src.database.chat_db import SystemSetting, AsyncSessionLocal
            from sqlalchemy import select
            import json
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(SystemSetting).where(SystemSetting.key == "admin_main_llm_config"))
                setting = result.scalars().first()
                if setting and setting.value:
                    data = json.loads(setting.value)
                    await self.update_llm_config(
                        data.get("model_name", config.MAIN_MODEL),
                        data.get("input_cost", 0.1),
                        data.get("output_cost", 0.4),
                        data.get("context_window", 128000)
                    )
        except Exception as e:
            logger.error(f"Failed to load admin LLM config: {e}")
            
        try:
            from src.utils.session_manager import find_free_port
            
            # Temporarily force headless, disable system Chrome, and use a safe temp profile dir for startup tools discovery
            old_headless = os.environ.get("BROWSER_USE_HEADLESS")
            old_system_chrome = os.environ.get("BROWSER_USE_SYSTEM_CHROME")
            old_user_data_dir = os.environ.get("BROWSER_USER_DATA_DIR")
            
            os.environ["BROWSER_USE_HEADLESS"] = "true"
            os.environ["BROWSER_USE_SYSTEM_CHROME"] = "false"
            
            temp_port = find_free_port()
            os.environ["BROWSER_USER_DATA_DIR"] = os.path.join(config.TEMP_DIR_PATH, f"startup_discovery_{temp_port}")
            
            temp_manager = MCPToolManager(port=temp_port, user_id="system")
            all_tools = await temp_manager.get_tools()
            
            # Restore settings
            if old_headless is not None:
                os.environ["BROWSER_USE_HEADLESS"] = old_headless
            else:
                os.environ.pop("BROWSER_USE_HEADLESS", None)

            if old_system_chrome is not None:
                os.environ["BROWSER_USE_SYSTEM_CHROME"] = old_system_chrome
            else:
                os.environ.pop("BROWSER_USE_SYSTEM_CHROME", None)
                
            if old_user_data_dir is not None:
                os.environ["BROWSER_USER_DATA_DIR"] = old_user_data_dir
            else:
                os.environ.pop("BROWSER_USER_DATA_DIR", None)
                
            for tool in all_tools:
                tool_text = f"{tool.name} {tool.description or ''}"
                try:
                    await self.tool_selector._get_embedding(tool_text)
                    logger.info(f"Pre-embedded tool at startup: {tool.name}")
                except Exception as e:
                    logger.warning(f"Failed to pre-embed tool {tool.name}: {e}")
            
            try:
                await temp_manager.close()
            except Exception as e:
                logger.warning(f"Ignored error closing temp_manager during startup: {e}")
            logger.info("Pre-initialization of MCP tools and embeddings cache complete.")
        except Exception as e:
            logger.error(f"Error during MCP pre-initialization: {e}")

    async def shutdown(self):
        for task in self.active_tasks.values():
            task.cancel()
        for session in self.session_manager.sessions.values():
            mcp = session.get("mcp_manager")
            if mcp:
                try:
                    await mcp.close()
                except Exception as e:
                    logger.warning(f"Error closing mcp_manager during shutdown: {e}")

    async def stop_process(self, chat_id: str, user_id: str) -> bool:
        if chat_id in self.active_tasks:
            self.active_tasks[chat_id].cancel()
            return True
        return False

    def get_live_tool_logs(self, chat_id: str) -> list:
        return self.live_tool_logs.get(chat_id, [])

    def _wrap_tool_with_logging(self, tool: Any, chat_id: str, user_id: str, executed_tool_calls: list, query: str = "") -> Any:
        from langchain_core.tools import StructuredTool
        from datetime import datetime, timezone
        import json
        import uuid
        from src.database.chat_db import ToolExecutionLog, AsyncSessionLocal

        async def _coroutine_wrapper(*args, **kwargs):
            db_id = str(uuid.uuid4())
            tool_name = tool.name
            
            # Broadcast tool_start
            if self.stream_manager:
                tool_start_msg = {
                    "type": "tool_start",
                    "tool_call_id": db_id,
                    "tool": tool_name,
                    "args": kwargs
                }
                await self.stream_manager.broadcast_frame(tool_start_msg, user_id, is_tool=True)
                
            # Create pending DB log
            async with AsyncSessionLocal() as db:
                log_entry = ToolExecutionLog(
                    id=db_id,
                    chat_id=chat_id,
                    agent_id="agent_react",
                    tool_name=tool_name,
                    tool_input=json.dumps(kwargs),
                    status="IN_PROGRESS"
                )
                db.add(log_entry)
                await db.commit()
                
            # Update in-memory log buffer
            log_item = {
                "id": db_id,
                "tool_name": tool_name,
                "tool_input": json.dumps(kwargs),
                "status": "IN_PROGRESS",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            if chat_id not in self.live_tool_logs:
                self.live_tool_logs[chat_id] = []
            self.live_tool_logs[chat_id].append(log_item)
                
            # Execute original tool
            status = "success"
            error_str = None
            output_str = ""
            final_res = ""
            try:    
                raw_res = await tool.ainvoke(kwargs)
                
                # Check for LLM configuration/initialization errors in raw_res
                res_str = str(raw_res)
                if "LLM not initialized" in res_str or "No LLM configured in bridge" in res_str:
                    raise RuntimeError(res_str)
                
                # 1. ToolOutputSanitizer & Artifact Extraction
                sanitized_res, b64_frame = ToolOutputSanitizer.sanitize(raw_res)
                
                # 2. UI Streaming
                if b64_frame and self.stream_manager:
                    asyncio.create_task(self.stream_manager.broadcast_frame(b64_frame, user_id, is_tool=False))
                
                # Construct output_str from sanitized_res
                if isinstance(sanitized_res, list):
                    text_blocks = []
                    for block in sanitized_res:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_blocks.append(block.get("text", ""))
                        else:
                            text_blocks.append(str(block))
                    output_str = "\n".join(text_blocks)
                else:
                    output_str = str(sanitized_res)
                
                # 3. Semantic Compression & Token Budget Check (Strictly restricted to text/HTML extraction tools)
                if tool_name in ("browser_extract_raw", "browser_get_html") and output_str and len(output_str) > 5000:
                    search_query = query
                    if isinstance(kwargs, dict) and kwargs.get("query"):
                        search_query = f"{query} | {kwargs.get('query')}"
                    
                    if len(output_str) > 15000:
                        output_str = await self.semantic_compressor.compress(query=search_query, raw_text=output_str, max_chars=6000)
                    else:
                        output_str = await self.semantic_compressor.compress(query=search_query, raw_text=output_str, max_chars=4000)
                
                # 4. Observability & Logging
                raw_size = len(str(raw_res))
                final_size = len(output_str)
                compression_ratio = (1 - (final_size / raw_size)) * 100 if raw_size > 0 else 0
                logger.info(f"[ToolOutputPipeline] {tool_name} | Raw: {raw_size} chars | Processed: {final_size} chars | Reduced by {compression_ratio:.1f}%")
                
                # 5. Formulate lightweight metadata response for data extraction tools to LLM
                if tool_name in ("browser_extract_raw", "browser_extract_vision"):
                    summary_text = await self.semantic_compressor.compress(query=query, raw_text=output_str, max_chars=2000)
                    extracted_url = kwargs.get("url") or ""
                    if not extracted_url:
                        try:
                            session_data = self.session_manager.get_session(user_id)
                            mcp_manager = session_data.get("mcp_manager")
                            if mcp_manager and mcp_manager.browser_session:
                                page = await mcp_manager.browser_session.get_current_page()
                                extracted_url = page.url
                        except Exception:
                            pass
                    
                    metadata_output = {
                        "status": "SUCCESS_SAVED_TO_DATABASE",
                        "url": extracted_url,
                        "db_log_id": db_id,
                        "data_summary": summary_text,
                        "notes": "Raw full text saved in DB logs. Move to next task URL if extraction targets are met."
                    }
                    final_res = json.dumps(metadata_output, indent=2)
                else:
                    final_res = output_str
            except Exception as e:
                status = "failed"
                error_str = str(e)
                output_str = f"Error: {e}"
                final_res = output_str
                
            # Update DB log
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update
                await db.execute(
                    update(ToolExecutionLog)
                    .where(ToolExecutionLog.id == db_id)
                    .values(
                        status=status.upper(),
                        tool_output=output_str,
                        error_message=error_str
                    )
                )
                await db.commit()
                
            # Update in-memory log buffer
            for item in self.live_tool_logs.get(chat_id, []):
                if item["id"] == db_id:
                    item["status"] = status.upper()
                    item["tool_output"] = output_str
                    item["error_message"] = error_str
                    break
                    
            # Add to executed tool calls for final AI response payload
            executed_tool_calls.append({
                "id": db_id,
                "tool_name": tool_name,
                "tool_input": kwargs,
                "tool_output": output_str,
                "status": status.upper(),
                "error_message": error_str
            })
                
            if self.stream_manager:
                tool_output_msg = {
                    "type": "tool_output",
                    "tool_call_id": db_id,
                    "db_id": db_id,
                    "status": status,
                    "output": output_str,
                    "error": error_str
                }
                await self.stream_manager.broadcast_frame(tool_output_msg, user_id, is_tool=True)
                
            if error_str:
                raise RuntimeError(error_str)
                
            return final_res

        wrapped = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            func=tool._run,
            coroutine=_coroutine_wrapper
        )
        return wrapped

    async def process_message(self, user_id: str, message: str, chat_id: str) -> dict:
        execution_id = str(uuid.uuid4())
        token_user = current_user_id.set(user_id)
        token_chat = current_chat_id.set(chat_id)
        token_run = current_agent_run_id.set(execution_id)
        try:
            self.active_users.add(user_id)
            
            # Create stage-0 logging record in AgentExecutionLog
            async with AsyncSessionLocal() as db:
                log = AgentExecutionLog(
                    id=execution_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    agent_stage="1",
                    stage_name="ReAct Agent Run",
                    status="IN_PROGRESS",
                    input_data=json.dumps({"message": message}),
                )
                db.add(log)
                await db.commit()
            
            # Reset LLM token tracking accumulator
            if hasattr(self.llm, "reset_accumulator"):
                self.llm.reset_accumulator()

            # Cost Control: Check user budget limit
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(BudgetLimit).where(
                        (BudgetLimit.scope == "user") & (BudgetLimit.scope_id == user_id)
                    )
                )
                budget = result.scalar_one_or_none()
                if budget:
                    if budget.monthly_budget and budget.current_monthly_spend >= budget.monthly_budget:
                        if budget.action_at_100 == "reject":
                            raise RuntimeError("Monthly budget limit exceeded. Requests rejected.")
                        elif budget.action_at_100 == "switch_cheaper_model":
                            object.__setattr__(self.llm, "model_name", "openai/gpt-4o-mini")
                            logger.warning(f"User {user_id} exceeded budget. Switched to cheaper model openai/gpt-4o-mini.")
                        elif budget.action_at_100 == "throttle":
                            await asyncio.sleep(5.0)
                            logger.warning(f"User {user_id} throttled due to budget limits.")
            
            # --------------------------------------------------------------------------
            # PII / System Introspection Guardrail
            # --------------------------------------------------------------------------
            # If the user is asking about personal data, system internals, API keys,
            # model architecture, or how the agent works — respond with a friendly,
            # transparent description of the system instead of proceeding with the
            # full agent loop (which would waste tokens and time).
            # --------------------------------------------------------------------------
            _msg_lower = message.lower()
            _pii_triggers = [
                "system prompt", "your prompt", "your instructions", "what are your instructions",
                "what model are you", "which model", "what llm", "what ai model", "underlying model",
                "api key", "openrouter", "secret key", "environment variable", "your config",
                "how do you work", "how does this work", "how are you built", "your architecture",
                "what tools do you have", "list your tools", "show your tools",
                "your source code", "your code", "internal", "backend",
                "are you gpt", "are you claude", "are you gemini", "are you chatgpt",
                "who made you", "who created you", "who built you", "who trained you",
                "tell me about yourself", "what are you",
            ]
            if any(trigger in _msg_lower for trigger in _pii_triggers):
                pii_response = (
                    "As **SciParser AI**, I don't simply relay information from a static training database. "
                    "Instead, I am an **autonomous AI agent** that uses a combination of advanced reasoning, "
                    "real-time browser automation, and specialized tools to complete your requests.\n\n"
                    "Here's how I approach tasks:\n\n"
                    "1. **Real-Time Web Search**: I can navigate the live web, open URLs, and extract "
                    "structured data directly from pages — finding the most current, accurate information.\n\n"
                    "2. **Live Browser Automation**: I control a real browser session, interact with "
                    "web elements, handle authentication flows, and read dynamic content that traditional "
                    "APIs cannot access.\n\n"
                    "3. **Data Synthesis**: After gathering information across multiple sources and steps, "
                    "I compile, compare, and consolidate everything into a clean, structured final report "
                    "tailored to your specific request.\n\n"
                    "This approach allows me to provide you with live, accurate results rather than "
                    "relying on potentially outdated knowledge from a fixed training cutoff. "
                    "If you have a specific research, comparison, or data extraction task in mind, "
                    "I'm ready to get started! 🚀"
                )

                # Save the PII response to the database
                pii_msg_id = str(uuid.uuid4())
                async with AsyncSessionLocal() as db:
                    session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == chat_id))).scalar_one_or_none()
                    if not session_obj:
                        session_obj = ChatSession(
                            id=chat_id,
                            user_id=user_id,
                            title="About SciParser AI",
                            status="active"
                        )
                        db.add(session_obj)

                    user_msg = Message(
                        message_id=str(uuid.uuid4()),
                        chat_id=chat_id,
                        user_id=user_id,
                        role="user",
                        content=message
                    )
                    db.add(user_msg)

                    ai_msg = Message(
                        message_id=pii_msg_id,
                        chat_id=chat_id,
                        user_id=user_id,
                        role="ai",
                        content=pii_response,
                        plan_data=json.dumps([]),
                        tool_calls=json.dumps([]),
                        token_usage=json.dumps({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                        cost="0"
                    )
                    db.add(ai_msg)
                    await db.commit()

                return {
                    "success": True,
                    "message": {
                        "id": pii_msg_id,
                        "content": pii_response,
                        "tool_calls": [],
                        "plan": [],
                        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        "cost": 0
                    }
                }
            # --------------------------------------------------------------------------

            # --------------------------------------------------------------------------
            # Non-Automation Guardrail
            # --------------------------------------------------------------------------
            # SciParser is a focused autonomous automation agent. If the user asks
            # general knowledge questions, math, trivia, opinions, greetings, or
            # anything unrelated to browser automation / web tasks — short-circuit
            # immediately with a friendly redirect. Zero tokens wasted.
            # --------------------------------------------------------------------------
            _non_automation_triggers = [
                # Math / calculations
                "what is", "calculate", "solve", "compute", "how much is", "what's",
                "what does", "define", "explain", "tell me", "can you tell",
                # General knowledge / trivia
                "who is", "who was", "where is", "where was", "when is", "when was",
                "why is", "why does", "how many", "how old", "what year",
                # Opinions / recommendations (non-automation)
                "do you think", "what do you think", "what's your opinion",
                "what's the best", "recommend me", "suggest me",
                # Greetings / chitchat
                "hello", "hi ", "hey ", "good morning", "good afternoon", "good evening",
                "how are you", "what's up", "how's it going",
                # Weather / news / facts
                "weather", "news today", "latest news", "joke", "tell me a joke",
                "fun fact", "did you know",
                # Translation / writing
                "translate", "write a poem", "write a story", "write an essay",
                "summarize this text", "proofread",
                # Coding help (unrelated to automation tasks)
                "write code for", "give me code", "python code", "javascript code",
            ]
            # Only trigger if the message does NOT look like an automation/browser task
            _automation_keywords = [
                "automate", "automation", "browser", "scrape", "scraping", "crawl",
                "navigate", "click", "fill", "form", "login", "extract", "download",
                "website", "url", "http", "www.", ".com", ".org", ".net",
                "schedule", "run every", "monitor", "track", "watch",
                "data extraction", "web data", "open page", "go to",
            ]
            _is_automation_task = any(kw in _msg_lower for kw in _automation_keywords)

            if not _is_automation_task and any(trigger in _msg_lower for trigger in _non_automation_triggers):
                non_auto_response = (
                    "I'm **SciParser AI** — an **autonomous automation agent** built exclusively "
                    "for browser automation, web scraping, data extraction, and scheduled web tasks. 🤖\n\n"
                    "I'm not a general-purpose chatbot or search engine, so I'm unable to answer "
                    "general knowledge questions, math problems, or casual conversations.\n\n"
                    "**Here's what I *can* do for you:**\n\n"
                    "- 🌐 **Navigate & Automate** — Open any website and perform actions (click, fill forms, login)\n"
                    "- 📊 **Extract Data** — Scrape structured data from web pages, tables, and documents\n"
                    "- ⏰ **Schedule Tasks** — Run automations daily, weekly, or monthly automatically\n"
                    "- 🔍 **Monitor & Track** — Watch pages for changes and report back\n\n"
                    "**Try asking me something like:**\n"
                    "> *\"Go to amazon.com and extract the top 10 bestselling books\"*\n"
                    "> *\"Login to my dashboard and download the monthly report\"*\n"
                    "> *\"Monitor this URL every day and alert me if the price drops\"*\n\n"
                    "Give me an automation task and I'll get it done! 🚀"
                )

                # Save to database
                non_auto_msg_id = str(uuid.uuid4())
                async with AsyncSessionLocal() as db:
                    session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == chat_id))).scalar_one_or_none()
                    if not session_obj:
                        session_obj = ChatSession(
                            id=chat_id,
                            user_id=user_id,
                            title="SciParser — Automation Only",
                            status="active"
                        )
                        db.add(session_obj)

                    user_msg = Message(
                        message_id=str(uuid.uuid4()),
                        chat_id=chat_id,
                        user_id=user_id,
                        role="user",
                        content=message
                    )
                    db.add(user_msg)

                    ai_msg = Message(
                        message_id=non_auto_msg_id,
                        chat_id=chat_id,
                        user_id=user_id,
                        role="ai",
                        content=non_auto_response,
                        plan_data=json.dumps([]),
                        tool_calls=json.dumps([]),
                        token_usage=json.dumps({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                        cost="0"
                    )
                    db.add(ai_msg)
                    await db.commit()

                return {
                    "success": True,
                    "message": {
                        "id": non_auto_msg_id,
                        "content": non_auto_response,
                        "tool_calls": [],
                        "plan": [],
                        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        "cost": 0
                    }
                }
            # --------------------------------------------------------------------------

            # Setup session
            session_data = self.session_manager.get_session(user_id)
            if not session_data.get("mcp_manager"):
                session_data["mcp_manager"] = MCPToolManager(port=session_data["port"], user_id=user_id)
            mcp_manager = session_data["mcp_manager"]

            # 1. Get tools from MCP
            all_tools = await mcp_manager.get_tools()
            all_tools = [t for t in all_tools if t.name != "retry_with_browser_use_agent"]
            
            # Inject parallel orchestrator tool
            from src.services.parallel_orchestrator import create_spawn_parallel_browser_workers_tool
            from src.utils.pdf_tools import create_read_pdf_from_url_tool
            
            all_tools.append(create_spawn_parallel_browser_workers_tool(user_id=user_id))
            all_tools.append(create_read_pdf_from_url_tool())

            # Inject memory retriever tool for raw tool logs
            from src.services.tool_history_tool import create_fetch_past_tool_logs_tool
            all_tools.append(create_fetch_past_tool_logs_tool(chat_id=chat_id))

            # Run Tool Selection system to choose the right tools
            tools = await self.tool_selector.select_tools(message, all_tools)

            # Force-include core browser utilities
            core_tool_names = {
                "browser_get_state",
                "browser_navigate",
                "browser_click",
                "browser_wait",
                "browser_key_press",
                "browser_extract_raw",
                "browser_extract_vision",
                "browser_extract_from_vision",
                "read_pdf_from_url",
                "fetch_past_tool_logs"
            }
            selected_names = {t.name for t in tools}
            for t in all_tools:
                if t.name in core_tool_names and t.name not in selected_names:
                    tools.append(t)

            # Wrap tools with database logging & WebSocket streaming
            executed_tool_calls = []
            wrapped_tools = [
                self._wrap_tool_with_logging(t, chat_id, user_id, executed_tool_calls, query=message)
                for t in tools
            ]

            # 2. Plan the Task Queue (Lightweight JSON Plan)
            if self.stream_manager:
                await self.stream_manager.broadcast_thought(chat_id, "Planning workflow task queue...")

            # Fetch chat history context for the planner
            chat_context = ""
            try:
                async with AsyncSessionLocal() as db:
                    history_stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
                    history_res = await db.execute(history_stmt)
                    history_msgs = history_res.scalars().all()
                    
                    if history_msgs:
                        context_parts = []
                        for msg in history_msgs[-10:]: # last 10 messages
                            role_str = "USER" if msg.role == "user" else "AGENT"
                            context_parts.append(f"{role_str}: {msg.content}")
                        chat_context = "\n".join(context_parts)
            except Exception as e:
                logger.error(f"Failed to fetch chat history for planner: {e}")

            planner_prompt = (
                "You are an expert Task Planner.\n"
                "Decompose the following user request into a sequence of isolated, focused sub-tasks to execute sequentially.\n"
                "Each task must target a single URL or document, or perform a single specific extraction step.\n"
                "If the user is continuing a previous task, DO NOT create redundant tasks (e.g. do not re-navigate to a page if already there).\n"
                "Output ONLY a valid JSON list of objects. Do NOT output any markdown tags, commentary or code blocks. Start directly with [\n"
                "JSON format:\n"
                "[\n"
                "  {\n"
                "    \"id\": 1,\n"
                "    \"description\": \"Detailed task instruction\"\n"
                "  }\n"
                "]\n\n"
            )
            if chat_context:
                planner_prompt += f"PREVIOUS CHAT CONTEXT:\n{chat_context}\n\n"
            
            planner_prompt += f"CURRENT USER REQUEST: {message}"
            
            tasks = []
            try:
                planner_res = await self.llm.ainvoke([SystemMessage(content=planner_prompt)])
                plan_text = planner_res.content.strip()
                
                # Write raw planner response to a debug file
                try:
                    with open("planner_debug.txt", "w", encoding="utf-8") as debug_f:
                        debug_f.write(f"Raw Planner Response:\n{plan_text}\n")
                except Exception as write_err:
                    logger.error(f"Failed to write planner_debug.txt: {write_err}")

                if plan_text.startswith("```json"):
                    plan_text = plan_text.split("```json", 1)[-1]
                elif plan_text.startswith("```"):
                    plan_text = plan_text.split("```", 1)[-1]
                if plan_text.endswith("```"):
                    plan_text = plan_text.rsplit("```", 1)[0]
                plan_text = plan_text.strip()
                tasks = json.loads(plan_text)
                if not isinstance(tasks, list) or len(tasks) == 0:
                    raise ValueError("Planner output is not a list or is empty")
            except Exception as e:
                logger.error(f"Planner decomposition failed: {e}")
                try:
                    with open("planner_debug.txt", "a", encoding="utf-8") as debug_f:
                        debug_f.write(f"\nDecomposition Exception: {e}\n{traceback.format_exc()}\n")
                except Exception as write_err:
                    logger.error(f"Failed to append exception to planner_debug.txt: {write_err}")
                logger.warning(f"Failed to generate task plan: {e}. Defaulting to single task.")
                tasks = [{"id": 1, "description": message}]

            # 3. Initialize visual plan checklist for UI
            plan_tasks = []
            for task in tasks:
                plan_tasks.append({
                    "id": f"task_{task['id']}",
                    "title": task["description"],
                    "description": "",
                    "status": "pending",
                    "priority": "medium",
                    "level": 1,
                    "dependencies": [],
                    "subtasks": [],
                    "thought": ""
                })
            self.active_plans[chat_id] = plan_tasks
            if self.stream_manager:
                await self.stream_manager.broadcast_plan(chat_id, plan_tasks)

            # Retrieve relevant memory context for the agent
            from src.services.memory_retriever import memory_retriever
            async with AsyncSessionLocal() as mem_db:
                memory_context = await memory_retriever.retrieve_context(
                    db=mem_db, user_id=user_id, query=message, domain="general"
                )

            # System prompt for targeted ReAct agent runs
            system_prompt = (
                "You are an autonomous browser agent. Your objective is to complete the target task assigned to you.\n"
                "You control a live browser session. Focus on executing browser actions strictly one by one (sequentially).\n\n"
                "IMPORTANT INSTRUCTIONS:\n"
                "1. Always create a clear TODO list to plan and complete the task step-by-step.\n"
                "2. Use the cursor/mouse carefully for every action.\n"
                "3. Plan State Tracking: You MUST explicitly maintain and update your TODO list in your thoughts before every action. Clearly mark completed steps with '[x]' and current running steps with '[current]'.\n"
                "4. Linear URL Processing: Focus purely on your current target URL. Extract the details, print them clearly, and finish. Do not navigate to other pages outside the target task.\n"
                "5. Context Persistence (IMPORTANT): If the user's request is a conversational follow-up question (e.g. \"What was the third item in that list?\", \"Can you format that as a CSV?\"), DO NOT invoke any tools or browser actions. Answer directly using your conversation memory and the data you've already extracted.\n"
                "6. Multi-tab processing: If the user provides multiple URLs to process, you MUST open them in multiple tabs within the same browser session using the `new_tab: true` argument when navigating, rather than replacing the current page.\n"
                "7. PDF FILES IN BROWSER (CRITICAL): If you navigate to a URL and the browser opens a PDF viewer (you will see a PDF document rendered directly, not a normal webpage), you MUST NOT continue trying to click or scroll inside the PDF viewer as it will get you stuck forever. Instead, immediately use the `read_pdf_from_url` tool passing the EXACT same URL you navigated to. This will download and extract all the text data from the PDF directly.\n"
                "8. IMAGE-ONLY OR SCANNED CONTENT (CRITICAL): If the data you need is NOT present in the HTML text (e.g. prices are shown as images, inside a canvas element, or inside a PDF rendered as an image), you MUST immediately call `browser_extract_from_vision` with your exact query. This tool takes a screenshot and uses Vision AI to read data directly from the visual pixels, bypassing the DOM entirely. ALWAYS use this as your first fallback when text extraction fails.\n"
                "9. NEVER GET STUCK: If any browser action (click, scroll, type) produces no visible change after 2 attempts, STOP and switch strategy: try `browser_extract_from_vision` to read what is currently on screen, or use `read_pdf_from_url` if a PDF URL is involved.\n"
            )
            
            if memory_context:
                system_prompt += f"\n=========================================\nMEMORY CONTEXT\n=========================================\n{memory_context}\n=========================================\n"


            # Setup composite backend & fallback model
            projects_dir = config.PROJECTS_DIR
            os.makedirs(projects_dir, exist_ok=True)
            backend = CompositeBackend(
                default=StateBackend(),
                routes={
                    "/projects/": FilesystemBackend(
                        root_dir=projects_dir,
                        virtual_mode=True,
                    ),
                },
            )
            fallback_llm = MemoryPruningLLM(
                model_name="openai/gpt-4o-mini",
                openrouter_api_key=config.OPENROUTER_API_KEY,
                temperature=0.8,
                max_retries=3,
            )
            fallback_llm.reset_accumulator()

            completed_metadata = []

            # 4. Save User Message to DB (minimal)
            async with AsyncSessionLocal() as db:
                session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == chat_id))).scalar_one_or_none()
                if not session_obj:
                    # Dynamically generate a short, friendly, and meaningful title via LLM
                    title = suggest_chat_title(message)
                    try:
                        title_prompt = (
                            "You are a helpful assistant. Generate a short, friendly, and meaningful conversation title "
                            "(maximum 3-5 words) summarizing the user's intent from the following first message. "
                            "Do not include quotes, prefixes like 'Title:', or trailing punctuation.\n\n"
                            f"User message: {message}"
                        )
                        title_res = await self.llm.completion(
                            messages=[{"role": "user", "content": title_prompt}],
                            max_tokens=15
                        )
                        candidate = title_res.strip().strip('"\'')
                        if candidate and len(candidate) > 2 and len(candidate) < 60 and "generate" not in candidate.lower():
                            title = candidate
                    except Exception as e:
                        logger.warning(f"Failed to generate LLM chat title: {e}")

                    session_obj = ChatSession(
                        id=chat_id,
                        user_id=user_id,
                        title=title,
                        status="active"
                    )
                    db.add(session_obj)

                user_msg = Message(
                    message_id=str(uuid.uuid4()),
                    chat_id=chat_id,
                    user_id=user_id,
                    role="user",
                    content=message
                )
                db.add(user_msg)
                await db.commit()

            # 5. Execute each planned task sequentially
            for idx, task in enumerate(tasks):
                # Update task status to running
                for item in plan_tasks:
                    if item["id"] == f"task_{task['id']}":
                        item["status"] = "running"
                if self.stream_manager:
                    await self.stream_manager.broadcast_plan(chat_id, plan_tasks)

                # Formulate task prompt containing summaries of previously completed tasks
                completed_summary_str = ""
                if completed_metadata:
                    completed_summary_str = json.dumps(completed_metadata, indent=2)

                task_message = (
                    f"You are executing step {task['id']} of the overall request.\n"
                    f"OVERALL REQUEST: {message}\n"
                    f"YOUR CURRENT TARGET TASK: {task['description']}\n\n"
                )
                if completed_summary_str:
                    task_message += (
                        f"DATA EXTRACTED SO FAR FROM PREVIOUS COMPLETED STEPS:\n"
                        f"{completed_summary_str}\n\n"
                    )
                task_message += (
                    "Focus ONLY on completing the current target task. "
                    "Once the action is successful and the details are extracted, stop. Do not continue to future steps."
                )

                messages = [HumanMessage(content=task_message)]
                
                # Isolated thread checkpointer ID per task to avoid context bloat!
                run_config = {"configurable": {"thread_id": f"{chat_id}_task_{task['id']}"}}
                
                agent_executor = create_deep_agent(
                    model=self.llm,
                    backend=backend,
                    tools=wrapped_tools,
                    system_prompt=system_prompt,
                    checkpointer=MemorySaver(),
                    middleware=[
                        ModelCallLimitMiddleware(run_limit=60),
                        ToolCallLimitMiddleware(run_limit=80),
                        ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
                        ModelFallbackMiddleware(fallback_llm),
                        ToolRetryMiddleware(max_retries=2, retry_on=(TimeoutError, ConnectionError)),
                    ],
                )

                task_response = ""
                async for event in agent_executor.astream({"messages": messages}, run_config, stream_mode="updates"):
                    for node_name, node_output in event.items():
                        if not isinstance(node_output, dict) or "messages" not in node_output:
                            continue
                        for msg in node_output["messages"]:
                            # Process ToolMessage screenshots
                            if isinstance(msg, ToolMessage) or (hasattr(msg, "type") and msg.type == "tool"):
                                content = msg.content
                                
                                # Non-fatal error patterns the agent can recover from —
                                # log a warning and let the loop continue instead of halting.
                                # Most tool errors are self-correctable by the LLM on the next turn;
                                # only truly catastrophic errors (unmatched by this list) should halt.
                                _RECOVERABLE_ERROR_PATTERNS = [
                                    # deepagents internal tool guardrails
                                    "write_todos",
                                    "should never be called multiple times in parallel",
                                    "todo",
                                    # File operation errors (LLM can retry with corrected args)
                                    "exceeds file length",
                                    "line offset",
                                    "file not found",
                                    "not found",
                                    "no such file",
                                    "is not a file",
                                    "is a directory",
                                    "permission denied",
                                    # Tool argument / validation errors
                                    "invalid argument",
                                    "invalid parameter",
                                    "missing required",
                                    "expected type",
                                    "out of range",
                                    "out of bounds",
                                    # Browser-use / MCP tool transient errors
                                    "element not found",
                                    "selector not found",
                                    "no element found",
                                    "stale element",
                                    "not interactable",
                                    "timed out",
                                    "timeout",
                                    "navigation failed",
                                    "target closed",
                                    "session closed",
                                    "connection refused",
                                    "connection reset",
                                ]

                                def _is_recoverable_error(text: str) -> bool:
                                    lowered = text.lower()
                                    return any(pat in lowered for pat in _RECOVERABLE_ERROR_PATTERNS)

                                # HALT ON TOOL ERRORS TO SAVE COSTS — but skip recoverable ones
                                if isinstance(content, str) and content.startswith("Error:"):
                                    if _is_recoverable_error(content):
                                        logger.warning(f"Non-fatal tool error (skipping): {content}")
                                    else:
                                        logger.error(f"Halting agent execution due to tool failure: {content}")
                                        return {"success": False, "error": content}
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            text_content = block.get("text", "")
                                            if text_content.startswith("Error:"):
                                                if _is_recoverable_error(text_content):
                                                    logger.warning(f"Non-fatal tool error (skipping): {text_content}")
                                                else:
                                                    logger.error(f"Halting agent execution due to tool failure: {text_content}")
                                                    return {"success": False, "error": text_content}
                                    
                                b64_frame = None
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "image_url":
                                            url = block.get("image_url", {}).get("url", "")
                                            b64_frame = url.split(",", 1)[-1] if url.startswith("data:image") else url
                                elif isinstance(content, str):
                                    try:
                                        data = json.loads(content)
                                        if isinstance(data, dict) and "screenshot" in data:
                                            b64_frame = data["screenshot"]
                                    except Exception:
                                        match = re.search(r'"screenshot"\s*:\s*"([^"]+)"', content)
                                        if match:
                                            b64_frame = match.group(1)
                                if b64_frame and self.stream_manager:
                                    asyncio.create_task(self.stream_manager.broadcast_frame(b64_frame, user_id, is_tool=False))
                            
                            # Process AIMessage thoughts
                            elif isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
                                if msg.content:
                                    task_response = msg.content
                                if self.stream_manager and msg.content:
                                    await self.stream_manager.broadcast_thought(chat_id, f"[Task {task['id']}] {msg.content}")
                                    self._latest_thoughts[chat_id] = msg.content

                # Mark task as completed
                for item in plan_tasks:
                    if item["id"] == f"task_{task['id']}":
                        item["status"] = "completed"
                        item["thought"] = task_response
                if self.stream_manager:
                    await self.stream_manager.broadcast_plan(chat_id, plan_tasks)

                # Cache task summary for next steps
                completed_metadata.append({
                    "task_id": task["id"],
                    "description": task["description"],
                    "extracted_data_summary": task_response
                })

            # 6. Run Final Consolidation Aggregator
            if self.stream_manager:
                await self.stream_manager.broadcast_thought(chat_id, "Compiling final consolidated results...")

            aggregator_prompt = (
                "You are the final consolidated report builder.\n"
                "Your job is to compile a clear, accurate, and concise final response based on the data extracted across all completed steps.\n\n"
                f"USER GOAL: {message}\n\n"
                f"EXTRACTED DATA FROM ALL COMPLETED STEPS:\n{json.dumps(completed_metadata, indent=2)}\n\n"
                "CRITICAL FORMATTING RULES:\n"
                "1. ONLY generate a markdown table if the user's goal involved extracting structured/tabular data "
                "(e.g. product listings, prices, search results, comparisons). "
                "DO NOT generate a table for navigation tasks, action tasks, or tasks with no structured data.\n"
                "2. For simple navigation or action tasks (e.g. 'go to google.com', 'click the button', 'login'), "
                "respond with a SHORT plain-text summary (1-3 sentences) confirming what was done. No headers, no tables.\n"
                "3. For data extraction tasks, compile all extracted data into a clean structured table with proper column names.\n"
                "4. Never invent data. If no data was extracted, say so clearly in plain text.\n"
                "5. Do not include execution metadata like 'Step ID', 'Task Description', 'Status', or 'Outcome' columns — "
                "those are internal agent internals, not useful output for the user."
            )

            aggregator_res = await self.llm.ainvoke([SystemMessage(content=aggregator_prompt)])
            final_response = aggregator_res.content.strip()

            # 7. Calculate total token usage and cost across all runs
            total_prompt_tokens = self.llm.accumulated_prompt_tokens
            total_completion_tokens = self.llm.accumulated_completion_tokens
            total_cost = self.llm.accumulated_cost
            
            if hasattr(fallback_llm, "accumulated_cost"):
                total_prompt_tokens += fallback_llm.accumulated_prompt_tokens
                total_completion_tokens += fallback_llm.accumulated_completion_tokens
                total_cost += fallback_llm.accumulated_cost
                
            token_usage_json = json.dumps({
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens
            })
            cost_str = str(total_cost)

            # 8. Save Final Consolidated Response to DB & Deduct User Credits
            ai_msg_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                ai_msg = Message(
                    message_id=ai_msg_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    role="ai",
                    content=final_response,
                    plan_data=json.dumps(self.active_plans.get(chat_id, [])),
                    tool_calls=json.dumps(executed_tool_calls),
                    token_usage=token_usage_json,
                    cost=cost_str
                )
                db.add(ai_msg)
                
                # Deduct cost from user's credit balance
                await db.execute(
                    update(User)
                    .where(User.user_id == user_id)
                    .values(credit_balance=User.credit_balance - total_cost)
                )

                # Update budget spend & trigger alert thresholds
                budget_res = await db.execute(
                    select(BudgetLimit).where(
                        (BudgetLimit.scope == "user") & (BudgetLimit.scope_id == user_id)
                    )
                )
                user_budget = budget_res.scalar_one_or_none()
                if not user_budget:
                    # Seed a default budget of $5 daily and $50 monthly for the user
                    user_budget = BudgetLimit(
                        scope="user",
                        scope_id=user_id,
                        daily_budget=5.0,
                        monthly_budget=50.0,
                        current_daily_spend=total_cost,
                        current_monthly_spend=total_cost,
                        alert_thresholds="50,75,90,100",
                        action_at_100="switch_cheaper_model"
                    )
                    db.add(user_budget)
                else:
                    user_budget.current_daily_spend += total_cost
                    user_budget.current_monthly_spend += total_cost

                # Evaluate thresholds
                if user_budget.monthly_budget:
                    pct_before = ((user_budget.current_monthly_spend - total_cost) / user_budget.monthly_budget) * 100
                    pct_after = (user_budget.current_monthly_spend / user_budget.monthly_budget) * 100
                    try:
                        thresholds = [float(t.strip()) for t in user_budget.alert_thresholds.split(",") if t.strip()]
                        for th in thresholds:
                            if pct_before < th <= pct_after:
                                # Write alert notification to DB
                                alert = AlertNotification(
                                    severity="critical" if th >= 100 else "warning" if th >= 90 else "info",
                                    category="cost",
                                    title=f"Cost Alert: {th}% Budget Exceeded",
                                    message=f"User {user_id} monthly budget of ${user_budget.monthly_budget:.2f} has reached {pct_after:.1f}% consumption."
                                )
                                db.add(alert)
                                # Broadcast alert notification to user stream
                                if self.stream_manager:
                                    asyncio.create_task(self.stream_manager.broadcast_notification(
                                        chat_id, "budget_alert", f"Monthly budget usage is at {pct_after:.1f}%."
                                    ))
                    except Exception as th_err:
                        logger.error(f"Error checking budget alerts: {th_err}")

                # Update AgentExecutionLog success status
                await db.execute(
                    update(AgentExecutionLog)
                    .where(AgentExecutionLog.id == execution_id)
                    .values(
                        status="COMPLETED",
                        output_data=final_response,
                        token_usage=token_usage_json,
                        cost=cost_str
                    )
                )
                await db.commit()

            # Broadcast the final response over WebSocket to handle any HTTP timeout/drop cases
            if self.stream_manager:
                try:
                    await self.stream_manager.broadcast_notification(
                        chat_id,
                        "final_response",
                        json.dumps({
                            "id": ai_msg_id,
                            "role": "ai",
                            "content": final_response,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "plan": self.active_plans.get(chat_id, []),
                            "tool_calls": executed_tool_calls
                        })
                    )
                except Exception as ws_err:
                    logger.error(f"Failed to broadcast final response via WS: {ws_err}")

            # Trigger Memory Extractor in background
            try:
                from src.services.memory_extractor import memory_extractor
                conversation_history = f"User: {message}\nAI: {final_response}"
                asyncio.create_task(
                    memory_extractor.extract_and_store(
                        user_id=user_id, domain="general", conversation_history=conversation_history
                    )
                )
            except Exception as extract_err:
                logger.error(f"Failed to trigger memory extractor: {extract_err}")

            return {
                "success": True,
                "message": {
                    "id": ai_msg_id,
                    "content": final_response,
                    "tool_calls": executed_tool_calls,
                    "plan": self.active_plans.get(chat_id, []),
                    "token_usage": {
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens
                    },
                    "cost": total_cost,
                    "log_id": execution_id
                }
            }

        except Exception as e:
            logger.error(f"Error in process_message: {traceback.format_exc()}")
            if self.stream_manager:
                try:
                    await self.stream_manager.broadcast_notification(
                        chat_id,
                        "error_response",
                        json.dumps({
                            "id": str(uuid.uuid4()),
                            "role": "assistant",
                            "content": f"⚠️ An error occurred during execution: {str(e)}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    )
                except Exception as ws_err:
                    logger.error(f"Failed to broadcast error response via WS: {ws_err}")

            if execution_id:
                try:
                    async with AsyncSessionLocal() as db:
                        await db.execute(
                            update(AgentExecutionLog)
                            .where(AgentExecutionLog.id == execution_id)
                            .values(
                                status="FAILED",
                                error_message=str(e)
                            )
                        )
                        await db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to log agent failure: {db_err}")
            return {"success": False, "error": str(e)}
        finally:
            self.active_users.discard(user_id)
            current_user_id.reset(token_user)
            current_chat_id.reset(token_chat)
            current_agent_run_id.reset(token_run)

brain = Brain()
