import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.database.chat_db import Base, engine as app_engine, AsyncSessionLocal
from src.utils.logger import logger

async def create_database_if_not_exists():
    """
    Checks if the database specified in config.DATABASE_URL exists,
    and creates it if it does not.
    """
    from urllib.parse import urlparse, urlunparse
    from src import config
    from src.database.chat_db import _build_asyncpg_url

    raw_url = config.DATABASE_URL
    if not raw_url:
        logger.error("DATABASE_URL is not set.")
        return

    parsed = urlparse(raw_url)
    db_name = parsed.path.lstrip('/')
    if not db_name:
        logger.error("No database name found in DATABASE_URL.")
        return

    # Connect to 'postgres' default database to perform database check/creation
    postgres_parsed = parsed._replace(path='/postgres')
    postgres_url = _build_asyncpg_url(urlunparse(postgres_parsed))

    # We must use isolation_level="AUTOCOMMIT" so CREATE DATABASE is run outside a transaction block
    temp_engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
    try:
        async with temp_engine.connect() as conn:
            # Query pg_database to check if database exists
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.scalar()
            if not exists:
                logger.info(f"Database '{db_name}' does not exist. Creating database...")
                # CREATE DATABASE cannot be parameterized, but db_name comes from parsed config url path (safe)
                await conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"Database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
    except Exception as e:
        logger.error(f"Error checking/creating database '{db_name}': {e}")
    finally:
        await temp_engine.dispose()
        
    # Attempt to install pgvector on the actual database
    try:
        app_url_autocommit = config.DATABASE_URL
        if app_url_autocommit.startswith("postgresql://"):
            app_url_autocommit = app_url_autocommit.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif app_url_autocommit.startswith("postgres://"):
            app_url_autocommit = app_url_autocommit.replace("postgres://", "postgresql+asyncpg://", 1)
        
        pg_engine = create_async_engine(app_url_autocommit, isolation_level="AUTOCOMMIT")
        async with pg_engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("pgvector extension verified.")
        await pg_engine.dispose()
    except Exception as e:
        logger.warning(f"Failed to initialize pgvector. RAG memory may not work. Error: {e}")

async def init_database():
    """
    Creates all database tables if they don't exist.
    Uses Replit's built-in PostgreSQL database.
    """
    await create_database_if_not_exists()
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
            await conn.execute(text(
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS screenshots TEXT"
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
            # LLM provider columns — stored per-user so admins can configure custom
            # providers (Groq / NVIDIA / Ollama) that override the global OpenRouter
            # default. api_key is kept nullable so that provider selection without a
            # key can still be useful for admin-managed deployments where keys live
            # in env vars or a vault.
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(20)"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100)"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key TEXT"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_base_url TEXT"
            ))
            # llm_requests analytics table. The Alembic migration
            # (alembic/versions/20260708_0001_create_llm_requests.py) is the
            # source of truth going forward; this CREATE TABLE IF NOT EXISTS is
            # kept as a defensive fallback for deployments that pick up the code
            # change without running `alembic upgrade head` first.
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
                    deleted_at TIMESTAMPTZ,
                    organization_id VARCHAR(50),
                    agent_run_id VARCHAR(36),
                    agent_name VARCHAR(50),
                    agent_stage VARCHAR(20),
                    queue_time_ms INTEGER DEFAULT 0,
                    processing_time_ms INTEGER DEFAULT 0,
                    tool_name VARCHAR(50),
                    mcp_server VARCHAR(50),
                    browser_session VARCHAR(100),
                    cache_hit BOOLEAN DEFAULT FALSE,
                    streaming BOOLEAN DEFAULT FALSE,
                    request_size INTEGER DEFAULT 0,
                    response_size INTEGER DEFAULT 0,
                    temperature DOUBLE PRECISION,
                    top_p DOUBLE PRECISION,
                    max_tokens INTEGER
                )
            """))
            # Run column migration ALTER TABLE commands
            for col_name, col_type in [
                ("organization_id", "VARCHAR(50)"),
                ("agent_run_id", "VARCHAR(36)"),
                ("agent_name", "VARCHAR(50)"),
                ("agent_stage", "VARCHAR(20)"),
                ("queue_time_ms", "INTEGER DEFAULT 0"),
                ("processing_time_ms", "INTEGER DEFAULT 0"),
                ("tool_name", "VARCHAR(50)"),
                ("mcp_server", "VARCHAR(50)"),
                ("browser_session", "VARCHAR(100)"),
                ("cache_hit", "BOOLEAN DEFAULT FALSE"),
                ("streaming", "BOOLEAN DEFAULT FALSE"),
                ("request_size", "INTEGER DEFAULT 0"),
                ("response_size", "INTEGER DEFAULT 0"),
                ("temperature", "DOUBLE PRECISION"),
                ("top_p", "DOUBLE PRECISION"),
                ("max_tokens", "INTEGER")
            ]:
                await conn.execute(text(f"ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
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

            # Create new admin budget and telemetry tables
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS budget_limits (
                    id BIGSERIAL PRIMARY KEY,
                    scope VARCHAR(50) NOT NULL,
                    scope_id VARCHAR(100) NOT NULL,
                    daily_budget DOUBLE PRECISION,
                    monthly_budget DOUBLE PRECISION,
                    current_daily_spend DOUBLE PRECISION DEFAULT 0,
                    current_monthly_spend DOUBLE PRECISION DEFAULT 0,
                    alert_thresholds VARCHAR(100) DEFAULT '50,75,90,100',
                    action_at_100 VARCHAR(50) DEFAULT 'switch_cheaper_model'
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alert_notifications (
                    id VARCHAR(36) PRIMARY KEY,
                    severity VARCHAR(20) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS metric_snapshots (
                    id BIGSERIAL PRIMARY KEY,
                    cpu_percent DOUBLE PRECISION,
                    ram_percent DOUBLE PRECISION,
                    active_websockets INTEGER,
                    active_browser_instances INTEGER,
                    db_size_bytes BIGINT,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_error_logs (
                    id VARCHAR(36) PRIMARY KEY,
                    error_id VARCHAR(50) NOT NULL UNIQUE,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    user_id VARCHAR(36),
                    conversation_id VARCHAR(100),
                    agent_run_id VARCHAR(36),
                    api_endpoint VARCHAR(255),
                    http_method VARCHAR(10),
                    provider VARCHAR(50),
                    model VARCHAR(100),
                    tool_name VARCHAR(50),
                    mcp_server VARCHAR(50),
                    browser_session VARCHAR(100),
                    severity VARCHAR(20) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    error_code VARCHAR(50) NOT NULL,
                    error_message TEXT NOT NULL,
                    stacktrace TEXT,
                    retry_count INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_budget_limits_scope_id ON budget_limits (scope_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_metric_snapshots_timestamp ON metric_snapshots (timestamp)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_system_error_logs_error_id ON system_error_logs (error_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_system_error_logs_timestamp ON system_error_logs (timestamp)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_system_error_logs_user_id ON system_error_logs (user_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_system_error_logs_conversation_id ON system_error_logs (conversation_id)"
            ))

            logger.info("Database tables checked/created successfully.")

        # Attempt to add RAG embedding columns in an isolated transaction
        try:
            async with app_engine.begin() as conn_rag:
                await conn_rag.execute(text("ALTER TABLE memory_episodic ADD COLUMN IF NOT EXISTS embedding vector(384)"))
                await conn_rag.execute(text("ALTER TABLE memory_semantic ADD COLUMN IF NOT EXISTS embedding vector(384)"))
                await conn_rag.execute(text("ALTER TABLE memory_procedural ADD COLUMN IF NOT EXISTS embedding vector(384)"))
                logger.info("RAG memory embedding columns verified.")
        except Exception as e:
            logger.warning(f"RAG embedding columns could not be created (likely missing pgvector extension). Error: {e}")

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
