import sys
import os
import asyncio
import json

from sqlalchemy import select
from src.database.chat_db import AsyncSessionLocal, AgentExecutionLog

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AgentExecutionLog).order_by(AgentExecutionLog.created_at.desc()).limit(5))
        logs = result.scalars().all()
        print(f"Retrieved {len(logs)} log entries:")
        for log in logs:
            print(f"ID: {log.id}")
            print(f"Created At: {log.created_at}")
            print(f"Status: {log.status}")
            print(f"Token Usage Raw: {log.token_usage}")
            print(f"Cost: {log.cost}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
