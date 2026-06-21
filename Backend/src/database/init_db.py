import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.database.chat_db import Base, SERVER_URL
from src.utils.logger import logger

load_dotenv(".env")

async def migrate_tables(conn):
    """Add missing columns to existing tables."""
    try:
        # Check if state_data column exists in chat_sessions
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'chat_sessions' 
            AND COLUMN_NAME = 'state_data'
        """))
        state_data_exists = result.scalar() > 0
        
        if not state_data_exists:
            logger.info("Adding missing 'state_data' column to chat_sessions table...")
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN state_data TEXT"))
            logger.info("Successfully added 'state_data' column.")

        # Check if status column exists in chat_sessions
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'chat_sessions' 
            AND COLUMN_NAME = 'status'
        """))
        status_exists = result.scalar() > 0
        
        if not status_exists:
            logger.info("Adding missing 'status' column to chat_sessions table...")
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
            logger.info("Successfully added 'status' column.")
        # Check if plan_data column exists in messages
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'messages' 
            AND COLUMN_NAME = 'plan_data'
        """))
        plan_data_exists = result.scalar() > 0
        
        if not plan_data_exists:
            logger.info("Adding missing 'plan_data' column to messages table...")
            await conn.execute(text("ALTER TABLE messages ADD COLUMN plan_data TEXT"))
            logger.info("Successfully added 'plan_data' column.")
            
    except Exception as e:
        logger.warning(f"Migration check encountered an issue (may be expected): {e}")

async def init_database():
    """
    Checks if the database and tables exist. If not, creates them.
    Also runs migrations for existing tables.
    """
    db_name = os.getenv("DATABASE_NAME", "sciparser_v1")

    # 1. Connect to MySQL server (without specifying a database) to create the DB
    server_engine = create_async_engine(
        SERVER_URL, 
        echo=False,
        connect_args={"charset": "utf8mb4"}
    )

    try:
        logger.info(f"Connecting to MySQL server to create database '{db_name}'...")
        async with server_engine.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            await conn.execute(text(f"ALTER DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            logger.info(f"Database '{db_name}' checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database '{db_name}': {e}")
        raise
    finally:
        await server_engine.dispose()

    # 2. Connect to the actual database and create tables
    from src.database.chat_db import engine as app_engine
    
    try:
        logger.info(f"Creating tables in database '{db_name}'...")
        async with app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables checked/created successfully.")
            
            # Run migrations for existing tables
            await migrate_tables(conn)
    except Exception as e:
        logger.error(f"Error creating tables in database '{db_name}': {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_database())
