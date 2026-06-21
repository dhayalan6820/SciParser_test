import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.chat_db import AsyncSessionLocal, AgentExecutionLog, ToolExecutionLog
from src.utils.logger import logger

class AgentManager:
    """Manages agent execution tracking and history."""
    
    def __init__(self):
        self.stream_manager = None # Will be set in main.py lifespan
        self.agent_history: Dict[str, List[Dict]] = {}
        self.tool_history: Dict[str, List[Dict]] = {}
        self.current_status: Dict[str, Dict] = {}
    
    async def log_agent_stage(
        self,
        chat_id: str,
        user_id: str,
        agent_stage: str,
        stage_name: str,
        input_data: dict = None,
        output_data: dict = None,
        status: str = "IN_PROGRESS",
        error_message: str = None
    ):
        """Log an agent execution stage to the database."""
        try:
            async with AsyncSessionLocal() as db:
                log_entry = AgentExecutionLog(
                    chat_id=chat_id,
                    user_id=user_id,
                    agent_stage=agent_stage,
                    stage_name=stage_name,
                    input_data=json.dumps(input_data),
                    output_data=json.dumps(output_data),
                    status=status,
                    error_message=error_message,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(log_entry)
                await db.commit()
                await db.refresh(log_entry)
                
                # Update in-memory status
                self.current_status[chat_id] = {
                    "agent_stage": agent_stage,
                    "stage_name": stage_name,
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                logger.info(f"[AgentManager] Logged {agent_stage} for chat {chat_id}: {status}")
                
                # Broadcast update via WebSocket to prevent frontend polling
                if self.stream_manager:
                    update_payload = {
                        "event": "agent_update",
                        "data": {
                            "agent_stage": agent_stage,
                            "stage_name": stage_name,
                            "status": status,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                    await self.stream_manager.broadcast_status(json.dumps(update_payload), chat_id)
        except Exception as e:
            logger.error(f"[AgentManager] Failed to log agent stage: {e}")
    
    async def log_tool_execution(
        self,
        chat_id: str,
        agent_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: dict,
        status: str,
        error_message: Optional[str] = None
    ):
        """Log a tool execution to the database."""
        try:
            async with AsyncSessionLocal() as db:
                log_entry = ToolExecutionLog(
                    chat_id=chat_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    tool_input=json.dumps(tool_input),
                    tool_output=json.dumps(tool_output),
                    status=status,
                    error_message=error_message,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(log_entry)
                await db.commit()
                await db.refresh(log_entry)
                
                logger.info(f"[AgentManager] Logged tool {tool_name} for chat {chat_id}: {status}")
        except Exception as e:
            logger.error(f"[AgentManager] Failed to log tool execution: {e}")
    
    async def get_agent_history(self, chat_id: str) -> List[Dict]:
        """Get all agent execution logs for a chat."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AgentExecutionLog)
                    .where(AgentExecutionLog.chat_id == chat_id)
                    .order_by(AgentExecutionLog.created_at)
                )
                logs = result.scalars().all()
                
                return [
                    {
                        "agent_stage": log.agent_stage,
                        "stage_name": log.stage_name,
                        "input_data": json.loads(log.input_data) if log.input_data else {},
                        "output_data": json.loads(log.output_data) if log.output_data else {},
                        "status": log.status,
                        "error_message": log.error_message,
                        "created_at": log.created_at.isoformat() if log.created_at else None
                    }
                    for log in logs
                ]
        except Exception as e:
            logger.error(f"[AgentManager] Failed to get agent history: {e}")
            return []
    
    async def get_tool_history(self, chat_id: str) -> List[Dict]:
        """Get all tool execution logs for a chat."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ToolExecutionLog)
                    .where(ToolExecutionLog.chat_id == chat_id)
                    .order_by(ToolExecutionLog.created_at)
                )
                logs = result.scalars().all()
                
                return [
                    {
                        "agent_id": log.agent_id,
                        "tool_name": log.tool_name,
                        "tool_input": json.loads(log.tool_input) if log.tool_input else {},
                        "tool_output": json.loads(log.tool_output) if log.tool_output else {},
                        "status": log.status,
                        "error_message": log.error_message,
                        "created_at": log.created_at.isoformat() if log.created_at else None
                    }
                    for log in logs
                ]
        except Exception as e:
            logger.error(f"[AgentManager] Failed to get tool history: {e}")
            return []
    
    async def get_current_status(self, chat_id: str) -> Dict:
        """Get current agent execution status for a chat."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AgentExecutionLog)
                    .where(AgentExecutionLog.chat_id == chat_id)
                    .order_by(AgentExecutionLog.created_at.desc())
                    .limit(1)
                )
                latest_log = result.scalar_one_or_none()
                
                if latest_log:
                    return {
                        "chat_id": chat_id,
                        "agent_stage": latest_log.agent_stage,
                        "stage_name": latest_log.stage_name,
                        "status": latest_log.status,
                        "error_message": latest_log.error_message,
                        "timestamp": latest_log.created_at.isoformat() if latest_log.created_at else None
                    }
                
                return {
                    "chat_id": chat_id,
                    "agent_stage": None,
                    "stage_name": None,
                    "status": "IDLE",
                    "error_message": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"[AgentManager] Error getting current status: {e}")
            return {
                "chat_id": chat_id,
                "agent_stage": None,
                "stage_name": None,
                "status": "ERROR",
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Global instance
agent_manager = AgentManager()