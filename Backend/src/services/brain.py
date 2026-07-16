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
    ) -> str:
        from langchain_core.messages import SystemMessage
        import json

        prompt = (
            "You are an expert autonomous Python script compiler and developer.\n"
            f"Your job is to generate a fully functional, self-contained Python script to automate the task: '{title}'.\n"
            f"USER GOAL: {user_goal}\n"
            f"AUTOMATION FRAMEWORK: {framework}\n\n"
        )
        
        if plan_context:
            prompt += f"EXECUTION PLAN PATHWAYS:\n{plan_context}\n\n"
            
        if tool_context:
            context_str = json.dumps(tool_context, indent=2)
            prompt += f"OBSERVED TOOLS EXECUTIONS LOGS:\n{context_str}\n\n"
            
        prompt += (
            "INSTRUCTIONS:\n"
            "1. Output ONLY the raw Python code. Do NOT wrap the code in markdown code blocks like ```python ... ```. Start the response directly with the first line of code (e.g. imports).\n"
            "2. The script must be fully self-contained and run standalone. Implement standard try/except blocks for robust error handling.\n"
            "3. If using Playwright, use standard Playwright async API with chromium headless browser.\n"
            "4. Do not add any conversational text before or after the code block."
        )
        
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
            return code.strip()
        except Exception as e:
            logger.error(f"Failed to generate automated script: {e}")
            return f"# Error generating automated script: {e}"

def get_model_pricing(model_name: str) -> tuple[float, float]:
    """Returns (input_cost_per_million, output_cost_per_million) for the given model."""
    name = model_name.lower()
    if "gemini-3.5-flash" in name or "gemini-3-flash" in name or "gemini-3-flash-preview" in name:
        return 0.50, 3.50
    elif "gemini-1.5-pro" in name or "gemini-3-pro" in name:
        return 1.25, 5.00
    elif "gpt-4o-mini" in name:
        return 0.15, 0.60
    elif "gpt-4o" in name:
        return 2.50, 10.00
    elif "claude-3-5-sonnet" in name:
        return 3.00, 15.00
    elif "claude-3-haiku" in name:
        return 0.25, 1.25
    elif "minimax-m3" in name:
        return 0.30, 1.20
    # Default fallback to config settings
    from src import config
    return getattr(config, "LLM_INPUT_COST_PER_MILLION", 0.1), getattr(config, "LLM_OUTPUT_COST_PER_MILLION", 0.4)

import contextvars

current_user_id = contextvars.ContextVar("current_user_id", default="system")
current_chat_id = contextvars.ContextVar("current_chat_id", default=None)
current_agent_run_id = contextvars.ContextVar("current_agent_run_id", default=None)


from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

class TokenTrackingCallbackHandler(AsyncCallbackHandler):
    def __init__(self, llm_instance):
        self.llm_instance = llm_instance

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
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
                    
                    await record_llm_request(
                        user_id=user_id,
                        chat_id=chat_id,
                        model=self.llm_instance.model_name,
                        source="chat" if chat_id else "system",
                        category_tokens=category_tokens,
                        input_tokens=prompt_tokens,
                        output_tokens=completion_tokens,
                        cost_usd=cost
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
    def __init__(self,model_name: str = os.getenv("MAIN_MODEL")):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.active_plans: Dict[str, Any] = {}
        self.active_users: set = set()
        self._latest_thoughts: Dict[str, str] = {}
        self.live_tool_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.session_manager = SessionManager()
        self.db_manager = DatabaseManager()
        self.stream_manager = None
        self.model_name = model_name
        self.llm = MemoryPruningLLM(
            model_name=self.model_name,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            temperature=0.8,
            max_retries=3,
            max_tokens=16384,
        )
        self.tool_selector = ToolSelector(model_name=self.model_name)
        self.code_processor = CodeProcessor(self.llm)
        self.semantic_compressor = SemanticCompressor(self.tool_selector)

    def is_user_active(self, user_id: str) -> bool:
        return user_id in self.active_users

    async def initialize(self):
        logger.info("Pre-initializing MCP tools and generating embeddings cache...")
        try:
            from src.utils.session_manager import find_free_port
            
            # Temporarily force headless and disable system Chrome for startup tools discovery
            old_headless = os.environ.get("BROWSER_USE_HEADLESS")
            old_system_chrome = os.environ.get("BROWSER_USE_SYSTEM_CHROME")
            os.environ["BROWSER_USE_HEADLESS"] = "true"
            os.environ["BROWSER_USE_SYSTEM_CHROME"] = "false"
            
            temp_port = find_free_port()
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
            
            # Setup session
            session_data = self.session_manager.get_session(user_id)
            if not session_data.get("mcp_manager"):
                session_data["mcp_manager"] = MCPToolManager(port=session_data["port"], user_id=user_id)
            mcp_manager = session_data["mcp_manager"]

            # 1. Get tools from MCP
            all_tools = await mcp_manager.get_tools()
            all_tools = [t for t in all_tools if t.name != "retry_with_browser_use_agent"]

            # Run Tool Selection system to choose the right tools
            tools = await self.tool_selector.select_tools(message, all_tools)

            # Force-include core browser utilities
            core_tool_names = {
                "browser_get_state",
                "browser_wait",
                "browser_key_press",
                "browser_extract_raw",
                "browser_extract_vision"
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

            planner_prompt = (
                "You are an expert Task Planner.\n"
                "Decompose the following user request into a sequence of isolated, focused sub-tasks to execute sequentially.\n"
                "Each task must target a single URL or document, or perform a single specific extraction step.\n"
                "Output ONLY a valid JSON list of objects. Do NOT output any markdown tags, commentary or code blocks. Start directly with [\n"
                "JSON format:\n"
                "[\n"
                "  {\n"
                "    \"id\": 1,\n"
                "    \"description\": \"Detailed task instruction\"\n"
                "  }\n"
                "]\n\n"
                f"USER REQUEST: {message}"
            )
            
            tasks = []
            try:
                planner_res = await self.llm.ainvoke([SystemMessage(content=planner_prompt)])
                plan_text = planner_res.content.strip()
                if plan_text.startswith("```json"):
                    plan_text = plan_text.split("```json", 1)[-1]
                elif plan_text.startswith("```"):
                    plan_text = plan_text.split("```", 1)[-1]
                if plan_text.endswith("```"):
                    plan_text = plan_text.rsplit("```", 1)[0]
                plan_text = plan_text.strip()
                tasks = json.loads(plan_text)
                if not isinstance(tasks, list):
                    raise ValueError("Planner output is not a list")
            except Exception as plan_err:
                logger.warning(f"Failed to generate task plan: {plan_err}. Defaulting to single task.")
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

            # System prompt for targeted ReAct agent runs
            system_prompt = (
                "You are an autonomous browser agent. Your objective is to complete the target task assigned to you.\n"
                "You control a live browser session. Focus on executing browser actions strictly one by one (sequentially).\n\n"
                "IMPORTANT INSTRUCTIONS:\n"
                "1. Always create a clear TODO list to plan and complete the task step-by-step.\n"
                "2. Use the cursor/mouse carefully for every action.\n"
                "3. Plan State Tracking: You MUST explicitly maintain and update your TODO list in your thoughts before every action. Clearly mark completed steps with '[x]' and current running steps with '[current]'.\n"
                "4. Linear URL Processing: Focus purely on your current target URL. Extract the details, print them clearly, and finish. Do not navigate to other pages outside the target task."
            )

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
                openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
                temperature=0.8,
                max_retries=3,
            )
            fallback_llm.reset_accumulator()

            completed_metadata = []

            # 4. Save User Message to DB (minimal)
            async with AsyncSessionLocal() as db:
                session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == chat_id))).scalar_one_or_none()
                if not session_obj:
                    session_obj = ChatSession(
                        id=chat_id,
                        user_id=user_id,
                        title=message[:50] + ("..." if len(message) > 50 else ""),
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
                                
                                # HALT ON ANY TOOL ERROR TO SAVE COSTS
                                if isinstance(content, str) and content.startswith("Error:"):
                                    logger.error(f"Halting agent execution due to tool failure: {content}")
                                    return {"success": False, "error": content}
                                if isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            text_content = block.get("text", "")
                                            if text_content.startswith("Error:"):
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
                "Decompose, merge, deduplicate, and compile the final structured results based on the data extracted across all steps.\n\n"
                f"USER GOAL: {message}\n\n"
                f"EXTRACTED DATA FROM ALL COMPLETED STEPS:\n{json.dumps(completed_metadata, indent=2)}\n\n"
                "Please present the complete gathered data clearly in the final consolidated layout requested by the user (e.g. compile a structured table). "
                "Ensure no details are lost. If no data was successfully extracted, output a friendly error message explaining what failed."
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
                    "cost": total_cost
                }
            }

        except Exception as e:
            logger.error(f"Error in process_message: {traceback.format_exc()}")
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
