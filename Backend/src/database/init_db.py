import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.database.chat_db import Base, engine as app_engine, AsyncSessionLocal
from src.utils.logger import logger

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
            await conn.execute(text(
                "ALTER TABLE users DROP COLUMN IF EXISTS floppydata_api_key"
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
            # Schedule timezone + browser mode columns
            await conn.execute(text(
                "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS timezone VARCHAR(100) DEFAULT 'America/New_York'"
            ))
            await conn.execute(text(
                "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS headless BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            # Weekly schedule day-of-week picker
            await conn.execute(text(
                "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS schedule_day_of_week VARCHAR(10) DEFAULT 'mon'"
            ))
            # Task #121: drop the never-written screenshot_url column so it can't
            # accidentally start holding raw screenshot frames (a secrets leak risk).
            await conn.execute(text(
                "ALTER TABLE tool_execution_logs DROP COLUMN IF EXISTS screenshot_url"
            ))
            # Task #127: role-based access control + account status.
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'"
            ))
            # Task #146: usage credits. Existing users get the same 5.0 default as
            # new signups so nothing breaks for current accounts after this ships.
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS credit_balance DOUBLE PRECISION NOT NULL DEFAULT 5.0"
            ))
            # Task #176: llm_requests analytics table.
            # Base.metadata.create_all above creates this for fresh installs; the
            # explicit CREATE TABLE IF NOT EXISTS ensures existing deployments pick
            # it up without an Alembic migration.
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS llm_requests (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    chat_id VARCHAR(100),
                    model VARCHAR(100) NOT NULL,
                    source VARCHAR(50) NOT NULL,
                    system_tokens INTEGER NOT NULL DEFAULT 0,
                    user_tokens INTEGER NOT NULL DEFAULT 0,
                    history_tokens INTEGER NOT NULL DEFAULT 0,
                    memory_tokens INTEGER NOT NULL DEFAULT 0,
                    tool_tokens INTEGER NOT NULL DEFAULT 0,
                    rag_tokens INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
                    latency_ms INTEGER,
                    finish_reason VARCHAR(50),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    deleted_at TIMESTAMPTZ
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_llm_requests_user_created "
                "ON llm_requests (user_id, created_at)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_llm_requests_chat_created "
                "ON llm_requests (chat_id, created_at)"
            ))

            # Task #127 (post-review fix): admin user deletion must cascade to a
            # user's owned rows instead of failing on FK constraints. messages.user_id
            # and chat_sessions.user_id were created without ON DELETE CASCADE;
            # re-create those constraints with CASCADE so admin_delete_user works for
            # users who already have chat history.
            await conn.execute(text("""
                DO $$
                DECLARE
                    fk_name TEXT;
                BEGIN
                    SELECT tc.constraint_name INTO fk_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = 'messages'
                        AND tc.constraint_type = 'FOREIGN KEY'
                        AND kcu.column_name = 'user_id';
                    IF fk_name IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE messages DROP CONSTRAINT %I', fk_name);
                    END IF;
                    ALTER TABLE messages
                        ADD CONSTRAINT messages_user_id_fkey
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
                END $$;
            """))
            await conn.execute(text("""
                DO $$
                DECLARE
                    fk_name TEXT;
                BEGIN
                    SELECT tc.constraint_name INTO fk_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = 'chat_sessions'
                        AND tc.constraint_type = 'FOREIGN KEY'
                        AND kcu.column_name = 'user_id';
                    IF fk_name IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE chat_sessions DROP CONSTRAINT %I', fk_name);
                    END IF;
                    ALTER TABLE chat_sessions
                        ADD CONSTRAINT chat_sessions_user_id_fkey
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
                END $$;
            """))
            logger.info("Database tables checked/created successfully.")

        # Bootstrap: if no admin exists yet, promote the earliest-created user
        # to admin so there's always a way into the Admin Dashboard. Runs in
        # its own transaction after table/column creation above is committed.
        try:
            async with AsyncSessionLocal() as session:
                admin_count_result = await session.execute(
                    text("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                )
                admin_count = admin_count_result.scalar_one()
                if admin_count == 0:
                    first_user_result = await session.execute(
                        text("SELECT user_id FROM users ORDER BY created_at ASC LIMIT 1")
                    )
                    row = first_user_result.first()
                    if row:
                        await session.execute(
                            text("UPDATE users SET role = 'admin' WHERE user_id = :uid"),
                            {"uid": row[0]},
                        )
                        await session.commit()
                        logger.info(f"Bootstrapped admin role for earliest user (user_id={row[0]}).")
        except Exception as e:
            logger.warning(f"Admin bootstrap check failed (non-fatal): {e}")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_database())
