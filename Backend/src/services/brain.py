import asyncio
import os
import uuid
import re
import traceback
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.prebuilt import create_react_agent
from deepagents import create_deep_agent
from src.utils.logger import logger
from src.agents.mcp_agent import MCPToolManager
from src.utils.session_manager import SessionManager
from src.database.chat_db import AsyncSessionLocal, Message, ChatSession, ToolExecutionLog
from sqlalchemy import select
from src.services.tool_selector import ToolSelector
from langchain_core.tools import StructuredTool
from datetime import datetime, timezone
import json

class DatabaseManager:
    # Minimal stub just for main.py compatibility
    async def get_or_create_chat_session(self, user_id: str, chat_id: str):
        pass

class MockCodeProcessor:
    # Stub for the scheduler endpoint to prevent crash
    async def run_script_generation(self, *args, **kwargs):
        return "# Script generation disabled in simplified ReAct architecture."

class Brain:
    def __init__(self,model_name: str = os.getenv("MAIN_MODEL")):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.active_plans: Dict[str, Any] = {}
        self.live_tool_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.session_manager = SessionManager()
        self.db_manager = DatabaseManager()
        self.code_processor = MockCodeProcessor()
        self.stream_manager = None
        self.model_name = model_name
        self.llm = ChatOpenRouter(
            model_name=self.model_name,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            temperature=0.8,
            max_retries=3,
            max_tokens=16384,
        )
        self.tool_selector = ToolSelector(model_name=self.model_name)

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

    def _wrap_tool_with_logging(self, tool: Any, chat_id: str, user_id: str, executed_tool_calls: list) -> Any:
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
            try:
                res = await tool.ainvoke(kwargs)
                if isinstance(res, list):
                    text_blocks = []
                    for block in res:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_blocks.append(block.get("text", ""))
                        else:
                            text_blocks.append(str(block))
                    output_str = "\n".join(text_blocks)
                else:
                    output_str = str(res)
            except Exception as e:
                status = "failed"
                error_str = str(e)
                output_str = f"Error: {e}"
                
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
                
            # Broadcast tool_output
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
                
            return res

        wrapped = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            func=tool._run,
            coroutine=_coroutine_wrapper
        )
        return wrapped

    async def process_message(self, user_id: str, message: str, chat_id: str) -> dict:
        try:
            # 1. Ensure MCP Server and Session exist
            # (MCPToolManager lazily initializes inside get_tools())
            
            # Setup session
            session_data = self.session_manager.get_session(user_id)
            if not session_data.get("mcp_manager"):
                session_data["mcp_manager"] = MCPToolManager(port=session_data["port"], user_id=user_id)
            mcp_manager = session_data["mcp_manager"]

            # 2. Get tools from MCP
            all_tools = await mcp_manager.get_tools()
            
            # Filter out the meta-agent tool to force sequential atomic tool calling
            all_tools = [t for t in all_tools if t.name != "retry_with_browser_use_agent"]

            # Run Tool Selection system to choose the right tools
            tools = await self.tool_selector.select_tools(message, all_tools)

            # Force-include core browser utilities that the agent always needs to operate properly
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
                self._wrap_tool_with_logging(t, chat_id, user_id, executed_tool_calls)
                for t in tools
            ]

            # 3. Create simple ReAct agent
            system_prompt = (
                "You are an autonomous browser agent. Your objective is to complete the user's task by any valid method. "
                "You control a live browser session. If you encounter an obstacle (e.g. login popup, cookie banner), "
                "do not give up. Find a way around it or close it. Never repeat the same failed action.\n\n"
                "IMPORTANT INSTRUCTIONS:\n"
                "1. Always create a clear TODO list to plan and complete the task step-by-step.\n"
                "2. Use the cursor/mouse carefully for every action (e.g., hover over elements, verify coordinates before clicking).\n"
                "3. CRITICAL: You MUST execute browser actions strictly one by one (sequentially). NEVER call multiple browser tools or output parallel tool calls in a single turn. You must wait for the output of the current tool (like navigate or click) and analyze the page state before generating the next tool call."
            )
            # agent_executor = create_react_agent(self.llm, tools, prompt=system_prompt)
            agent_executor = create_deep_agent(
                model = self.llm,
                system_prompt = system_prompt,
                tools = wrapped_tools
            )

            # 4. Save User Message to DB (minimal)
            async with AsyncSessionLocal() as db:
                # Ensure ChatSession exists
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

            # 5. Run the agent and stream results
            messages = [HumanMessage(content=message)]
            
            if self.stream_manager:
                await self.stream_manager.broadcast_thought(chat_id, "Agent starting execution...")

            final_response = ""
            # Use updates mode to intercept tool messages
            async for event in agent_executor.astream({"messages": messages}, stream_mode="updates"):
                logger.info(f"Agent stream event keys: {list(event.keys())}")
                # Dynamically process any node that outputs message state updates
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict) or "messages" not in node_output:
                        continue
                    for msg in node_output["messages"]:
                        # Process ToolMessage content (screenshots / base64 frame extraction)
                        if isinstance(msg, ToolMessage) or (hasattr(msg, "type") and msg.type == "tool"):
                            content = msg.content
                            b64_frame = None

                            if isinstance(content, list):
                                new_content = ""
                                for block in content:
                                    if isinstance(block, dict):
                                        b_type = block.get("type")
                                        if b_type == "image_url":
                                            url = block.get("image_url", {}).get("url", "")
                                            if url.startswith("data:image"):
                                                b64_frame = url.split(",", 1)[-1]
                                            else:
                                                b64_frame = url
                                            new_content += "[Image Data Omitted]\n"
                                        elif b_type == "image":
                                            # Native MCP image block
                                            b64_frame = block.get("data", "")
                                            new_content += "[Image Data Omitted]\n"
                                        elif b_type == "text":
                                            new_content += str(block.get("text", "")) + "\n"
                                        else:
                                            new_content += str(block) + "\n"
                                    else:
                                        new_content += str(block) + "\n"
                                msg.content = new_content.strip()
                            elif isinstance(content, str):
                                if "[SCREENSHOT]" in content:
                                    match = re.search(r'\[SCREENSHOT\](.*?)\[/SCREENSHOT\]', content, flags=re.DOTALL)
                                    if match:
                                        b64_frame = match.group(1)
                                    msg.content = re.sub(r'\[SCREENSHOT\].*?\[/SCREENSHOT\]', '[Image Data]', content, flags=re.DOTALL)
                                else:
                                    # Parse JSON output from MCP browser_get_state
                                    try:
                                        import json
                                        data = json.loads(content)
                                        if isinstance(data, dict) and "screenshot" in data:
                                            b64_frame = data["screenshot"]
                                            # Strip the giant base64 from content to avoid bloating LLM memory
                                            data["screenshot"] = "[Image Data]"
                                            msg.content = json.dumps(data, indent=2)
                                    except Exception:
                                        # Fallback regex search for "screenshot" field
                                        match = re.search(r'"screenshot"\s*:\s*"([^"]+)"', content)
                                        if match:
                                            b64_frame = match.group(1)
                                            msg.content = re.sub(r'"screenshot"\s*:\s*"[^"]+"', '"screenshot": "[Image Data]"', content)
                                
                            if b64_frame and self.stream_manager:
                                asyncio.create_task(self.stream_manager.broadcast_frame(b64_frame, user_id, is_tool=False))
                    
                        # Process AIMessage content (thoughts & responses)
                        elif isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
                            if msg.content:
                                final_response = msg.content
                            if self.stream_manager and msg.content:
                                await self.stream_manager.broadcast_thought(chat_id, msg.content)

            # 6. Save AI Message to DB
            ai_msg_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                ai_msg = Message(
                    message_id=ai_msg_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    role="ai",
                    content=final_response or "Task finished.",
                    tool_calls=json.dumps(executed_tool_calls)
                )
                db.add(ai_msg)
                await db.commit()

            return {
                "success": True,
                "message": {
                    "id": ai_msg_id,
                    "content": final_response or "Task finished.",
                    "tool_calls": executed_tool_calls
                }
            }

        except Exception as e:
            logger.error(f"Error in process_message: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

brain = Brain()
