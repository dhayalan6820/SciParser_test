import re
import sys
import uuid
import json
import asyncio
import traceback
import httpx as _httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    # Initialize brain (LLMs, Browser, MCP) on startup
    try:
        await brain.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize brain during startup: {e}")
    yield
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
    # 1. Fetch the selected tool logs to build the script
    from src.database.chat_db import ToolExecutionLog
    stmt = select(ToolExecutionLog).where(ToolExecutionLog.id.in_(req.selected_tool_ids))
    res = await db.execute(stmt)
    tool_logs = res.scalars().all()
    
    execution_history = [
        {
            "tool": log.tool_name,
            "input": json.loads(log.tool_input) if log.tool_input else {},
            "output": log.tool_output[:1000] if log.tool_output else "",
            "status": log.status,
            "error": log.error_message
        }
        for log in tool_logs
    ]
    
    # 2. Build tool_context list from request (frontend-supplied summaries of successful tools)
    tool_context = [
        {"tool_name": item.tool_name, "output": item.output}
        for item in (req.tool_context or [])
    ]

    # 3. Auto-detect the best script framework from the tools that were actually used.
    #    Tavily-only sessions → generate a Tavily search script (no browser needed).
    #    Any browser tool present → use Playwright (default).
    _TAVILY_TOOLS = {"tavily_search_results_json", "ai_parser_dynamic_search"}
    _BROWSER_PREFIXES = ("browser_", "navigate", "click", "type", "scroll", "fill", "select", "playwright")

    all_tool_names = {(item.get("tool_name") or item.get("tool") or "").lower()
                      for item in (tool_context or []) + execution_history}
    all_tool_names.discard("")

    has_browser = any(
        name.startswith(prefix) for name in all_tool_names for prefix in _BROWSER_PREFIXES
    )
    has_tavily  = any(name in _TAVILY_TOOLS for name in all_tool_names)

    if has_tavily and not has_browser:
        framework = "tavily"
    else:
        framework = "playwright"

    logger.info(f"Script generation framework selected: {framework} "
                f"(tools: {all_tool_names or 'none from context'})")

    # 4. Generate the Python script using the specialized code model
    generated_script = await brain.code_processor.run_script_generation(
        req.title, execution_history, framework=framework, tool_context=tool_context
    )
    
    # 3. Create the schedule with the generated script
    schedule = await ChatService.create_schedule(db, current_user.user_id, req)
    
    # Update the schedule with the generated script
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule.schedule_id)
    res = await db.execute(stmt)
    schedule_db = res.scalar_one()
    schedule_db.generated_script = generated_script
    await db.commit()
    
    return {
        "schedule_id": schedule.schedule_id,
        "status": schedule.status,
        "created_at": schedule.created_at
    }

@app.get("/sciparser/v1/scheduler/list")
async def get_schedules(db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    return await ChatService.get_user_schedules(db, current_user.user_id)

@app.delete("/sciparser/v1/scheduler/{schedule_id}")
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Delete a schedule."""
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = delete(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}

@app.patch("/sciparser/v1/scheduler/{schedule_id}")
async def update_schedule(schedule_id: str, req: Dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Update schedule details (title, type, recipient)."""
    from src.database.chat_db import Schedule as ScheduleModel
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    res = await db.execute(stmt)
    schedule = res.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if "title" in req: schedule.title = req["title"]
    if "schedule_type" in req: schedule.schedule_type = req["schedule_type"]
    if "email_recipient" in req: schedule.email_recipient = req["email_recipient"]
    if "status" in req: schedule.status = req["status"]
    
    await db.commit()
    return {"status": "success"}

@app.post("/sciparser/v1/scheduler/{schedule_id}/run")
async def run_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(ChatService.get_current_user)):
    """Manually trigger a schedule execution."""
    # 1. Fetch the schedule
    from src.database.chat_db import Schedule as ScheduleModel, ScheduleRun
    stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id, ScheduleModel.user_id == current_user.user_id)
    res = await db.execute(stmt)
    schedule = res.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # 2. Create a run record
    run = ScheduleRun(
        run_id=str(uuid.uuid4()),
        schedule_id=schedule_id,
        status="running",
        engine="playwright",
        attempt=1,
        created_at=datetime.now(timezone.utc)
    )
    db.add(run)
    await db.commit()
    
    # 3. Execute the script in a background task
    async def execute_task():
        import subprocess
        import tempfile
        import os
        import re
        
        start_time = datetime.now(timezone.utc)
        max_tries = 3
        current_try = 0
        last_error = ""
        current_script = schedule.generated_script
        current_framework = "playwright"
        execution_summary = ""

        while current_try < max_tries:
            current_try += 1
            
            # Broadcast start of attempt
            await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                "type": "pipeline_update",
                "step_id": 4,
                "status": "running",
                "details": f"Attempt {current_try} using {current_framework}..."
            })

            try:
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8') as f:
                    f.write(current_script)
                    temp_path = f.name

                # Run the script and capture output line by line
                process = subprocess.Popen(
                    [sys.executable, "-u", temp_path], # -u for unbuffered output
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                full_output = []
                if process.stdout:
                    for line in process.stdout:
                        clean_line = line.strip()
                        if clean_line:
                            full_output.append(clean_line)
                            # Broadcast log line to UI
                            await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                                "type": "log",
                                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                                "engine": current_framework,
                                "message": clean_line
                            })
                            
                            # Check for screenshot markers in output (if script is configured to emit them)
                            if "[SCREENSHOT]" in clean_line:
                                match = re.search(r'\[SCREENSHOT\](.*?)\s*\[/SCREENSHOT\]', clean_line, re.DOTALL)
                                if match:
                                    await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                                        "type": "screenshot",
                                        "frame": match.group(1).strip()
                                    })

                process.wait(timeout=300)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

                if process.returncode == 0:
                    # Success!
                    async with AsyncSessionLocal() as task_db:
                        stmt = select(ScheduleRun).where(ScheduleRun.run_id == run.run_id)
                        res = await task_db.execute(stmt)
                        run_db = res.scalar_one()
                        run_db.status = "completed"
                        run_db.output = "\n".join(full_output)
                        run_db.duration_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
                        run_db.finished_at = datetime.now(timezone.utc)
                        await task_db.commit()
                        
                        stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
                        res = await task_db.execute(stmt)
                        sch_db = res.scalar_one()
                        sch_db.extracted_content = run_db.output
                        await task_db.commit()
                        
                        # Broadcast completion
                        await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                            "type": "pipeline_update",
                            "step_id": 6,
                            "status": "completed",
                            "details": "Automation completed successfully."
                        })
                        return
                else:
                    last_error = "\n".join(full_output)
                    logger.warning(f"Attempt {current_try} failed: {last_error}")
                    
                    if current_try < max_tries:
                        # Rectify and regenerate
                        if current_try == 2:
                            current_framework = "browser-use"
                        
                        logger.info(f"Regenerating script for {current_framework} due to error.")
                        current_script = await brain.code_processor.run_script_generation(
                            schedule.title + " (FIXING ERROR: " + last_error[:100] + ")", 
                            [], 
                            framework=current_framework
                        )
                        
                        # Update run record for retry
                        async with AsyncSessionLocal() as task_db:
                            stmt = select(ScheduleRun).where(ScheduleRun.run_id == run.run_id)
                            res = await task_db.execute(stmt)
                            run_db = res.scalar_one()
                            run_db.attempt = current_try + 1
                            run_db.engine = current_framework
                            await task_db.commit()
                    else:
                        # Final failure handled outside the loop
                        pass
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error during execution attempt {current_try}: {e}")
                if current_try >= max_tries:
                    break
                
                # Update run record for retry on exception
                async with AsyncSessionLocal() as task_db:
                    stmt = select(ScheduleRun).where(ScheduleRun.run_id == run.run_id)
                    res = await task_db.execute(stmt)
                    run_db = res.scalar_one()
                    run_db.attempt = current_try + 1
                    await task_db.commit()
            
        # If we reach here, all attempts failed
        async with AsyncSessionLocal() as task_db:
            stmt = select(ScheduleRun).where(ScheduleRun.run_id == run.run_id)
            res = await task_db.execute(stmt)
            run_db = res.scalar_one()
            run_db.status = "failed"
            run_db.error_log = last_error
            run_db.finished_at = datetime.now(timezone.utc)
            await task_db.commit()
            
            # Broadcast failure
            await plan_stream_manager.broadcast_schedule_update(schedule_id, {
                "type": "pipeline_update",
                "step_id": 4,
                "status": "failed",
                "details": f"Automation failed after {max_tries} attempts."
            })
            return

    asyncio.create_task(execute_task())
    return {"status": "success", "run_id": run.run_id}


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


@app.post("/sciparser/v1/settings/proxy")
async def set_proxy(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    """Store a residential proxy URL for the current user's browser sessions."""
    from urllib.parse import urlparse as _urlparse
    proxy_url = (req.get("proxy_url") or "").strip()
    if not proxy_url:
        raise HTTPException(status_code=400, detail="proxy_url is required")
    _parsed = _urlparse(proxy_url)
    if _parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="proxy_url must use http or https scheme")
    if not _parsed.hostname:
        raise HTTPException(status_code=400, detail="proxy_url must include a valid hostname")
    session = brain.session_manager.get_session(current_user.user_id)
    session["proxy_url"] = proxy_url
    if session.get("mcp_manager"):
        try:
            await session["mcp_manager"].close()
        except Exception:
            pass
        session["mcp_manager"] = None
    return {"status": "saved"}


@app.delete("/sciparser/v1/settings/proxy")
async def delete_proxy(current_user: User = Depends(ChatService.get_current_user)):
    """Remove the user's proxy configuration."""
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
async def get_proxy_status(current_user: User = Depends(ChatService.get_current_user)):
    """Return the user's current proxy configuration (password masked)."""
    from urllib.parse import urlparse as _urlparse, urlunparse as _urlunparse
    session = brain.session_manager.get_session(current_user.user_id)
    proxy_url = session.get("proxy_url")
    masked: str | None = None
    if proxy_url:
        try:
            _p = _urlparse(proxy_url)
            if _p.password:
                # Rebuild with password replaced by ***
                netloc = f"{_p.username}:***@{_p.hostname}"
                if _p.port:
                    netloc += f":{_p.port}"
                masked = _urlunparse((_p.scheme, netloc, _p.path, _p.params, _p.query, _p.fragment))
            else:
                masked = proxy_url
        except Exception:
            masked = proxy_url
    return {"active": proxy_url is not None, "proxy_url_masked": masked}


@app.post("/sciparser/v1/settings/proxy/test")
async def test_proxy(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    """Test a proxy URL by routing a request to an IP-check service through it."""
    proxy_url = (req.get("proxy_url") or "").strip()
    if not proxy_url:
        # Fall back to checking the stored proxy
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