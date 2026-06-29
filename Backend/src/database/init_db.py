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

        # Check if tool_calls column exists in messages
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'messages' 
            AND COLUMN_NAME = 'tool_calls'
        """))
        tool_calls_exists = result.scalar() > 0
        
        if not tool_calls_exists:
            logger.info("Adding missing 'tool_calls' column to messages table...")
            await conn.execute(text("ALTER TABLE messages ADD COLUMN tool_calls TEXT"))
            logger.info("Successfully added 'tool_calls' column.")

        # Check if form_data column exists in messages
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'messages' 
            AND COLUMN_NAME = 'form_data'
        """))
        form_data_exists = result.scalar() > 0
        
        if not form_data_exists:
            logger.info("Adding missing 'form_data' column to messages table...")
            await conn.execute(text("ALTER TABLE messages ADD COLUMN form_data TEXT"))
            logger.info("Successfully added 'form_data' column.")

        # --- Schedule Table Migrations ---
        
        # Check if user_id column exists in schedules
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedules' 
            AND COLUMN_NAME = 'user_id'
        """))
        user_id_exists = result.scalar() > 0
        
        if not user_id_exists:
            logger.info("Adding missing 'user_id' column to schedules table...")
            await conn.execute(text("ALTER TABLE schedules ADD COLUMN user_id VARCHAR(36) NOT NULL"))
            logger.info("Successfully added 'user_id' column.")

        # Check if title column exists in schedules
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedules' 
            AND COLUMN_NAME = 'title'
        """))
        title_exists = result.scalar() > 0
        
        if not title_exists:
            logger.info("Adding missing 'title' column to schedules table...")
            await conn.execute(text("ALTER TABLE schedules ADD COLUMN title VARCHAR(255)"))
            logger.info("Successfully added 'title' column.")

        # Check if selected_data column exists in schedules
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedules' 
            AND COLUMN_NAME = 'selected_data'
        """))
        selected_data_exists = result.scalar() > 0
        
        if not selected_data_exists:
            logger.info("Adding missing 'selected_data' column to schedules table...")
            await conn.execute(text("ALTER TABLE schedules ADD COLUMN selected_data TEXT"))
            logger.info("Successfully added 'selected_data' column.")

        # Check if updated_at column exists in schedules
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedules' 
            AND COLUMN_NAME = 'updated_at'
        """))
        updated_at_exists = result.scalar() > 0
        
        if not updated_at_exists:
            logger.info("Adding missing 'updated_at' column to schedules table...")
            await conn.execute(text("ALTER TABLE schedules ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
            logger.info("Successfully added 'updated_at' column.")
        
        # Check if plan_data column exists in schedules
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedules' 
            AND COLUMN_NAME = 'plan_data'
        """))
        if result.scalar() == 0:
            logger.info("Adding missing 'plan_data' column to schedules table...")
            await conn.execute(text("ALTER TABLE schedules ADD COLUMN plan_data TEXT"))

        # Check if engine column exists in schedule_runs
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedule_runs' 
            AND COLUMN_NAME = 'engine'
        """))
        if result.scalar() == 0:
            logger.info("Adding missing 'engine' column to schedule_runs table...")
            await conn.execute(text("ALTER TABLE schedule_runs ADD COLUMN engine VARCHAR(50)"))

        # Check if attempt column exists in schedule_runs
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedule_runs' 
            AND COLUMN_NAME = 'attempt'
        """))
        if result.scalar() == 0:
            logger.info("Adding missing 'attempt' column to schedule_runs table...")
            await conn.execute(text("ALTER TABLE schedule_runs ADD COLUMN attempt INT DEFAULT 1"))

        # Check if finished_at column exists in schedule_runs
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'schedule_runs' 
            AND COLUMN_NAME = 'finished_at'
        """))
        if result.scalar() == 0:
            logger.info("Adding missing 'finished_at' column to schedule_runs table...")
            await conn.execute(text("ALTER TABLE schedule_runs ADD COLUMN finished_at TIMESTAMP NULL"))
        
        # Update tool_output to LONGTEXT to handle large outputs
        logger.info("Ensuring 'tool_output' column in tool_execution_logs is LONGTEXT...")
        await conn.execute(text("ALTER TABLE tool_execution_logs MODIFY COLUMN tool_output LONGTEXT"))
        logger.info("Successfully updated 'tool_output' column.")

        # --- Token Usage and Cost Migrations ---
        
        # Check if token_usage column exists in messages
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'messages' AND COLUMN_NAME = 'token_usage'
        """))
        if result.scalar() == 0:
            logger.info("Adding 'token_usage' column to messages...")
            await conn.execute(text("ALTER TABLE messages ADD COLUMN token_usage TEXT"))

        # Check if cost column exists in messages
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'messages' AND COLUMN_NAME = 'cost'
        """))
        if result.scalar() == 0:
            logger.info("Adding 'cost' column to messages...")
            await conn.execute(text("ALTER TABLE messages ADD COLUMN cost TEXT"))

        # Check if token_usage column exists in agent_execution_logs
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_execution_logs' AND COLUMN_NAME = 'token_usage'
        """))
        if result.scalar() == 0:
            logger.info("Adding 'token_usage' column to agent_execution_logs...")
            await conn.execute(text("ALTER TABLE agent_execution_logs ADD COLUMN token_usage TEXT"))

        # Check if cost column exists in agent_execution_logs
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_execution_logs' AND COLUMN_NAME = 'cost'
        """))
        if result.scalar() == 0:
            logger.info("Adding 'cost' column to agent_execution_logs...")
            await conn.execute(text("ALTER TABLE agent_execution_logs ADD COLUMN cost TEXT"))
            
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
