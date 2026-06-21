# src/services/brain.py
import asyncio
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, List

from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import (
    HumanMessage, 
    AIMessage, 
    SystemMessage, 
    BaseMessage,
    ToolMessage
)
from langchain_core.tools import BaseTool 
from langchain_openrouter import ChatOpenRouter
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# Database and Utilities
from src.database.chat_db import AsyncSessionLocal, Message, ChatSession, AgentExecutionLog, ToolExecutionLog
from src.utils.logger import logger
from src.agents.mcp_agent import MCPToolManager
from src.utils.playwright_manager import PlaywrightSessionManager
from src.services.agent_manager import agent_manager

# ATAG Models
from src.services.ATAG import (
    AgentState, 
    ATAGProcessor, 
    serialize_state, 
    deserialize_state
)

class DatabaseManager:
    """Manages transaction-scoped database operations securely to prevent locking connection pools."""
    
    async def log_agent_execution(self, user_id: str, chat_id: str, stage: str, name: str, status: str, input_data: Any = None, output_data: Any = None, error: str = None):
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
                    error_message=error
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
                # FIX: Changed ChatSession.session_id to ChatSession.id
                result = await db.execute(select(ChatSession).where(ChatSession.id == chat_id))
                session = result.scalar_one_or_none()
                if session:
                    db.expunge(session)
                    return session
                
                # Create new session with all required fields, tied to user_id and chat_id
                new_session = ChatSession(
                    id=chat_id,  # FIX: Use 'id' instead of 'session_id'
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
                # FIX: Use scalar_one_or_none() instead of scalar_one() to prevent crash
                result = await db.execute(select(ChatSession).where(ChatSession.id == chat_id))
                session = result.scalar_one_or_none()
                if session:
                    db.expunge(session)
                    return session
                # If still no session after rollback, re-raise with clear error
                raise Exception(f"Failed to create or retrieve session for chat_id={chat_id}, user_id={user_id}")
            except Exception as e:
                logger.error(f"Error getting/creating session: {e}")
                raise


class Brain:
    """
    Orchestrates the Multi-Agent System (Agent 1, Agent 2, Agent 3) using LangGraph and LangChain.
    """
    def __init__(self, stream_manager=None):
        self.stream_manager = stream_manager
        self.browser_manager = PlaywrightSessionManager(stream_manager=stream_manager)
        self.db_manager = DatabaseManager()
        self.atag_processor: Optional[ATAGProcessor] = None
        self.llm = None
        self.search_tool = None
        self.initialized = False

    async def initialize(self):
        """Eagerly initializes execution LLMs, search utilities, and subprocess processors."""
        if self.initialized:
            return

        logger.info("Initializing multi-agent orchestrator system...")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        self.llm = ChatOpenRouter(
            model_name="google/gemini-3-flash-preview" if os.getenv("USE_FLASH") else "google/gemini-3.5-flash",
            openrouter_api_key=api_key,
            temperature=0.4,
            max_tokens=8192
        )
        self.search_tool = TavilySearch(max_results=3)
        self.atag_processor = ATAGProcessor(self.llm)
        
        # Pre-warm browser and MCP for a default system session to ensure connectivity
        try:
            logger.info("Pre-warming browser and MCP tools...")
            # await self.browser_manager.ensure_browser_launched("system-init")
            session_obj = self.browser_manager.sessions.get("system-init")
            if session_obj:
                port = session_obj.get("port", 9222)
                mcp = MCPToolManager(cdp_url=f"http://localhost:{port}")
                await mcp.initialize()
                session_obj["mcp_manager"] = mcp
            logger.info("System pre-warm complete.")
        except Exception as e:
            logger.warning(f"System pre-warm failed (non-critical): {e}")

        self.initialized = True
        logger.info("Multi-agent orchestrator initialization complete.")

    async def process_chat_message(
        self,
        user_message_content: str,
        user_id: str,
        chat_id: str,
        
    ) -> str:
        """Adapts request parameters to run inside the stateful Multi-Agent Workflow."""
        if not self.initialized:
            await self.initialize()

        result = await self.process_message(user_id, user_message_content, chat_id)
        
        # FIX: Ensure we extract the string content regardless of which agent finished
        if isinstance(result, dict):
            return result.get("execution_result") or result.get("message") or "Agent completed with no summary."
        return str(result)

    async def process_message(self, user_id: str, user_message: str, chat_id: str) -> Dict[str, Any]:
        """
        Runs Agent 1 (Analysis) -> Agent 2 (Strategy) -> Agent 3 (Execution) with UI updates and Critic retries.
        """
        current_plan = [
            {"id": "1", "title": "Task 1: Analysis", "description": "Understanding user intent", "status": "pending", "priority": "high", "level": 0, "dependencies": [], "subtasks": [], "details": None},
            {"id": "2", "title": "Task 2: Strategy", "description": "Generating execution prompt", "status": "pending", "priority": "high", "level": 0, "dependencies": ["1"], "subtasks": [], "details": None},
            {"id": "3", "title": "Task 3: Execution", "description": "Running browser tools", "status": "pending", "priority": "high", "level": 0, "dependencies": ["2"], "subtasks": [], "details": None}
        ]

        async def update_ui(idx, status, input_data=None, output_data=None, error=None, details=None):
            current_plan[idx]["status"] = status
            if details:
                current_plan[idx]["details"] = details
            
            # Log to database
            await self.db_manager.log_agent_execution(
                user_id=user_id,
                chat_id=chat_id,
                stage=str(idx + 1),
                name=current_plan[idx]["title"],
                status=status.upper(),
                input_data=input_data,
                output_data=output_data,
                error=error
            )
            # Broadcast to UI
            if self.stream_manager:
                await self.stream_manager.broadcast_plan(chat_id, current_plan)

        try:
            if not self.initialized: await self.initialize()
            session = await self.db_manager.get_or_create_chat_session(user_id, chat_id)
            
            # Persist Human Message to DB
            async with AsyncSessionLocal() as db:
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

            state_data = deserialize_state(session.state_data if session else "{}")
            
            # --- Agent 1: Analysis ---
            await update_ui(0, "in-progress", input_data={"message": user_message})
            understanding = await self.atag_processor.run_input_understanding(user_message)
            task_summary = understanding.get("task_summary", "Processing...")
            await update_ui(0, "completed", output_data=understanding, details=f"Task Summary: {task_summary}")

            # --- Agent 2: Strategy ---
            await update_ui(1, "in-progress", input_data=understanding)
            confirmed_inputs = str(understanding.get("task_summary", user_message))
            execution_prompt = await self.atag_processor.run_execution_generation(user_message, confirmed_inputs)
            
            # Extract a clean summary of the prompt for the UI
            prompt_summary = execution_prompt.split("4. Execution Steps")[0].strip() if "4. Execution Steps" in execution_prompt else "Strategy generated."
            await update_ui(1, "completed", output_data={"prompt": execution_prompt}, details=f"Strategy:\n{prompt_summary}")

            # --- Agent 3: Execution (with Retries & Critic) ---
            retry_count = 0
            max_retries = 3
            last_error = None
            final_response = None

            while retry_count < max_retries:
                try:
                    await update_ui(2, "in-progress", input_data={"prompt": execution_prompt, "retry": retry_count})
                    await self.browser_manager.ensure_browser_launched(chat_id)
                    session_obj = self.browser_manager.sessions.get(chat_id)
                    
                    if not session_obj.get("mcp_manager"):
                        from src.agents.mcp_agent import MCPToolManager
                        port = session_obj.get("port", 9222)
                        session_obj["mcp_manager"] = MCPToolManager(cdp_url=f"http://localhost:{port}")
                    
                    mcp_manager = session_obj["mcp_manager"]
                    all_tools = await mcp_manager.get_tools()
                    if self.search_tool: all_tools.append(self.search_tool)

                    graph_input = {"messages": [HumanMessage(content=execution_prompt)]}
                    graph_output = await self._execute_tool_graph(graph_input, all_tools, chat_id)
                    
                    final_response = graph_output["messages"][-1].content
                    await update_ui(2, "completed", output_data={"response": final_response}, details=f"Task execution finished (Attempt {retry_count + 1}).")
                    break # Success!

                except Exception as e:
                    retry_count += 1
                    last_error = str(e)
                    logger.warning(f"Execution attempt {retry_count} failed: {last_error}")
                    
                    if retry_count < max_retries:
                        # Run Critic to revise the prompt
                        logger.info(f"Running Critic to revise prompt for attempt {retry_count + 1}...")
                        execution_prompt = await self.atag_processor.run_critic(user_message, execution_prompt, last_error)
                        
                        # Update UI with Critic's feedback
                        await update_ui(2, "in-progress", details=f"Attempt {retry_count} failed: {last_error[:50]}... Critic is revising strategy for Attempt {retry_count + 1}.")
                        
                        # Small delay to let browser stabilize
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"All {max_retries} attempts failed.")
                        await update_ui(2, "failed", error=last_error, details=f"All {max_retries} attempts failed. Last error: {last_error}")
                        final_response = f"I attempted the task {max_retries} times but encountered persistent errors. Last error: {last_error}"

            # Persist AI Message to DB with Plan Data
            ai_msg_id = str(uuid.uuid4())
            async with AsyncSessionLocal() as db:
                ai_msg = Message(
                    message_id=ai_msg_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    role="ai",
                    content=final_response,
                    plan_data=json.dumps(current_plan), # Save the final plan
                    created_at=datetime.now(timezone.utc)
                )
                db.add(ai_msg)
                await db.commit()

            return {
                "success": True,
                "execution_result": final_response,
                "message": {
                    "id": ai_msg_id,
                    "log_id": str(uuid.uuid4()), # FIX: Required by schema
                    "role": "ai",
                    "content": final_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "plan": current_plan
                },
                "plan": current_plan
            }

        except Exception as e:
            logger.error(f"Critical workflow failure: {str(e)}")
            return {
                "success": False,
                "execution_result": "Something went wrong. Please try again.",
                "error": str(e)
            }

    async def _execute_tool_graph(self, input_data: Dict[str, Any], tools: List[BaseTool], chat_id: str) -> Dict[str, Any]:
        """Creates and executes a temporary LangGraph to handle tool calling for Agent 3."""
        
        # Define the tool node
        tool_node = ToolNode(tools)
        
        # Bind tools to the LLM
        llm_with_tools = self.llm.bind_tools(tools)

        # Define the logic for the agent
        async def call_model(state: AgentState):
            messages = state['messages']
            response = await llm_with_tools.ainvoke(messages)
            
            # Log tool calls if any
            if response.tool_calls:
                for tc in response.tool_calls:
                    await self.db_manager.log_tool_execution(
                        chat_id=chat_id,
                        agent_id="3",
                        tool_name=tc["name"],
                        status="IN_PROGRESS",
                        tool_input=tc["args"]
                    )
                    # Broadcast tool activity to browser area
                    if self.stream_manager:
                        await self.stream_manager.broadcast_frame(
                            json.dumps({"type": "tool_start", "tool": tc["name"], "args": tc["args"]}), 
                            chat_id,
                            is_tool=True
                        )
            
            return {"messages": [response]}

        def should_continue(state: AgentState):
            messages = state['messages']
            last_message = messages[-1]
            if last_message.tool_calls:
                return "tools"
            return END

        # Build the graph
        workflow = StateGraph(AgentState)
        
        # Add a system message to enforce plan following and tool selection
        async def call_model(state: AgentState):
            messages = state['messages']
            if len(messages) == 1: # First call
                messages = [SystemMessage(content=(
                    "You are a strict execution agent. You have been given a specific multi-step plan. "
                    "Your ONLY goal is to complete every step of that plan. "
                    "TOOL SELECTION RULES: "
                    "1. Use 'tavily_search' ONLY for general web searching or finding URLs. "
                    "2. Use 'browser_' tools (Playwright) for ALL interactions: form filling, clicking, booking, and checking availability. "
                    "Do not stop after navigating. Do not ask the user for clarification. "
                    "If there is a form, fill it. If there is a button, click it. "
                    "If an element is missing, use your tools to find it. "
                    "Continue until you have the final result requested by the user."
                ))] + messages
            
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}

        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        app = workflow.compile()
        return await app.ainvoke(input_data)

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
        await self.browser_manager.shutdown_all()


# ============================================================
# INSTANTIATE GLOBAL EXPORTS FOR COMPATIBILITY
# ============================================================
brain = Brain()
db_manager = DatabaseManager()