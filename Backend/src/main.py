import os
import re
import sys
import uuid
import json
import asyncio
import smtplib
import tempfile
import subprocess
import traceback
import httpx as _httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

# Local Imports
from src.database.chat_db import AsyncSessionLocal, User, Message, get_db
from src.database.init_db import init_database
from src.schemas.schema import (
    SignUp, SignIn, Token, UserResponse, ChatRequest, 
    ChatResponse, RenameChatRequest, ScheduleRequest, ScheduleResponse
)
from src.utils.logger import logger
from src.services.brain import brain
from src.services.chat_service import ChatService

# --- WebSocket Plan Manager ---
class PlanStreamManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.browser_connections: Dict[str, List[WebSocket]] = {}
        self.schedule_connections: Dict[str, List[WebSocket]] = {}
        self.last_frame: Dict[str, Any] = {}  # last browser frame per user_id

    async def connect(self, chat_id: str, websocket: WebSocket, is_browser: bool = False, is_schedule: bool = False):
        if is_schedule:
            if chat_id not in self.schedule_connections:
                self.schedule_connections[chat_id] = []
            self.schedule_connections[chat_id].append(websocket)
        elif is_browser:
            if chat_id not in self.browser_connections:
                self.browser_connections[chat_id] = []
            self.browser_connections[chat_id].append(websocket)
        else:
            if chat_id not in self.active_connections:
                self.active_connections[chat_id] = []
            self.active_connections[chat_id].append(websocket)

    def disconnect(self, chat_id: str, websocket: WebSocket, is_browser: bool = False, is_schedule: bool = False):
        if is_schedule:
            if chat_id in self.schedule_connections:
                if websocket in self.schedule_connections[chat_id]:
                    self.schedule_connections[chat_id].remove(websocket)
        elif is_browser:
            if chat_id in self.browser_connections:
                if websocket in self.browser_connections[chat_id]:
                    self.browser_connections[chat_id].remove(websocket)
        else:
            if chat_id in self.active_connections:
                if websocket in self.active_connections[chat_id]:
                    self.active_connections[chat_id].remove(websocket)

    async def broadcast_schedule_update(self, schedule_id: str, data: Any):
        """Broadcasts live logs, pipeline steps, or screenshots for a running schedule."""
        if schedule_id in self.schedule_connections:
            for connection in self.schedule_connections[schedule_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

    async def broadcast_notification(self, chat_id: str, notification_type: str, message: str):
        """Broadcasts a one-time informational notification to the UI."""
        if chat_id in self.active_connections:
            for connection in self.active_connections[chat_id]:
                try:
                    await connection.send_json({
                        "type": "notification",
                        "notification_type": notification_type,
                        "message": message,
                    })
                except Exception:
                    pass

    async def broadcast_plan(self, chat_id: str, plan_data: Any):
        if chat_id in self.active_connections:
            for connection in self.active_connections[chat_id]:
                try:
                    await connection.send_json({"type": "plan_update", "data": plan_data})
                except Exception:
                    pass

    async def broadcast_thought(self, chat_id: str, thought: str):
        """Broadcasts a live reasoning/thought to the UI."""
        if chat_id in self.active_connections:
            for connection in self.active_connections[chat_id]:
                try:
                    await connection.send_json({"type": "thought_update", "data": thought})
                except Exception:
                    pass

    async def broadcast_mouse(self, mouse_data: Any, user_id: str):
        """Broadcasts a mouse-position event to browser stream clients for a user."""
        if user_id in self.browser_connections:
            dead: list = []
            for connection in list(self.browser_connections[user_id]):
                try:
                    await connection.send_json({"event": "mouse", "data": mouse_data})
                except Exception:
                    dead.append(connection)
            for conn in dead:
                self.disconnect(user_id, conn, is_browser=True)

    async def broadcast_frame(self, frame_data: Any, user_id: str, is_tool: bool = False):
        """Broadcasts a base64 CDP frame or tool log to all connected browser stream clients for a user."""
        if not is_tool:
            self.last_frame[user_id] = frame_data
        conns = self.browser_connections.get(user_id, [])
        if not is_tool:
            logger.info(f"broadcast_frame: user={user_id[:8]} connections={len(conns)} frame_len={len(str(frame_data.get('frame','') if isinstance(frame_data, dict) else frame_data))}")
        if user_id in self.browser_connections:
            event_type = "tool_log" if is_tool else "frame"
            dead: list = []
            for connection in list(self.browser_connections[user_id]):
                try:
                    await connection.send_json({"event": event_type, "data": frame_data})
                except Exception as exc:
                    logger.warning(f"broadcast_frame: send FAILED for user={user_id[:8]}: {exc}")
                    dead.append(connection)
            for conn in dead:
                self.disconnect(user_id, conn, is_browser=True)

plan_stream_manager = PlanStreamManager()
# Inject manager into brain and its session_manager so they can broadcast
brain.stream_manager = plan_stream_manager
brain.session_manager.stream_manager = plan_stream_manager

# ── APScheduler (global) ───────────────────────────────────────────────────
_scheduler = AsyncIOScheduler(timezone="UTC")


def _calculate_next_run(schedule_type: str, schedule_time: Optional[str]) -> Optional[datetime]:
    """Return the next UTC datetime for a given schedule_type + HH:MM time string."""
    hour, minute = 9, 0
    if schedule_time:
        try:
            parts = schedule_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule_type == "daily":
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    elif schedule_type == "weekly":
        days_ahead = 0 - candidate.weekday()  # next Monday
        if days_ahead <= 0:
            days_ahead += 7
        candidate += timedelta(days=days_ahead)
        return candidate
    elif schedule_type == "monthly":
        if candidate.day != 1 or candidate <= now:
            # First of next month
            if now.month == 12:
                candidate = candidate.replace(year=now.year + 1, month=1, day=1)
            else:
                candidate = candidate.replace(month=now.month + 1, day=1)
        return candidate
    return None


def _build_cron_trigger(schedule_type: str, schedule_time: Optional[str]) -> Optional[CronTrigger]:
    """Build an APScheduler CronTrigger from schedule_type and HH:MM time."""
    hour, minute = 9, 0
    if schedule_time:
        try:
            parts = schedule_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            pass

    if schedule_type == "daily":
        return CronTrigger(hour=hour, minute=minute, timezone="UTC")
    elif schedule_type == "weekly":
        return CronTrigger(day_of_week="mon", hour=hour, minute=minute, timezone="UTC")
    elif schedule_type == "monthly":
        return CronTrigger(day=1, hour=hour, minute=minute, timezone="UTC")
    return None


def _register_schedule_job(schedule_id: str, schedule_type: str, schedule_time: Optional[str]) -> None:
    """Register (or replace) an APScheduler cron job for a schedule."""
    trigger = _build_cron_trigger(schedule_type, schedule_time)
    if trigger is None:
        return
    job_id = f"sched_{schedule_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    _scheduler.add_job(
        _auto_run_schedule,
        trigger=trigger,
        id=job_id,
        args=[schedule_id],
        misfire_grace_time=600,
    )
    logger.info(f"Registered APScheduler job {job_id} ({schedule_type} @ {schedule_time or '09:00'})")


async def _auto_run_schedule(schedule_id: str) -> None:
    """APScheduler callback — creates a run record then executes the task."""
    from src.database.chat_db import Schedule as ScheduleModel, ScheduleRun
    async with AsyncSessionLocal() as db:
        stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
        res = await db.execute(stmt)
        sched = res.scalar_one_or_none()
        if not sched or sched.status != "active":
            return
        run = ScheduleRun(
            run_id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            status="running",
            engine="playwright",
            attempt=1,
            created_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()
        run_id = run.run_id

    logger.info(f"Auto-run triggered for schedule {schedule_id}, run {run_id}")
    await _run_schedule_task(schedule_id, run_id)


def _sync_send_email(smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str,
                     from_addr: str, to_addr: str, subject: str, html_body: str) -> None:
    """Synchronous email sender — must be called via run_in_executor."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, [to_addr], msg.as_string())


async def _send_result_email(recipient: str, schedule_title: str, output: str) -> None:
    """Send a completion email if SMTP env-vars are configured."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    if not (smtp_host and smtp_user and smtp_pass):
        logger.info("SMTP not configured — skipping email notification.")
        return
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    from_addr = os.getenv("SMTP_FROM", smtp_user)

    html_body = f"""
<html><body style="font-family:sans-serif;background:#0a0f1a;color:#e2e8f0;padding:32px;">
  <div style="max-width:600px;margin:0 auto;background:#111827;border-radius:16px;border:1px solid #1f2937;padding:32px;">
    <h2 style="color:#818cf8;margin-top:0;">&#128295; SciParser AI — Automation Complete</h2>
    <p style="color:#94a3b8;">Your scheduled automation <strong style="color:#e2e8f0;">{schedule_title}</strong> has completed successfully.</p>
    <div style="background:#05070a;border:1px solid #1f2937;border-radius:12px;padding:20px;margin:20px 0;font-family:monospace;font-size:13px;color:#cbd5e1;white-space:pre-wrap;max-height:400px;overflow:hidden;">{output[:3000]}</div>
    <p style="color:#64748b;font-size:12px;margin-bottom:0;">Powered by SciParser AI</p>
  </div>
</body></html>
"""
    subject = f"[SciParser] Automation complete: {schedule_title}"
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _sync_send_email,
            smtp_host, smtp_port, smtp_user, smtp_pass, from_addr, recipient, subject, html_body,
        )
        logger.info(f"Result email sent to {recipient}")
    except Exception as e:
        logger.warning(f"Failed to send result email to {recipient}: {e}")


async def _run_schedule_task(schedule_id: str, run_id: str) -> None:
    """
    Core execution coroutine shared by manual runs and APScheduler auto-runs.
    Runs the stored script, retries up to 3 times with script regeneration, then
    updates last_run / next_run and sends a result email on completion.
    """
    from src.database.chat_db import Schedule as ScheduleModel, ScheduleRun

    # Load schedule once
    async with AsyncSessionLocal() as db:
        stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
        res = await db.execute(stmt)
        sched = res.scalar_one_or_none()
        if not sched:
            return
        title           = sched.title
        current_script  = sched.generated_script or ""
        email_recipient = sched.email_recipient or ""
        schedule_type   = sched.schedule_type or "manual"
        schedule_time   = sched.schedule_time or ""
        # Mark last_run immediately
        sched.last_run = datetime.now(timezone.utc)
        await db.commit()

    start_time       = datetime.now(timezone.utc)
    max_tries        = 3
    current_try      = 0
    last_error       = ""
    current_framework = "playwright"

    while current_try < max_tries:
        current_try += 1

        await plan_stream_manager.broadcast_schedule_update(schedule_id, {
            "type": "pipeline_update",
            "step_id": 4,
            "status": "running",
            "details": f"Attempt {current_try} using {current_framework}...",
        })

        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                f.write(current_script)
                temp_path = f.name

            process = subprocess.Popen(
                [sys.executable, "-u", temp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            full_output: List[str] = []
            if process.stdout:
                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        full_output.append(clean_line)
                        await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                            "type": "log",
                            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                            "engine": current_framework,
                            "message": clean_line,
                        })
                        if "[SCREENSHOT]" in clean_line:
                            match = re.search(r'\[SCREENSHOT\](.*?)\[/SCREENSHOT\]', clean_line, re.DOTALL)
                            if match:
                                await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                                    "type": "screenshot",
                                    "frame": match.group(1).strip(),
                                })

            process.wait(timeout=300)
            if os.path.exists(temp_path):
                os.unlink(temp_path)

            if process.returncode == 0:
                # ── Success ──────────────────────────────────────────────
                output_text = "\n".join(full_output)
                duration    = int((datetime.now(timezone.utc) - start_time).total_seconds())
                next_run_dt = _calculate_next_run(schedule_type, schedule_time)

                async with AsyncSessionLocal() as db:
                    stmt = select(ScheduleRun).where(ScheduleRun.run_id == run_id)
                    res  = await db.execute(stmt)
                    run_db = res.scalar_one()
                    run_db.status           = "completed"
                    run_db.output           = output_text
                    run_db.duration_seconds = duration
                    run_db.finished_at      = datetime.now(timezone.utc)
                    await db.commit()

                async with AsyncSessionLocal() as db:
                    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
                    res  = await db.execute(stmt)
                    sch_db = res.scalar_one()
                    sch_db.extracted_content = output_text
                    sch_db.next_run          = next_run_dt
                    await db.commit()

                await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                    "type": "pipeline_update",
                    "step_id": 6,
                    "status": "completed",
                    "details": "Automation completed successfully.",
                })

                # Send email if recipient configured
                if email_recipient:
                    await _send_result_email(email_recipient, title, output_text)
                return

            else:
                last_error = "\n".join(full_output)
                logger.warning(f"Schedule {schedule_id} attempt {current_try} failed: {last_error[:200]}")
                if current_try < max_tries:
                    if current_try == 2:
                        current_framework = "browser-use"
                    current_script = await brain.code_processor.run_script_generation(
                        title + " (FIXING ERROR: " + last_error[:100] + ")",
                        [],
                        framework=current_framework,
                    )
                    async with AsyncSessionLocal() as db:
                        stmt = select(ScheduleRun).where(ScheduleRun.run_id == run_id)
                        res  = await db.execute(stmt)
                        run_db = res.scalar_one()
                        run_db.attempt = current_try + 1
                        run_db.engine  = current_framework
                        await db.commit()

        except Exception as e:
            last_error = str(e)
            logger.error(f"Schedule {schedule_id} execution error (attempt {current_try}): {e}")
            if current_try >= max_tries:
                break
            async with AsyncSessionLocal() as db:
                stmt = select(ScheduleRun).where(ScheduleRun.run_id == run_id)
                res  = await db.execute(stmt)
                run_db = res.scalar_one()
                run_db.attempt = current_try + 1
                await db.commit()

    # All attempts failed
    async with AsyncSessionLocal() as db:
        stmt = select(ScheduleRun).where(ScheduleRun.run_id == run_id)
        res  = await db.execute(stmt)
        run_db = res.scalar_one()
        run_db.status     = "failed"
        run_db.error_log  = last_error
        run_db.finished_at = datetime.now(timezone.utc)
        await db.commit()

    await plan_stream_manager.broadcast_schedule_update(schedule_id, {
        "type": "pipeline_update",
        "step_id": 4,
        "status": "failed",
        "details": f"Automation failed after {max_tries} attempts.",
    })


async def _load_and_schedule_all() -> None:
    """Load all non-manual active schedules from DB and register APScheduler jobs."""
    from src.database.chat_db import Schedule as ScheduleModel
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(ScheduleModel).where(
                ScheduleModel.schedule_type != "manual",
                ScheduleModel.status == "active",
            )
            res = await db.execute(stmt)
            schedules = res.scalars().all()
            for s in schedules:
                _register_schedule_job(s.schedule_id, s.schedule_type, s.schedule_time)
                next_run = _calculate_next_run(s.schedule_type, s.schedule_time)
                if next_run and not s.next_run:
                    s.next_run = next_run
            await db.commit()
            logger.info(f"APScheduler: registered {len(schedules)} active schedule(s).")
    except Exception as e:
        logger.error(f"_load_and_schedule_all error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    try:
        await brain.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize brain during startup: {e}")
    _scheduler.start()
    asyncio.create_task(_load_and_schedule_all())
    yield
    _scheduler.shutdown(wait=False)
    await brain.shutdown()

app = FastAPI(title="SciParser AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Relaxed for development to ensure WS handshake
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Endpoints ---

@app.post("/sciparser/v1/signup", response_model=UserResponse)
async def signup(req: SignUp, db: AsyncSession = Depends(get_db)):
    return await ChatService.create_user(db, req.username, req.email, req.password)

@app.post("/sciparser/v1/signin", response_model=Token)
async def signin(req: SignIn, db: AsyncSession = Depends(get_db)):
    return await ChatService.authenticate_user(db, req.username, req.password)

@app.get("/sciparser/v1/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(ChatService.get_current_user)):
    return current_user

# --- Upload Endpoints ---

@app.post("/sciparser/v1/upload/metadata")
async def upload_metadata(req: Any, current_user: User = Depends(ChatService.get_current_user)):
    # Mock implementation for now as requested for local run
    file_id = str(uuid.uuid4())
    return {
        "id": file_id,
        "status": "success",
        "upload_url": f"/sciparser/v1/upload/stream/{file_id}"
    }

@app.get("/sciparser/v1/upload/files")
async def get_uploaded_files(current_user: User = Depends(ChatService.get_current_user)):
    # Mock implementation
    return []

# --- Chat Endpoints ---

@app.get("/sciparser/v1/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/sciparser/v1/chat/message", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    chat_id = str(req.chat_id) if req.chat_id else f"thread-{uuid.uuid4()}"
    
    # --- OPTIMIZATION: Cancel existing task for this chat to prevent "multi-time" execution ---
    if chat_id in brain.active_tasks:
        logger.info(f"Cancelling existing task for chat {chat_id} before starting new one.")
        brain.active_tasks[chat_id].cancel()
        try:
            await brain.active_tasks[chat_id]
        except asyncio.CancelledError:
            pass
    
    # Create a task for the message processing to allow cancellation
    task = asyncio.create_task(brain.process_message(current_user.user_id, req.message, chat_id))
    brain.active_tasks[chat_id] = task
    
    try:
        result = await task
        
        # Handle NEEDS_INPUT status (not a failure, but requires user action)
        if result.get("status") == "NEEDS_INPUT":
            form_data = result.get("form", {})
            description = form_data.get("description", "I need more information to proceed.")
            return {
                "message": {
                    "id": str(uuid.uuid4()),
                    "role": "ai",
                    "content": description,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "plan": [],
                    "log_id": str(uuid.uuid4()),
                    "status": "NEEDS_INPUT",
                    "form": form_data
                },
                "chat_id": chat_id,
                "plan": []
            }

        if not result.get("success"):
            error_msg = result.get("message") or result.get("error") or "Unknown error"
            raise HTTPException(status_code=500, detail=error_msg)
    except asyncio.CancelledError:
        # The /chat/stop endpoint already persisted "⛔ Process stopped by user." to DB
        # the moment the user pressed Stop, so we don't need to write it again here.
        # Just return a lightweight response so the HTTP request resolves cleanly.
        logger.info(f"Task for chat_id {chat_id} unwound via CancelledError (stop message already in DB)")
        return {
            "message": {
                "id": str(uuid.uuid4()),
                "role": "ai",
                "content": "⛔ Process stopped by user.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "plan": [],
                "log_id": str(uuid.uuid4())
            },
            "chat_id": chat_id,
            "plan": []
        }
    except BaseException as e:
        # Print the full traceback so the real root cause is always visible in logs.
        tb = traceback.format_exc()
        logger.error(f"Chat endpoint error — full traceback:\n{tb}")

        # Unwrap ExceptionGroup / BaseExceptionGroup to find the leaf cause(s).
        detail = str(e)
        if isinstance(e, BaseExceptionGroup):
            leaves = []
            def _collect(exc):
                if isinstance(exc, BaseExceptionGroup):
                    for sub in exc.exceptions:
                        _collect(sub)
                else:
                    leaves.append(f"{type(exc).__name__}: {exc}")
            _collect(e)
            if leaves:
                detail = " | ".join(leaves)

        raise HTTPException(status_code=500, detail=detail)
    finally:
        brain.active_tasks.pop(chat_id, None)

    ai_msg_data = result.get("message", {})
    
    return {
        "message": {
            "id": ai_msg_data.get("id", str(uuid.uuid4())),
            "role": "ai",
            "content": ai_msg_data.get("content", ""),
            "timestamp": ai_msg_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "plan": result.get("plan", []),
            "log_id": str(uuid.uuid4()) # FIX: Added missing log_id for validation
        },
        "chat_id": chat_id,
        "plan": result.get("plan", [])
    }

@app.post("/sciparser/v1/chat/stop")
async def stop_chat_process(chat_id: str = Query(...), current_user: User = Depends(ChatService.get_current_user)):
    stopped = await brain.stop_process(chat_id, user_id=current_user.user_id)

    # Persist the stopped message to DB immediately so it survives a page refresh,
    # regardless of whether the background task has fully unwound yet.
    ai_msg_id = str(uuid.uuid4())
    try:
        async with AsyncSessionLocal() as db:
            await brain.db_manager.get_or_create_chat_session(current_user.user_id, chat_id)
            ai_msg = Message(
                message_id=ai_msg_id,
                chat_id=chat_id,
                user_id=current_user.user_id,
                role="ai",
                content="⛔ Process stopped by user.",
                plan_data=json.dumps([]),
                created_at=datetime.now(timezone.utc)
            )
            db.add(ai_msg)
            await db.commit()
        logger.info(f"Stop message persisted to DB for chat_id {chat_id}")
    except Exception as e:
        logger.warning(f"Could not persist stop message for {chat_id}: {e}")

    return {"status": "success" if stopped else "not_found", "message_id": ai_msg_id}

@app.get("/sciparser/v1/chat/sessions")
async def get_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    return await ChatService.get_user_sessions(db, current_user.user_id)

@app.get("/sciparser/v1/chat/history")
async def get_history(
    chat_id: str = Query(...), # Use Query parameter
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(ChatService.get_current_user)
):
    # Coerce numeric IDs to string for safety
    return await ChatService.get_chat_history(db, str(chat_id), current_user.user_id)

@app.post("/sciparser/v1/chat/rename")
async def rename_session(req: RenameChatRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    return await ChatService.rename_session(db, req.chat_id, req.title, current_user.user_id)

@app.patch("/sciparser/v1/chat/sessions/{chat_id}/rename") # Match api.ts
async def rename_session(chat_id: str, req: RenameChatRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    return await ChatService.rename_session(db, chat_id, req.title, current_user.user_id)

@app.delete("/sciparser/v1/chat/sessions/{chat_id}")
async def delete_session(chat_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    return await ChatService.delete_session(db, chat_id, current_user.user_id)

@app.post("/sciparser/v1/chat/sessions/{chat_id}/reset-session")
async def reset_session_state(chat_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Wipe the persisted browser session_state for a chat so the next message starts fresh."""
    from src.database.chat_db import ChatSession as ChatSessionModel
    stmt = select(ChatSessionModel).where(
        ChatSessionModel.id == chat_id,
        ChatSessionModel.user_id == current_user.user_id
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.session_state = None
    await db.commit()
    logger.info(f"[reset-session] session_state cleared for chat_id={chat_id} by user={current_user.user_id}")
    return {"status": "success", "message": "Session state cleared."}

@app.get("/sciparser/v1/chat/sessions/{chat_id}/logs")
async def get_agent_logs(chat_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    from src.database.chat_db import AgentExecutionLog
    stmt = select(AgentExecutionLog).where(AgentExecutionLog.chat_id == chat_id).order_by(AgentExecutionLog.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/sciparser/v1/chat/sessions/{chat_id}/tools")
async def get_tool_logs(chat_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    from src.database.chat_db import ToolExecutionLog
    stmt = select(ToolExecutionLog).where(ToolExecutionLog.chat_id == chat_id).order_by(ToolExecutionLog.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

# --- Scheduler Endpoints ---

@app.post("/sciparser/v1/scheduler/create", response_model=ScheduleResponse)
async def create_schedule(req: ScheduleRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    from src.database.chat_db import ToolExecutionLog, Schedule as ScheduleModel

    # 1. Create schedule first so ChatService populates user_prompt/plan_data/assistant_response
    schedule = await ChatService.create_schedule(db, current_user.user_id, req)

    # 2. Fetch the selected tool logs to build the script
    stmt = select(ToolExecutionLog).where(ToolExecutionLog.id.in_(req.selected_tool_ids))
    res = await db.execute(stmt)
    tool_logs = res.scalars().all()

    execution_history = [
        {
            "tool": log.tool_name,
            "input": json.loads(log.tool_input) if log.tool_input else {},
            "output": log.tool_output[:1000] if log.tool_output else "",
            "status": log.status,
            "error": log.error_message,
        }
        for log in tool_logs
    ]

    # 3. Build tool_context list from request (frontend-supplied summaries of successful tools)
    tool_context = [
        {"tool_name": item.tool_name, "output": item.output}
        for item in (req.tool_context or [])
    ]

    # 4. Auto-detect the best script framework from the tools that were actually used.
    _TAVILY_TOOLS    = {"tavily_search_results_json", "ai_parser_dynamic_search"}
    _BROWSER_PREFIXES = ("browser_", "navigate", "click", "type", "scroll", "fill", "select", "playwright")

    all_tool_names = {
        (item.get("tool_name") or item.get("tool") or "").lower()
        for item in (tool_context or []) + execution_history
    }
    all_tool_names.discard("")

    has_browser = any(name.startswith(p) for name in all_tool_names for p in _BROWSER_PREFIXES)
    has_tavily  = any(name in _TAVILY_TOOLS for name in all_tool_names)
    framework   = "tavily" if (has_tavily and not has_browser) else "playwright"

    logger.info(f"Script generation framework selected: {framework} "
                f"(tools: {all_tool_names or 'none from context'})")

    # 5. Reload the freshly created schedule to get user_prompt / plan_data
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule.schedule_id)
    res  = await db.execute(stmt)
    schedule_db = res.scalar_one()

    # 6. Generate script with full context (user goal + agent plan)
    generated_script = await brain.code_processor.run_script_generation(
        req.title,
        execution_history,
        framework=framework,
        tool_context=tool_context,
        user_goal=schedule_db.user_prompt or "",
        plan_context=schedule_db.plan_data or "",
    )

    # 7. Save generated script + compute next_run
    schedule_time = getattr(req, "schedule_time", None)
    schedule_db.generated_script = generated_script
    schedule_db.next_run = _calculate_next_run(req.schedule_type, schedule_time)
    await db.commit()

    # 8. Register APScheduler job for non-manual schedules
    if req.schedule_type not in ("manual", None):
        _register_schedule_job(schedule.schedule_id, req.schedule_type, schedule_time)

    return {
        "schedule_id": schedule.schedule_id,
        "status": schedule.status,
        "created_at": schedule.created_at,
    }

@app.get("/sciparser/v1/scheduler/list")
async def get_schedules(db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = select(ScheduleModel).where(ScheduleModel.user_id == current_user.user_id).order_by(ScheduleModel.created_at.desc())
    res = await db.execute(stmt)
    schedules = res.scalars().all()
    return [
        {
            "schedule_id":       s.schedule_id,
            "title":             s.title,
            "schedule_type":     s.schedule_type,
            "schedule_time":     s.schedule_time,
            "email_recipient":   s.email_recipient,
            "status":            s.status,
            "generated_script":  s.generated_script,
            "extracted_content": s.extracted_content,
            "assistant_response": s.assistant_response,
            "plan_data":         s.plan_data,
            "user_prompt":       s.user_prompt,
            "next_run":          s.next_run.isoformat() if s.next_run else None,
            "last_run":          s.last_run.isoformat() if s.last_run else None,
            "created_at":        s.created_at.isoformat() if s.created_at else None,
            "updated_at":        s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in schedules
    ]

@app.delete("/sciparser/v1/scheduler/{schedule_id}")
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Delete a schedule and remove its APScheduler job."""
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = delete(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    await db.execute(stmt)
    await db.commit()
    job_id = f"sched_{schedule_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    return {"status": "success"}

@app.patch("/sciparser/v1/scheduler/{schedule_id}")
async def update_schedule(schedule_id: str, req: Dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Update schedule details and re-register APScheduler job if timing changed."""
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    res = await db.execute(stmt)
    schedule = res.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if "title" in req:          schedule.title          = req["title"]
    if "schedule_type" in req:  schedule.schedule_type  = req["schedule_type"]
    if "schedule_time" in req:  schedule.schedule_time  = req["schedule_time"]
    if "email_recipient" in req: schedule.email_recipient = req["email_recipient"]
    if "status" in req:         schedule.status         = req["status"]

    # Recalculate next_run whenever schedule type/time changes
    if "schedule_type" in req or "schedule_time" in req:
        schedule.next_run = _calculate_next_run(schedule.schedule_type, schedule.schedule_time)
        if schedule.schedule_type not in ("manual", None):
            _register_schedule_job(schedule_id, schedule.schedule_type, schedule.schedule_time)
        else:
            job_id = f"sched_{schedule_id}"
            if _scheduler.get_job(job_id):
                _scheduler.remove_job(job_id)

    await db.commit()
    return {"status": "success"}

@app.post("/sciparser/v1/scheduler/{schedule_id}/run")
async def run_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Manually trigger a schedule execution."""
    from src.database.chat_db import Schedule as ScheduleModel, ScheduleRun
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Schedule not found")

    run = ScheduleRun(
        run_id=str(uuid.uuid4()),
        schedule_id=schedule_id,
        status="running",
        engine="playwright",
        attempt=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    run_id = run.run_id

    asyncio.create_task(_run_schedule_task(schedule_id, run_id))
    return {"status": "success", "run_id": run_id}


# --- WebSocket Endpoints ---

async def get_token_user(token: str, db: AsyncSession):
    """Helper to validate token and return user in WebSocket."""
    try:
        return await ChatService.get_current_user(token, db)
    except Exception:
        return None

@app.websocket("/sciparser/v1/ws/plan/{chat_id}")
async def websocket_plan_endpoint(
    websocket: WebSocket, 
    chat_id: str, 
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # Accept first to prevent 403 handshake rejection
    await websocket.accept()
    
    user = await get_token_user(token, db)
    if not user:
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=1008)
        return

    # Verify ownership or allow if it's a new thread (will be created on first message)
    session = await ChatService.get_session_by_id(db, chat_id, user.user_id)
    # We don't close if session is missing here because it might be a brand new chat
    
    await plan_stream_manager.connect(chat_id, websocket)
    
    # --- NEW: Rehydrate UI on connect if task is active ---
    if chat_id in brain.active_plans:
        await websocket.send_json({
            "type": "plan_update", 
            "data": brain.active_plans[chat_id]
        })

    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        plan_stream_manager.disconnect(chat_id, websocket)
        # Auto-cancel the running agent when the last client disconnects (e.g. page reload)
        remaining = plan_stream_manager.active_connections.get(chat_id, [])
        if not remaining and chat_id in brain.active_tasks:
            logger.info(f"Last WS for {chat_id} closed — auto-cancelling agent task.")
            asyncio.create_task(brain.stop_process(chat_id, user_id=user.user_id))
    except Exception as e:
        _emsg = str(e)
        # "Cannot call receive once a disconnect message has been received" is a normal
        # client-initiated close — treat it silently like WebSocketDisconnect.
        if "Cannot call" in _emsg or "disconnect" in _emsg.lower():
            pass
        else:
            logger.error(f"Plan stream error: {e}")
        plan_stream_manager.disconnect(chat_id, websocket)
        remaining = plan_stream_manager.active_connections.get(chat_id, [])
        if not remaining and chat_id in brain.active_tasks:
            logger.info(f"Last WS for {chat_id} closed — auto-cancelling agent task.")
            asyncio.create_task(brain.stop_process(chat_id, user_id=user.user_id))

@app.websocket("/sciparser/v1/browser/stream")
async def browser_stream(
    websocket: WebSocket, 
    chat_id: str = Query(...), 
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # Accept first to prevent 403 handshake rejection
    await websocket.accept()
    
    user = await get_token_user(token, db)
    if not user:
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=1008)
        return

    # Use user.user_id for browser session mapping instead of chat_id
    await plan_stream_manager.connect(user.user_id, websocket, is_browser=True)

    # Immediately replay the last frame so reconnecting clients never see a blank panel
    cached = plan_stream_manager.last_frame.get(user.user_id)
    if cached:
        try:
            await websocket.send_json({"event": "frame", "data": cached})
        except Exception:
            pass

    try:
        while True:
            # Keep connection alive — receive() handles text, binary, and ping/pong
            await websocket.receive()
    except WebSocketDisconnect:
        plan_stream_manager.disconnect(user.user_id, websocket, is_browser=True)
    except Exception as e:
        _emsg = str(e)
        if "Cannot call" in _emsg or "disconnect" in _emsg.lower():
            pass
        else:
            logger.error(f"Browser stream error: {e}")
        plan_stream_manager.disconnect(user.user_id, websocket, is_browser=True)

@app.post("/sciparser/v1/browser/state")
async def toggle_browser_state(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    return {"status": "success", "is_active": req.get("is_active")}

@app.post("/sciparser/v1/browser/connect-cdp")
async def connect_cdp(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    """Store a user-provided CDP URL and verify it is reachable before accepting it."""
    import ipaddress, socket as _socket
    from urllib.parse import urlparse as _urlparse

    cdp_url = (req.get("cdp_url") or "").strip()
    if not cdp_url:
        raise HTTPException(status_code=400, detail="cdp_url is required")

    # -- SSRF guard ----------------------------------------------------------------
    # Only allow http/https/ws/wss schemes and block private/loopback/link-local IPs.
    _parsed = _urlparse(cdp_url)
    if _parsed.scheme not in ("http", "https", "ws", "wss"):
        raise HTTPException(status_code=400, detail="cdp_url must use http, https, ws, or wss")
    _host = _parsed.hostname or ""
    if not _host:
        raise HTTPException(status_code=400, detail="cdp_url must include a valid hostname")
    try:
        _resolved_ip = _socket.gethostbyname(_host)
        _ip_obj = ipaddress.ip_address(_resolved_ip)
        if (
            _ip_obj.is_loopback
            or _ip_obj.is_private
            or _ip_obj.is_link_local
            or _ip_obj.is_reserved
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "CDP URL resolves to a private/internal address. "
                    "Use a public tunnel URL (e.g. from cloudflared or ngrok)."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"Cannot resolve hostname: {_host}")
    # ------------------------------------------------------------------------------

    # Normalise ws(s):// → http(s):// for the /json/version health-check
    check_base = cdp_url.rstrip("/")
    if check_base.startswith("wss://"):
        check_base = "https://" + check_base[6:]
    elif check_base.startswith("ws://"):
        check_base = "http://" + check_base[5:]

    try:
        async with _httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(f"{check_base}/json/version")
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"CDP endpoint returned HTTP {resp.status_code}")
    except _httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot reach CDP URL: {exc}")

    session = brain.session_manager.get_session(current_user.user_id)
    session["cdp_url"] = cdp_url
    # Tear down any existing MCP manager so the next run uses the new endpoint
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None

    return {"status": "connected", "cdp_url": cdp_url}


@app.delete("/sciparser/v1/browser/connect-cdp")
async def disconnect_cdp(current_user: User = Depends(ChatService.get_current_user)):
    """Remove the user's CDP override and reset the MCP manager."""
    session = brain.session_manager.get_session(current_user.user_id)
    session["cdp_url"] = None
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None
    return {"status": "disconnected"}


@app.get("/sciparser/v1/browser/cdp-status")
async def get_cdp_status(current_user: User = Depends(ChatService.get_current_user)):
    """Return whether the user has an external CDP browser connected."""
    session = brain.session_manager.get_session(current_user.user_id)
    cdp_url = session.get("cdp_url")
    return {"connected": cdp_url is not None, "cdp_url": cdp_url}


def _mask_proxy_url(proxy_url: str) -> str:
    """Return proxy URL with password replaced by *** for display."""
    from urllib.parse import urlparse as _up, urlunparse as _uu
    try:
        _p = _up(proxy_url)
        if _p.password:
            netloc = f"{_p.username}:***@{_p.hostname}"
            if _p.port:
                netloc += f":{_p.port}"
            return _uu((_p.scheme, netloc, _p.path, _p.params, _p.query, _p.fragment))
    except Exception:
        pass
    return proxy_url


@app.post("/sciparser/v1/settings/proxy")
async def set_proxy(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user), db: AsyncSession = Depends(get_db)):
    """Store a residential proxy URL for the current user's browser sessions (persisted to DB)."""
    from urllib.parse import urlparse as _urlparse
    proxy_url = (req.get("proxy_url") or "").strip()
    if not proxy_url:
        raise HTTPException(status_code=400, detail="proxy_url is required")
    _parsed = _urlparse(proxy_url)
    if _parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="proxy_url must use http or https scheme")
    if not _parsed.hostname:
        raise HTTPException(status_code=400, detail="proxy_url must include a valid hostname")
    # Persist to DB
    result = await db.execute(select(User).where(User.user_id == current_user.user_id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.proxy_url = proxy_url
        await db.commit()
    # Update in-memory session
    session = brain.session_manager.get_session(current_user.user_id)
    session["proxy_url"] = proxy_url
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None
    return {"status": "saved", "proxy_url_masked": _mask_proxy_url(proxy_url)}


@app.delete("/sciparser/v1/settings/proxy")
async def delete_proxy(current_user: User = Depends(ChatService.get_current_user), db: AsyncSession = Depends(get_db)):
    """Remove the user's proxy configuration (persisted to DB)."""
    result = await db.execute(select(User).where(User.user_id == current_user.user_id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.proxy_url = None
        await db.commit()
    session = brain.session_manager.get_session(current_user.user_id)
    session["proxy_url"] = None
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None
    return {"status": "removed"}


@app.get("/sciparser/v1/settings/proxy")
async def get_proxy_status(current_user: User = Depends(ChatService.get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the user's current proxy configuration (password masked). Loads from DB if not cached."""
    session = brain.session_manager.get_session(current_user.user_id)
    proxy_url = session.get("proxy_url")
    # Lazy-load from DB on first access (e.g. after server restart)
    if proxy_url is None:
        result = await db.execute(select(User).where(User.user_id == current_user.user_id))
        db_user = result.scalar_one_or_none()
        if db_user and db_user.proxy_url:
            proxy_url = db_user.proxy_url
            session["proxy_url"] = proxy_url  # cache in session
    masked = _mask_proxy_url(proxy_url) if proxy_url else None
    return {"active": proxy_url is not None, "proxy_url_masked": masked}


@app.post("/sciparser/v1/settings/proxy/test")
async def test_proxy(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    """Test a proxy URL by routing a request to an IP-check service through it."""
    proxy_url = (req.get("proxy_url") or "").strip()
    if not proxy_url:
        session = brain.session_manager.get_session(current_user.user_id)
        proxy_url = session.get("proxy_url") or ""
    if not proxy_url:
        raise HTTPException(status_code=400, detail="No proxy_url provided or saved")
    try:
        async with _httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
            resp = await client.get("https://api.ipify.org?format=json")
        data = resp.json()
        return {"status": "ok", "exit_ip": data.get("ip", "unknown")}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Proxy test failed: {exc}")


@app.get("/sciparser/v1/settings/browser-engine")
async def get_browser_engine(current_user: User = Depends(ChatService.get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the user's preferred browser engine (camoufox or chrome)."""
    session = brain.session_manager.get_session(current_user.user_id)
    session_engine = session.get("browser_engine")
    if session_engine is not None:
        return {"engine": session_engine}
    result = await db.execute(select(User).where(User.user_id == current_user.user_id))
    db_user = result.scalar_one_or_none()
    db_engine = db_user.browser_engine if db_user else None
    if db_engine is not None:
        # Explicit user choice stored in DB — cache it in session for this run
        session["browser_engine"] = db_engine
        return {"engine": db_engine}
    # No explicit user choice — honour env var, DON'T write to session so
    # MCPToolManager's own fallback chain (browser_engine → BROWSER_ENGINE env → camoufox) is preserved
    return {"engine": os.getenv("BROWSER_ENGINE", "camoufox")}


@app.post("/sciparser/v1/settings/browser-engine")
async def set_browser_engine(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user), db: AsyncSession = Depends(get_db)):
    """Set the user's preferred browser engine (camoufox or chrome)."""
    engine = (req.get("engine") or "camoufox").strip().lower()
    if engine not in ("camoufox", "chrome"):
        raise HTTPException(status_code=400, detail="engine must be 'camoufox' or 'chrome'")
    result = await db.execute(select(User).where(User.user_id == current_user.user_id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.browser_engine = engine
        await db.commit()
    session = brain.session_manager.get_session(current_user.user_id)
    session["browser_engine"] = engine
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None
    return {"status": "saved", "engine": engine}


@app.post("/sciparser/v1/browser/close")
async def close_browser_session(current_user: User = Depends(ChatService.get_current_user)):
    """Close the browser process for the current user (keeps session alive for reuse)."""
    await brain.session_manager.close_browser(current_user.user_id)
    return {"status": "success", "message": "Browser session closed."}

@app.get("/sciparser/v1/browser/check")
async def check_browser_session(current_user: User = Depends(ChatService.get_current_user)):
    """Check if a browser session is active for the current user."""
    session = brain.session_manager.get_session(current_user.user_id)
    is_active = session.get("mcp_manager") is not None
    return {"status": "success", "is_active": is_active}

@app.get("/sciparser/v1/chat/sessions/{chat_id}/tool-logs-live")
async def get_live_tool_logs(chat_id: str, current_user: User = Depends(ChatService.get_current_user)):
    """Return the in-memory tool event buffer for an active execution."""
    return {"tool_logs": brain.get_live_tool_logs(chat_id)}

@app.get("/sciparser/v1/scheduler/{schedule_id}/runs")
async def get_schedule_runs(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Get execution history for a specific schedule."""
    return await ChatService.get_schedule_runs(db, schedule_id)

@app.websocket("/sciparser/v1/ws/schedule/{schedule_id}")
async def websocket_schedule_endpoint(
    websocket: WebSocket, 
    schedule_id: str, 
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket for real-time schedule monitoring (logs, pipeline, screenshots)."""
    await websocket.accept()
    
    user = await get_token_user(token, db)
    if not user:
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=1008)
        return

    await plan_stream_manager.connect(schedule_id, websocket, is_schedule=True)
    try:
        while True:
            # Keep connection alive, updates are pushed via broadcast_schedule_update
            await websocket.receive_text()
    except WebSocketDisconnect:
        plan_stream_manager.disconnect(schedule_id, websocket, is_schedule=True)
    except Exception as e:
        logger.error(f"Schedule stream error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  COGNITIVE MEMORY API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/memory/episodes")
async def get_memory_episodes(
    domain: Optional[str] = Query(None, description="Filter by domain, e.g. 'zillow.com'"),
    limit: int = Query(20, ge=1, le=100),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_token_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not brain.memory_service:
        return []
    return await brain.memory_service.get_recent_episodes(str(user.id), domain=domain, limit=limit)


@app.get("/memory/skills")
async def get_memory_skills(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_token_user(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not brain.memory_service:
        return []
    return await brain.memory_service.get_all_skills(str(user.id))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)