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
    async def _record_login_event(db: AsyncSession, username: str, success: bool, user_id: Optional[str] = None, failure_reason: Optional[str] = None) -> None:
        """Persist a login attempt (success or failure) for admin security monitoring."""
        from src.database.chat_db import LoginEvent
        try:
            db.add(LoginEvent(
                user_id=user_id,
                username_attempted=username,
                success=success,
                failure_reason=failure_reason,
            ))
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to record login event: {e}")
            await db.rollback()

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> dict:
        """Authenticate user and return JWT token."""
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not validator.verify_password(password, user.hashed_password):
            await ChatService._record_login_event(db, username, success=False, failure_reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if user.status == "suspended":
            await ChatService._record_login_event(db, username, success=False, user_id=user.user_id, failure_reason="suspended")
            raise HTTPException(
                status_code=403,
                detail="Your account has been suspended. Please contact an administrator.",
            )

        await ChatService._record_login_event(db, username, success=True, user_id=user.user_id)
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
    def _parse_token_usage(raw: Optional[str]) -> dict:
        """Best-effort parse of the JSON token_usage blob stored on AgentExecutionLog rows."""
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _pct_change(current: float, previous: float) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    # ── Admin: overview KPIs ─────────────────────────────────────────────
    @staticmethod
    async def admin_get_overview_metrics(db: AsyncSession, days: int = 30) -> dict:
        """KPI cards for the dashboard overview, computed entirely from real recorded data
        (users table, agent_execution_logs, schedule_runs) — no fabricated metrics."""
        from src.database.chat_db import AgentExecutionLog

        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)

        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        active_users = (
            await db.execute(select(func.count()).select_from(User).where(User.status == "active"))
        ).scalar() or 0

        running_agents = (
            await db.execute(
                select(func.count()).select_from(AgentExecutionLog).where(
                    AgentExecutionLog.status.in_(["PENDING", "IN_PROGRESS"])
                )
            )
        ).scalar() or 0

        completed_automations = (
            await db.execute(
                select(func.count()).select_from(ScheduleRun).where(
                    ScheduleRun.status == "COMPLETED", ScheduleRun.created_at >= current_start
                )
            )
        ).scalar() or 0

        async def _period_metrics(start, end):
            stmt = select(AgentExecutionLog).where(
                AgentExecutionLog.created_at >= start, AgentExecutionLog.created_at < end
            )
            logs = (await db.execute(stmt)).scalars().all()
            runs = len(logs)
            success = sum(1 for l in logs if (l.status or "").upper() in ("SUCCESS", "COMPLETED", "DONE"))
            tokens = 0
            cost = 0.0
            for l in logs:
                usage = ChatService._parse_token_usage(l.token_usage)
                tokens += int(usage.get("total") or usage.get("total_tokens") or 0)
                try:
                    cost += float(l.cost) if l.cost else 0.0
                except Exception:
                    pass
            rate = round((success / runs) * 100, 2) if runs else 0.0
            return runs, rate, tokens, round(cost, 4)

        cur_runs, cur_rate, cur_tokens, cur_cost = await _period_metrics(current_start, now)
        prev_runs, prev_rate, prev_tokens, prev_cost = await _period_metrics(previous_start, current_start)

        # Daily sparkline data (last 14 days) for runs and tokens
        sparkline_start = now - timedelta(days=14)
        recent_logs = (
            await db.execute(select(AgentExecutionLog).where(AgentExecutionLog.created_at >= sparkline_start))
        ).scalars().all()
        by_day: dict = {}
        for l in recent_logs:
            key = l.created_at.strftime("%Y-%m-%d") if l.created_at else "unknown"
            entry = by_day.setdefault(key, {"runs": 0, "tokens": 0})
            entry["runs"] += 1
            usage = ChatService._parse_token_usage(l.token_usage)
            entry["tokens"] += int(usage.get("total") or usage.get("total_tokens") or 0)
        days_sorted = sorted(by_day.keys())
        runs_sparkline = [by_day[d]["runs"] for d in days_sorted] or [0]
        tokens_sparkline = [by_day[d]["tokens"] for d in days_sorted] or [0]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "running_agents": running_agents,
            "completed_automations": completed_automations,
            "success_rate": cur_rate,
            "success_rate_change": ChatService._pct_change(cur_rate, prev_rate),
            "total_tokens": cur_tokens,
            "total_tokens_change": ChatService._pct_change(cur_tokens, prev_tokens),
            "total_cost": cur_cost,
            "total_cost_change": ChatService._pct_change(cur_cost, prev_cost),
            "total_runs": cur_runs,
            "total_runs_change": ChatService._pct_change(cur_runs, prev_runs),
            "runs_sparkline": runs_sparkline,
            "tokens_sparkline": tokens_sparkline,
        }

    # ── Admin: recent activity timeline ─────────────────────────────────
    @staticmethod
    async def admin_get_recent_activity(db: AsyncSession, limit: int = 20) -> dict:
        """Merge real signups, logins, automation runs, and agent run lifecycle events into one timeline."""
        from src.database.chat_db import AgentExecutionLog, LoginEvent

        items = []

        signups = (
            await db.execute(select(User).order_by(User.created_at.desc()).limit(limit))
        ).scalars().all()
        for u in signups:
            items.append({
                "type": "user_signup",
                "title": f"New user registered: {u.username}",
                "detail": u.email,
                "status": u.status,
                "timestamp": u.created_at,
            })

        logins = (
            await db.execute(select(LoginEvent).order_by(LoginEvent.created_at.desc()).limit(limit))
        ).scalars().all()
        for le in logins:
            items.append({
                "type": "login" if le.success else "login_failed",
                "title": (
                    f"{le.username_attempted} logged in" if le.success
                    else f"Failed login attempt for \"{le.username_attempted}\""
                ),
                "detail": le.failure_reason,
                "status": "SUCCESS" if le.success else "FAILED",
                "timestamp": le.created_at,
            })

        runs = (
            await db.execute(
                select(ScheduleRun, Schedule)
                .join(Schedule, Schedule.schedule_id == ScheduleRun.schedule_id)
                .order_by(ScheduleRun.created_at.desc())
                .limit(limit)
            )
        ).all()
        for run, schedule in runs:
            items.append({
                "type": "automation_run",
                "title": f"Automation \"{schedule.title or schedule.schedule_id[:8]}\" {run.status.lower()}",
                "detail": run.error_log[:200] if run.error_log else None,
                "status": run.status,
                "timestamp": run.created_at,
            })

        agent_logs = (
            await db.execute(
                select(AgentExecutionLog)
                .order_by(AgentExecutionLog.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        for log in agent_logs:
            status_upper = (log.status or "").upper()
            if status_upper in ("FAILED", "ERROR"):
                items.append({
                    "type": "agent_failure",
                    "title": f"Agent stage \"{log.stage_name}\" failed",
                    "detail": (log.error_message or "")[:200] or None,
                    "status": log.status,
                    "timestamp": log.created_at,
                })
            elif status_upper in ("PENDING", "IN_PROGRESS"):
                items.append({
                    "type": "agent_run_started",
                    "title": f"Agent stage \"{log.stage_name}\" started",
                    "detail": f"chat {log.chat_id[:12]}",
                    "status": log.status,
                    "timestamp": log.created_at,
                })
            elif status_upper in ("COMPLETED", "SUCCESS", "DONE"):
                items.append({
                    "type": "agent_run_completed",
                    "title": f"Agent stage \"{log.stage_name}\" completed",
                    "detail": f"chat {log.chat_id[:12]}",
                    "status": log.status,
                    "timestamp": log.updated_at or log.created_at,
                })

        items.sort(key=lambda i: i["timestamp"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return {"items": items[:limit]}

    # ── Admin: agent monitoring ──────────────────────────────────────────
    @staticmethod
    async def admin_list_agent_runs(
        db: AsyncSession, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None,
        search: Optional[str] = None, sort_by: str = "created_at", sort_dir: str = "desc",
    ) -> dict:
        from src.database.chat_db import AgentExecutionLog
        from sqlalchemy import or_

        base_stmt = select(AgentExecutionLog)
        if status_filter:
            base_stmt = base_stmt.where(AgentExecutionLog.status == status_filter.upper())
        if search:
            like = f"%{search}%"
            base_stmt = base_stmt.where(
                or_(AgentExecutionLog.chat_id.ilike(like), AgentExecutionLog.stage_name.ilike(like), AgentExecutionLog.user_id.ilike(like))
            )

        total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar() or 0

        sort_column_map = {
            "created_at": AgentExecutionLog.created_at,
            "status": AgentExecutionLog.status,
            "stage_name": AgentExecutionLog.stage_name,
        }
        sort_column = sort_column_map.get(sort_by, AgentExecutionLog.created_at)
        order_clause = sort_column.asc() if sort_dir == "asc" else sort_column.desc()

        stmt = base_stmt.order_by(order_clause).offset((page - 1) * page_size).limit(page_size)
        logs = (await db.execute(stmt)).scalars().all()

        all_logs = (await db.execute(select(AgentExecutionLog))).scalars().all()
        running_count = sum(1 for l in all_logs if l.status == "IN_PROGRESS")
        queued_count = sum(1 for l in all_logs if l.status == "PENDING")
        failed_count = sum(1 for l in all_logs if l.status in ("FAILED", "ERROR"))
        completed_count = sum(1 for l in all_logs if l.status in ("COMPLETED", "SUCCESS", "DONE"))

        runtimes = []
        for l in all_logs:
            if l.status in ("COMPLETED", "SUCCESS", "DONE") and l.created_at and l.updated_at:
                delta = (l.updated_at - l.created_at).total_seconds()
                if delta >= 0:
                    runtimes.append(delta)
        avg_runtime = round(sum(runtimes) / len(runtimes), 2) if runtimes else 0.0

        runs = []
        for l in logs:
            usage = ChatService._parse_token_usage(l.token_usage)
            tokens = int(usage.get("total") or usage.get("total_tokens") or 0)
            try:
                cost = float(l.cost) if l.cost else 0.0
            except Exception:
                cost = 0.0
            runs.append({
                "id": l.id,
                "chat_id": l.chat_id,
                "user_id": l.user_id,
                "stage_name": l.stage_name,
                "status": l.status,
                "tokens": tokens,
                "cost": cost,
                "error_message": l.error_message,
                "created_at": l.created_at,
            })

        return {
            "runs": runs,
            "total": total,
            "running_count": running_count,
            "queued_count": queued_count,
            "failed_count": failed_count,
            "completed_count": completed_count,
            "avg_runtime_seconds": avg_runtime,
        }

    # ── Admin: agent run drill-in timeline ───────────────────────────────
    @staticmethod
    async def admin_get_agent_run_timeline(db: AsyncSession, chat_id: str) -> dict:
        """All execution stages recorded for a given chat_id, ordered chronologically, so an
        admin can drill into a single run and see its full step-by-step timeline."""
        from src.database.chat_db import AgentExecutionLog

        logs = (
            await db.execute(
                select(AgentExecutionLog)
                .where(AgentExecutionLog.chat_id == chat_id)
                .order_by(AgentExecutionLog.created_at.asc())
            )
        ).scalars().all()
        if not logs:
            raise HTTPException(status_code=404, detail="No agent run found for that chat_id")

        stages = []
        for l in logs:
            usage = ChatService._parse_token_usage(l.token_usage)
            try:
                cost = float(l.cost) if l.cost else 0.0
            except Exception:
                cost = 0.0
            stages.append({
                "id": l.id,
                "agent_stage": l.agent_stage,
                "stage_name": l.stage_name,
                "status": l.status,
                "tokens": int(usage.get("total") or usage.get("total_tokens") or 0),
                "cost": cost,
                "error_message": l.error_message,
                "created_at": l.created_at,
                "updated_at": l.updated_at,
            })

        return {"chat_id": chat_id, "stages": stages}

    # ── Admin: cancel an in-progress agent run ───────────────────────────
    @staticmethod
    async def admin_cancel_agent_run(db: AsyncSession, chat_id: str) -> dict:
        """Cancel a running/queued agent execution for the given chat_id by delegating to the
        brain's real stop_process (the same mechanism used when a user stops their own chat)."""
        from src.database.chat_db import AgentExecutionLog
        from src.services.brain import brain

        logs = (
            await db.execute(
                select(AgentExecutionLog)
                .where(AgentExecutionLog.chat_id == chat_id, AgentExecutionLog.status.in_(["PENDING", "IN_PROGRESS"]))
            )
        ).scalars().all()
        if not logs:
            raise HTTPException(status_code=404, detail="No in-progress or queued run found for that chat_id")

        user_id = logs[0].user_id
        try:
            await brain.stop_process(chat_id, user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to cancel run: {e}")

        now = datetime.now(timezone.utc)
        for l in logs:
            l.status = "CANCELLED"
            l.updated_at = now
        await db.commit()

        return {"chat_id": chat_id, "action": "cancel", "success": True, "detail": f"Cancelled {len(logs)} stage(s)"}

    # ── Admin: automation monitoring ─────────────────────────────────────
    @staticmethod
    async def admin_list_automations(
        db: AsyncSession, page: int = 1, page_size: int = 20, search: Optional[str] = None,
        sort_by: str = "created_at", sort_dir: str = "desc",
    ) -> dict:
        base_stmt = select(Schedule)
        if search:
            like = f"%{search}%"
            base_stmt = base_stmt.where(Schedule.title.ilike(like))

        total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar() or 0

        sort_column_map = {
            "created_at": Schedule.created_at,
            "status": Schedule.status,
            "title": Schedule.title,
            "next_run": Schedule.next_run,
            "last_run": Schedule.last_run,
        }
        sort_column = sort_column_map.get(sort_by, Schedule.created_at)
        order_clause = sort_column.asc() if sort_dir == "asc" else sort_column.desc()

        stmt = base_stmt.order_by(order_clause).offset((page - 1) * page_size).limit(page_size)
        schedules = (await db.execute(stmt)).scalars().all()

        schedule_ids = [s.schedule_id for s in schedules]
        runs = []
        if schedule_ids:
            runs = (
                await db.execute(select(ScheduleRun).where(ScheduleRun.schedule_id.in_(schedule_ids)))
            ).scalars().all()

        runs_by_schedule: dict = {}
        for r in runs:
            runs_by_schedule.setdefault(r.schedule_id, []).append(r)

        automations = []
        for s in schedules:
            s_runs = runs_by_schedule.get(s.schedule_id, [])
            total_runs = len(s_runs)
            success_runs = sum(1 for r in s_runs if r.status == "COMPLETED")
            failed_runs = sum(1 for r in s_runs if r.status == "FAILED")
            success_rate = round((success_runs / total_runs) * 100, 2) if total_runs else 0.0
            automations.append({
                "schedule_id": s.schedule_id,
                "title": s.title,
                "status": s.status,
                "schedule_type": s.schedule_type,
                "last_run": s.last_run,
                "next_run": s.next_run,
                "total_runs": total_runs,
                "success_runs": success_runs,
                "failed_runs": failed_runs,
                "success_rate": success_rate,
            })

        return {"automations": automations, "total": total}

    # ── Admin: usage dashboard ────────────────────────────────────────────
    @staticmethod
    async def admin_get_usage_breakdown(db: AsyncSession, days: int = 30) -> dict:
        from src.database.chat_db import AgentExecutionLog

        since = datetime.now(timezone.utc) - timedelta(days=days)
        logs = (
            await db.execute(select(AgentExecutionLog).where(AgentExecutionLog.created_at >= since))
        ).scalars().all()

        total_prompt = 0
        total_completion = 0
        daily: dict = {}
        by_user: dict = {}

        for l in logs:
            usage = ChatService._parse_token_usage(l.token_usage)
            prompt = int(usage.get("input") or 0)
            completion = int(usage.get("output") or 0)
            total_prompt += prompt
            total_completion += completion

            day_key = l.created_at.strftime("%Y-%m-%d") if l.created_at else "unknown"
            entry = daily.setdefault(day_key, {"date": day_key, "prompt_tokens": 0, "completion_tokens": 0})
            entry["prompt_tokens"] += prompt
            entry["completion_tokens"] += completion

            try:
                cost = float(l.cost) if l.cost else 0.0
            except Exception:
                cost = 0.0
            u_entry = by_user.setdefault(l.user_id, {"user_id": l.user_id, "tokens": 0, "cost": 0.0, "runs": 0})
            u_entry["tokens"] += prompt + completion
            u_entry["cost"] += cost
            u_entry["runs"] += 1

        user_ids = list(by_user.keys())
        if user_ids:
            users = (await db.execute(select(User).where(User.user_id.in_(user_ids)))).scalars().all()
            username_map = {u.user_id: u.username for u in users}
            for uid, entry in by_user.items():
                entry["username"] = username_map.get(uid, uid[:8])
                entry["cost"] = round(entry["cost"], 4)

        daily_usage = sorted(daily.values(), key=lambda d: d["date"])
        top_users = sorted(by_user.values(), key=lambda u: u["tokens"], reverse=True)[:10]

        return {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "daily_usage": daily_usage,
            "top_users": top_users,
        }

    # ── Admin: security overview ──────────────────────────────────────────
    @staticmethod
    async def admin_get_security_overview(db: AsyncSession) -> dict:
        from src.database.chat_db import LoginEvent

        suspended = (
            await db.execute(select(User).where(User.status == "suspended").order_by(User.updated_at.desc()))
        ).scalars().all()
        recent = (
            await db.execute(select(User).order_by(User.created_at.desc()).limit(10))
        ).scalars().all()
        recent_logins = (
            await db.execute(
                select(LoginEvent).where(LoginEvent.success == True).order_by(LoginEvent.created_at.desc()).limit(20)
            )
        ).scalars().all()
        failed_logins = (
            await db.execute(
                select(LoginEvent).where(LoginEvent.success == False).order_by(LoginEvent.created_at.desc()).limit(20)
            )
        ).scalars().all()

        return {
            "suspended_users": [
                {"user_id": u.user_id, "username": u.username, "email": u.email, "updated_at": u.updated_at.isoformat() if u.updated_at else None}
                for u in suspended
            ],
            "recent_signups": [
                {"user_id": u.user_id, "username": u.username, "email": u.email, "created_at": u.created_at.isoformat() if u.created_at else None, "role": u.role, "status": u.status}
                for u in recent
            ],
            "recent_logins": [
                {"user_id": le.user_id, "username": le.username_attempted, "created_at": le.created_at.isoformat() if le.created_at else None}
                for le in recent_logins
            ],
            "failed_logins": [
                {"username": le.username_attempted, "reason": le.failure_reason, "created_at": le.created_at.isoformat() if le.created_at else None}
                for le in failed_logins
            ],
        }

    # ── Admin: unified analytics ──────────────────────────────────────────
    @staticmethod
    async def admin_get_analytics(db: AsyncSession, days: int = 30) -> dict:
        """Runs-over-time, success/error rate, token consumption, and browser-session volume,
        all computed from real AgentExecutionLog rows over the requested date range."""
        from src.database.chat_db import AgentExecutionLog

        since = datetime.now(timezone.utc) - timedelta(days=days)
        logs = (
            await db.execute(select(AgentExecutionLog).where(AgentExecutionLog.created_at >= since))
        ).scalars().all()

        daily_runs_map: dict = {}
        daily_tokens_map: dict = {}
        daily_sessions_map: dict = {}
        total_success = 0
        total_failed = 0

        for l in logs:
            day_key = l.created_at.strftime("%Y-%m-%d") if l.created_at else "unknown"
            status_upper = (l.status or "").upper()
            is_success = status_upper in ("COMPLETED", "SUCCESS", "DONE")
            is_failed = status_upper in ("FAILED", "ERROR")
            if is_success:
                total_success += 1
            if is_failed:
                total_failed += 1

            run_entry = daily_runs_map.setdefault(day_key, {"date": day_key, "total": 0, "success": 0, "failed": 0})
            run_entry["total"] += 1
            if is_success:
                run_entry["success"] += 1
            if is_failed:
                run_entry["failed"] += 1

            usage = ChatService._parse_token_usage(l.token_usage)
            tokens = int(usage.get("total") or usage.get("total_tokens") or 0)
            token_entry = daily_tokens_map.setdefault(day_key, {"date": day_key, "tokens": 0})
            token_entry["tokens"] += tokens

            session_entry = daily_sessions_map.setdefault(day_key, {"date": day_key, "chat_ids": set()})
            session_entry["chat_ids"].add(l.chat_id)

        daily_runs = sorted(daily_runs_map.values(), key=lambda d: d["date"])
        daily_tokens = sorted(daily_tokens_map.values(), key=lambda d: d["date"])
        daily_sessions = sorted(
            [{"date": d["date"], "sessions": len(d["chat_ids"])} for d in daily_sessions_map.values()],
            key=lambda d: d["date"],
        )

        total_runs = len(logs)
        overall_success_rate = round((total_success / total_runs) * 100, 2) if total_runs else 0.0

        return {
            "days": days,
            "daily_runs": daily_runs,
            "daily_tokens": daily_tokens,
            "daily_sessions": daily_sessions,
            "total_runs": total_runs,
            "total_success": total_success,
            "total_failed": total_failed,
            "overall_success_rate": overall_success_rate,
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