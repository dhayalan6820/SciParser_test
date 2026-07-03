from typing import List
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    TIMESTAMP, BigInteger, Boolean, Column, ForeignKey, Float, Index, Integer, String, Text, DateTime
)

from sqlalchemy.orm import Mapped, declarative_base, relationship
from enum import Enum as PyEnum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src import config

from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

_raw_url = config.DATABASE_URL

def _build_asyncpg_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    parsed = urlparse(raw_url)
    qs = parse_qs(parsed.query)
    qs.pop("sslmode", None)
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    cleaned = parsed._replace(query=new_query)
    return urlunparse(cleaned)

DATABASE_URL = _build_asyncpg_url(_raw_url)
SERVER_URL = DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)
Base = declarative_base()

async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

# --- Database Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    proxy_url = Column(Text, nullable=True)
    browser_engine = Column(String(50), nullable=True, default=None)
    role = Column(String(20), nullable=False, default="user", server_default="user")
    status = Column(String(20), nullable=False, default="active", server_default="active")
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages: Mapped[List["Message"]] = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_logs: Mapped[List["ChatLog"]] = relationship("ChatLog", back_populates="user", cascade="all, delete-orphan")

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user: Mapped["User"] = relationship("User", back_populates="chat_logs")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(100), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    plan_data = Column(Text)
    tool_calls = Column(Text)
    form_data = Column(Text)
    token_usage = Column(Text)
    cost = Column(Text)

    user: Mapped["User"] = relationship("User", back_populates="messages")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(100), primary_key=True, default=lambda: f"thread-{uuid.uuid4()}")
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    state_data = Column(Text)
    session_state = Column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    schedule_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(100), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True)

    title = Column(String(255), nullable=True)
    selected_data = Column(Text)
    user_prompt = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    plan_data = Column(Text, nullable=True)
    playwright_steps = Column(Text, nullable=True)
    extracted_content = Column(Text, nullable=True)
    generated_script = Column(Text, nullable=True)

    status = Column(String(20), default="completed")
    schedule_type = Column(String(20), default="manual")
    schedule_time = Column(String(50), nullable=True)
    schedule_day_of_week = Column(String(10), nullable=True)
    timezone = Column(String(100), nullable=True)
    headless = Column(Boolean, default=True, nullable=False)
    cron_expression = Column(String(50), nullable=True)
    email_recipient = Column(String(255), nullable=True)
    next_run = Column(TIMESTAMP(timezone=True), nullable=True)
    last_run = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ScheduleRun(Base):
    """Tracks each execution of a schedule."""
    __tablename__ = "schedule_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    schedule_id = Column(String(36), ForeignKey("schedules.schedule_id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(20), default="running")
    engine = Column(String(50), nullable=True)
    attempt = Column(Integer, default=1)
    output = Column(Text)
    error_log = Column(Text)
    duration_seconds = Column(Integer)

    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ToolExecutionStatus(PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class AgentExecutionLog(Base):
    """Tracks each agent's execution stage and output."""
    __tablename__ = "agent_execution_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    agent_stage = Column(String(20), nullable=False)
    stage_name = Column(String(100), nullable=False)
    input_data = Column(Text)
    output_data = Column(Text)
    status = Column(String(20), default="PENDING")
    error_message = Column(Text)
    token_usage = Column(Text)
    cost = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class LoginEvent(Base):
    """Tracks login attempts (success and failure) for admin security monitoring."""
    __tablename__ = "login_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    username_attempted = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class ToolExecutionLog(Base):
    """Tracks tool executions by Agent 3."""
    __tablename__ = "tool_execution_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(String(20), nullable=False)
    tool_name = Column(String(50), nullable=False)
    tool_input = Column(Text)
    tool_output = Column(Text)
    status = Column(String(20), default="PENDING")
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    # NOTE (Task #121): a `screenshot_url` column used to live here and was
    # never written to by either write site (DatabaseManager.log_tool_execution
    # in brain.py / AgentManager.log_tool_execution in agent_manager.py). It
    # was removed because a dead column earmarked for image data is an
    # attractive nuisance: a future "just store a debug screenshot link"
    # change could start populating it with a live-typing frame that shows a
    # password/OTP being entered, reopening the exact leak Task #120 closed.
    # If a legitimate need for a screenshot reference arises, it must only
    # ever store a link to a REDACTED/blurred snapshot — never a raw frame —
    # and should be reviewed against Backend/tests/test_screenshot_leakage.py.


# ─────────────────────────────────────────────
#  COGNITIVE MEMORY TABLES
# ─────────────────────────────────────────────

class MemoryEpisodic(Base):
    """Specific run experiences per user/domain."""
    __tablename__ = "memory_episodic"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    task_summary = Column(Text, nullable=False)
    outcome = Column(String(20), nullable=False)        # SUCCESS | FAIL | PARTIAL
    key_steps = Column(Text)                            # JSON array of compact step records
    tags = Column(Text)                                 # JSON array of keyword strings
    confidence_score = Column(Float, default=1.0)
    access_count = Column(Integer, default=0)
    last_accessed = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_memory_episodic_user_confidence", "user_id", "confidence_score"),
    )


class MemorySemantic(Base):
    """Factual knowledge about a domain (selectors, URLs, bot-detection quirks)."""
    __tablename__ = "memory_semantic"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    fact_key = Column(String(255), nullable=False)      # e.g. "address_input_selector"
    fact_value = Column(Text, nullable=False)
    confidence_score = Column(Float, default=1.0)
    source_episode_id = Column(String(36), nullable=True)
    access_count = Column(Integer, default=0)
    last_validated = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_memory_semantic_user_confidence", "user_id", "confidence_score"),
    )


class MemoryProcedural(Base):
    """Stored skill programs — reusable step sequences (includes CAPTCHA skills)."""
    __tablename__ = "memory_procedural"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)   # NULL = universal skill
    skill_name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True)                # NULL = applies anywhere
    procedure = Column(Text, nullable=False)                   # JSON with summary + steps
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.7)
    last_used = Column(TIMESTAMP(timezone=True), nullable=True)
    last_success = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))


class MemoryReflection(Base):
    """Lessons distilled from failures and successes."""
    __tablename__ = "memory_reflection"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    lesson = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)   # BOT_DETECTION|SELECTOR|AUTH|CAPTCHA|NAVIGATION|OTHER
    severity = Column(String(20), nullable=False)   # LOW | MEDIUM | HIGH
    validated_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
