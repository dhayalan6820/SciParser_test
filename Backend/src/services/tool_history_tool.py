from typing import Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import json
from sqlalchemy import select

def create_fetch_past_tool_logs_tool(chat_id: str) -> StructuredTool:
    class FetchPastLogsInput(BaseModel):
        limit: int = Field(default=5, description="Number of past tool executions to retrieve (default 5, max 20).")
        tool_name_filter: Optional[str] = Field(default=None, description="Optional. If provided, only returns logs for this specific tool name (e.g., 'browser_extract_raw').")

    async def _fetch_past_logs(limit: int = 5, tool_name_filter: Optional[str] = None) -> str:
        """
        Retrieves the raw output of tools executed previously in THIS chat session.
        Use this tool to recover large extracted data (like HTML or scraped tables) that is no longer in your immediate context window, 
        so you don't have to re-browse websites to get data you already extracted.
        """
        from src.database.chat_db import AsyncSessionLocal, ToolExecutionLog
        
        async with AsyncSessionLocal() as db:
            stmt = select(ToolExecutionLog).where(ToolExecutionLog.chat_id == chat_id)
            if tool_name_filter:
                stmt = stmt.where(ToolExecutionLog.tool_name == tool_name_filter)
            stmt = stmt.order_by(ToolExecutionLog.created_at.desc()).limit(min(limit, 20))
            
            result = await db.execute(stmt)
            logs = result.scalars().all()
            
            if not logs:
                return f"No past tool logs found for chat_id {chat_id}" + (f" and tool {tool_name_filter}" if tool_name_filter else "")
            
            output = []
            # Return in chronological order
            for log in reversed(logs):
                # Truncate output to prevent blowing up the context window completely
                out_str = str(log.tool_output)
                if len(out_str) > 8000:
                    out_str = out_str[:8000] + "\n... [TRUNCATED - output too large]"
                    
                output.append(f"--- LOG ID: {log.id} ---\nTool: {log.tool_name}\nInput: {log.tool_input}\nStatus: {log.status}\nOutput:\n{out_str}\n")
            
            return "\n".join(output)

    return StructuredTool.from_function(
        func=_fetch_past_logs,
        name="fetch_past_tool_logs",
        description="Retrieves the raw output of tools executed previously in THIS chat session to recover lost context.",
        args_schema=FetchPastLogsInput,
        coroutine=_fetch_past_logs
    )
