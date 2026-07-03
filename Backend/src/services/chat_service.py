import uuid
import jwt
import os
import json
from typing import Optional, List, Union
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Local Imports
from src.database.chat_db import ScheduleRun, User, Message, ChatSession, Schedule, get_db
from src.utils import validator
from src.utils.logger import logger
from src.config import JWT_SECRET_KEY as SECRET_KEY, JWT_ALGORITHM as ALGORITHM

security = HTTPBearer()

# JWT session tokens issued by ChatService use a longer expiry than the
# short-lived tokens in validator.py. Secret/algorithm are centralized in
# src/config.py so both stay in sync.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

class ChatService:
    @staticmethod
    async def create_user(db: AsyncSession, username: str, email: str, password: str) -> User:
        """Create a new user with hashed password."""
        stmt = select(User).where((User.username == username) | (User.email == email))
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username or email already registered")

        # Task #127: the very first account on a fresh deployment is made an
        # admin so there's always a way into the Admin Dashboard without a
        # server restart or manual DB edit. (init_db's startup bootstrap
        # covers the case of pre-existing users from before this migration.)
        admin_count_result = await db.execute(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        is_first_admin = admin_count_result.scalar_one() == 0

        hashed_pw = validator.hash_password(password)
        new_user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            email=email,
            hashed_password=hashed_pw,
            role="admin" if is_first_admin else "user",
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> dict:
        """Authenticate user and return JWT token."""
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not validator.verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if user.status == "suspended":
            raise HTTPException(
                status_code=403,
                detail="Your account has been suspended. Please contact an administrator.",
            )

        access_token = ChatService.create_access_token(data={"sub": user.user_id})
        return {"access_token": access_token, "token_type": "bearer"}

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Generate a JWT token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    async def get_current_user(
        credentials: Union[HTTPAuthorizationCredentials, str] = Security(security),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """Dependency to get the authenticated user from the JWT token. Supports both HTTP and WebSocket tokens."""
        try:
            # Handle both FastAPI Security object and raw string (for WebSockets)
            token = credentials.credentials if hasattr(credentials, 'credentials') else credentials
            
            # Use the local SECRET_KEY and ALGORITHM
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            stmt = select(User).where(User.user_id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            if user.status == "suspended":
                raise HTTPException(
                    status_code=403,
                    detail="Your account has been suspended. Please contact an administrator.",
                )
            return user
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Auth validation error: {e}")
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    @staticmethod
    async def get_current_admin_user(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """Dependency that additionally requires the authenticated user to hold the 'admin' role."""
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
        return current_user

    # ── Admin: user management ──────────────────────────────────────────
    @staticmethod
    async def admin_list_users(
        db: AsyncSession, page: int = 1, page_size: int = 20, search: Optional[str] = None
    ) -> dict:
        """List users with pagination and optional username/email search."""
        from sqlalchemy import func, or_

        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        if search:
            like = f"%{search}%"
            filter_clause = or_(User.username.ilike(like), User.email.ilike(like))
            stmt = stmt.where(filter_clause)
            count_stmt = count_stmt.where(filter_clause)

        total = (await db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        users = result.scalars().all()
        return {"users": users, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    async def admin_get_user(db: AsyncSession, user_id: str) -> User:
        stmt = select(User).where(User.user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    async def admin_update_user(
        db: AsyncSession,
        user_id: str,
        acting_admin: User,
        role: Optional[str] = None,
        status_value: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> User:
        """Update a user's role/status/profile fields. Prevents an admin from locking themselves out."""
        user = await ChatService.admin_get_user(db, user_id)

        if user.user_id == acting_admin.user_id:
            if role is not None and role != "admin":
                raise HTTPException(status_code=400, detail="You cannot remove your own admin role")
            if status_value is not None and status_value != "active":
                raise HTTPException(status_code=400, detail="You cannot suspend your own account")

        if username is not None:
            dup_stmt = select(User).where(User.username == username, User.user_id != user_id)
            if (await db.execute(dup_stmt)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username already in use")
            user.username = username
        if email is not None:
            dup_stmt = select(User).where(User.email == email, User.user_id != user_id)
            if (await db.execute(dup_stmt)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already in use")
            user.email = email
        if role is not None:
            user.role = role
        if status_value is not None:
            user.status = status_value

        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def admin_delete_user(db: AsyncSession, user_id: str, acting_admin: User) -> dict:
        if user_id == acting_admin.user_id:
            raise HTTPException(status_code=400, detail="You cannot delete your own account")
        user = await ChatService.admin_get_user(db, user_id)
        # Use an ORM-level delete (not a raw Core `delete(User)` statement) so the
        # `cascade="all, delete-orphan"` relationships declared on User (messages,
        # chat_sessions, chat_logs) actually fire. A raw DELETE bypasses the ORM
        # unit-of-work and can either orphan rows or fail on FK constraints for
        # users who already have chat history.
        await db.delete(user)
        await db.commit()
        return {"status": "success"}

    # ── Admin: operations metrics ───────────────────────────────────────
    @staticmethod
    async def admin_get_operations_metrics(db: AsyncSession, days: int = 30) -> dict:
        """Aggregate real AgentExecutionLog data into token/cost/success-failure metrics."""
        from src.database.chat_db import AgentExecutionLog
        from sqlalchemy import func

        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(AgentExecutionLog).where(AgentExecutionLog.created_at >= since)
        result = await db.execute(stmt)
        logs = result.scalars().all()

        total_runs = len(logs)
        success_count = 0
        failure_count = 0
        total_tokens = 0
        total_cost = 0.0
        daily: dict = {}
        error_counts: dict = {}
        status_counts: dict = {}

        for log in logs:
            status_norm = (log.status or "UNKNOWN").upper()
            status_counts[status_norm] = status_counts.get(status_norm, 0) + 1
            if status_norm in ("SUCCESS", "COMPLETED", "DONE"):
                success_count += 1
            elif status_norm in ("FAILED", "ERROR", "FAILURE"):
                failure_count += 1

            tokens = 0
            if log.token_usage:
                try:
                    parsed = json.loads(log.token_usage)
                    if isinstance(parsed, dict):
                        tokens = int(parsed.get("total_tokens") or parsed.get("total") or 0)
                    elif isinstance(parsed, (int, float)):
                        tokens = int(parsed)
                except Exception:
                    pass
            total_tokens += tokens

            cost = 0.0
            if log.cost:
                try:
                    cost = float(log.cost)
                except Exception:
                    pass
            total_cost += cost

            day_key = log.created_at.strftime("%Y-%m-%d") if log.created_at else "unknown"
            day_entry = daily.setdefault(day_key, {"date": day_key, "runs": 0, "success": 0, "failure": 0, "tokens": 0, "cost": 0.0})
            day_entry["runs"] += 1
            day_entry["tokens"] += tokens
            day_entry["cost"] += cost
            if status_norm in ("SUCCESS", "COMPLETED", "DONE"):
                day_entry["success"] += 1
            elif status_norm in ("FAILED", "ERROR", "FAILURE"):
                day_entry["failure"] += 1

            if log.error_message:
                key = log.error_message.strip()[:200]
                error_counts[key] = error_counts.get(key, 0) + 1

        daily_trends = sorted(daily.values(), key=lambda d: d["date"])
        top_errors = sorted(
            [{"error": k, "count": v} for k, v in error_counts.items()],
            key=lambda e: e["count"], reverse=True,
        )[:10]
        status_breakdown = [{"status": k, "count": v} for k, v in status_counts.items()]

        success_rate = round((success_count / total_runs) * 100, 2) if total_runs else 0.0

        return {
            "total_runs": total_runs,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "daily_trends": daily_trends,
            "top_errors": top_errors,
            "status_breakdown": status_breakdown,
        }

    @staticmethod
    async def get_user_sessions(db: AsyncSession, user_id: str) -> List[ChatSession]:
        """Get all chat sessions for a user."""
        stmt = select(ChatSession).where(ChatSession.user_id == str(user_id)).order_by(ChatSession.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_chat_history(db: AsyncSession, chat_id: str, user_id: str) -> dict:
        """Retrieve all messages for a specific chat session."""
        # Verify session ownership first
        session = await ChatService.get_session_by_id(db, chat_id, user_id)
        if not session:
            return {"messages": []}

        # FIX: Order by created_at (Message table) and filter by chat_id
        stmt = select(Message).where(Message.chat_id == str(chat_id)).order_by(Message.created_at.asc())
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        return {
            "messages": [
                {
                    "id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "plan": json.loads(msg.plan_data) if msg.plan_data else [],
                    "form": json.loads(msg.form_data) if msg.form_data else None,
                    "token_usage": json.loads(msg.token_usage) if msg.token_usage else None,
                    "cost": msg.cost,
                    "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else [],
                    "timestamp": msg.created_at.isoformat() if msg.created_at else datetime.now(timezone.utc).isoformat()
                }
                for msg in messages
            ]
        }

    @staticmethod
    async def rename_session(db: AsyncSession, chat_id: str, title: str, user_id: str) -> ChatSession:
        """Update the title of a chat session."""
        # FIX: Changed ChatSession.chat_id to ChatSession.id
        stmt = select(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session.title = title
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def delete_session(db: AsyncSession, chat_id: str, user_id: str) -> dict:
        """Delete a chat session and its associated messages."""
        # 1. Delete messages first
        await db.execute(delete(Message).where(Message.chat_id == chat_id))
        
        # 2. Delete logs
        from src.database.chat_db import AgentExecutionLog, ToolExecutionLog
        await db.execute(delete(AgentExecutionLog).where(AgentExecutionLog.chat_id == chat_id))
        await db.execute(delete(ToolExecutionLog).where(ToolExecutionLog.chat_id == chat_id))
        
        # 3. Delete session
        stmt = delete(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user_id)
        await db.execute(stmt)
        
        await db.commit()
        return {"status": "success"}

    @staticmethod
    async def get_session_by_id(db: AsyncSession, chat_id: str, user_id: str):
        """Strictly fetch a session only if it belongs to the requesting user."""
        # FIX: Changed session_id to id
        stmt = select(ChatSession).where(
            ChatSession.id == str(chat_id),
            ChatSession.user_id == str(user_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_session(db: AsyncSession, user_id: str, title: str = "New Chat"):
        # FIX: Explicitly generate a secure UUIDv4 string prefixed with 'thread-'
        session_id = f"thread-{uuid.uuid4()}"
        
        new_session = ChatSession(
            id=session_id,
            user_id=str(user_id),
            title=title,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    @staticmethod
    async def create_schedule(db: AsyncSession, user_id: str, req: any) -> Schedule:
        """Create a new automation schedule for a user."""
        # Fetch the selected AI message to extract plan and response
        stmt = select(Message).where(Message.message_id.in_(req.selected_message_ids), Message.role == "ai")
        res = await db.execute(stmt)
        ai_msg = res.scalars().first()
        
        # Fetch the selected user message to extract prompt
        stmt = select(Message).where(Message.message_id.in_(req.selected_message_ids), Message.role == "user")
        res = await db.execute(stmt)
        user_msg = res.scalars().first()

        new_schedule = Schedule(
            schedule_id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=req.chat_id,
            title=req.title,
            selected_data=json.dumps({
                "messages": req.selected_message_ids,
                "tools": req.selected_tool_ids
            }),
            user_prompt=user_msg.content if user_msg else None,
            assistant_response=ai_msg.content if ai_msg else None,
            plan_data=ai_msg.plan_data if ai_msg else None,
            schedule_type=req.schedule_type,
            schedule_time=req.schedule_time or "09:00",
            schedule_day_of_week=getattr(req, "schedule_day_of_week", None) or "mon",
            timezone=req.timezone or "America/New_York",
            headless=(req.advanced_options.headless if req.advanced_options else True),
            email_recipient=req.email_recipient,
            status=getattr(req, "status", None) or "active",
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_schedule)
        await db.commit()
        await db.refresh(new_schedule)
        return new_schedule

    @staticmethod
    async def get_schedule_runs(db: AsyncSession, schedule_id: str) -> List[ScheduleRun]:
        """Get execution history for a specific schedule."""
        from src.database.chat_db import ScheduleRun
        stmt = select(ScheduleRun).where(ScheduleRun.schedule_id == schedule_id).order_by(ScheduleRun.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_user_schedules(db: AsyncSession, user_id: str) -> List[Schedule]:
        """Get all schedules for a specific user."""
        stmt = select(Schedule).where(Schedule.user_id == user_id).order_by(Schedule.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()