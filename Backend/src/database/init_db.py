import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.database.chat_db import Base, engine as app_engine
from src.utils.logger import logger

load_dotenv()

async def init_database():
    """
    Creates all database tables if they don't exist.
    Uses Replit's built-in PostgreSQL database.
    """
    try:
        logger.info("Creating/verifying database tables...")
        async with app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Add session_state column to existing tables if it doesn't exist yet
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS session_state TEXT"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS proxy_url TEXT"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS browser_engine VARCHAR(50) DEFAULT NULL"
            ))
            # Reset rows that were seeded with the migration default so env-var override
            # works correctly for self-hosted deployments. Resetting 'camoufox' → NULL is
            # safe: the effective engine is unchanged (env fallback also yields camoufox
            # when BROWSER_ENGINE is unset). Explicit 'chrome' rows are untouched.
            await conn.execute(text(
                "UPDATE users SET browser_engine = NULL WHERE browser_engine = 'camoufox'"
            ))
            # Schedule auto-run and email columns
            await conn.execute(text(
                "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS next_run TIMESTAMPTZ"
            ))
            await conn.execute(text(
                "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS last_run TIMESTAMPTZ"
            ))
            logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_database())
