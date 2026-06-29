from typing import List
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    TIMESTAMP, BigInteger, Column, ForeignKey, Integer, String, Text, DateTime
)

from sqlalchemy.orm import Mapped, declarative_base, relationship, sessionmaker
from enum import Enum as PyEnum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

load_dotenv()

DATABASE_USER = os.getenv("DATABASE_USER", "root")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "root")
DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")
DATABASE_NAME = os.getenv("DATABASE_NAME", "sciparser_v1")

SERVER_URL = f"mysql+aiomysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}"
DATABASE_URL = f"{SERVER_URL}/{DATABASE_NAME}"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": None
    }
)

AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
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
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_logs: Mapped[List["ChatLog"]] = relationship("ChatLog", back_populates="user", cascade="all, delete-orphan")

class ChatLog(Base):
    __tablename__ = "chat_logs"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc), index=True)
    
    user: Mapped["User"] = relationship("User", back_populates="chat_logs")

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    # FIX: Standardized length to String(100) for UUID compatibility
    chat_id = Column(String(100), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False) # Changed to Text for long messages
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    plan_data = Column(Text) # Added to store the final agent plan
    tool_calls = Column(Text) # Added to store tool execution summary
    form_data = Column(Text) # Added to store dynamic forms for NEEDS_INPUT status
    token_usage = Column(Text) # JSON: {"input": int, "output": int, "total": int}
    cost = Column(Text) # String or Float for cost tracking
    
    user: Mapped["User"] = relationship("User", back_populates="messages")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    # FIX: Ensure ID is a String (UUIDv4) primary key, not an Integer
    id = Column(String(100), primary_key=True, default=lambda: f"thread-{uuid.uuid4()}")
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(20), default="active")  # Added status column
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # FIX: Added state_data column to store agent workflow state (no default for TEXT in MySQL)
    state_data = Column(Text)
    
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")

class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    schedule_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(100), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True)
    
    title = Column(String(255), nullable=True)
    selected_data = Column(Text) # JSON storing list of message_ids and tool_log_ids
    user_prompt = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    plan_data = Column(Text, nullable=True) # Added to store the rehydrated AI plan
    playwright_steps = Column(Text, nullable=True)
    extracted_content = Column(Text, nullable=True)
    generated_script = Column(Text, nullable=True)
    
    status = Column(String(20), default="completed")
    schedule_type = Column(String(20), default="manual")
    schedule_time = Column(String(50), nullable=True)
    cron_expression = Column(String(50), nullable=True)
    email_recipient = Column(String(255), nullable=True)
    
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ScheduleRun(Base):
    """Tracks each execution of a schedule."""
    __tablename__ = "schedule_runs"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    schedule_id = Column(String(36), ForeignKey("schedules.schedule_id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String(20), default="running") # running, completed, failed
    engine = Column(String(50), nullable=True) # playwright, browser-use
    attempt = Column(Integer, default=1)
    output = Column(Text(4294967295)) # The extracted data or error message
    error_log = Column(Text)
    duration_seconds = Column(Integer)
    
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(TIMESTAMP, nullable=True)
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
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    agent_stage = Column(String(20), nullable=False)
    stage_name = Column(String(100), nullable=False)
    input_data = Column(Text)
    output_data = Column(Text)
    status = Column(String(20), default="PENDING")
    error_message = Column(Text)
    token_usage = Column(Text) # JSON: {"input": int, "output": int, "total": int}
    cost = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ToolExecutionLog(Base):
    """Tracks tool executions by Agent 3."""
    __tablename__ = "tool_execution_logs"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(String(20), nullable=False)
    tool_name = Column(String(50), nullable=False)
    tool_input = Column(Text)
    tool_output = Column(Text(4294967295)) # Use LONGTEXT for large tool outputs
    status = Column(String(20), default="PENDING")
    error_message = Column(Text)
    screenshot_url = Column(String(500))
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))