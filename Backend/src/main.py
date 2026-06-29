import re
import sys
import uuid
import json
import asyncio
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
        self.schedule_connections: Dict[str, List[WebSocket]] = {} # New: Track schedule monitoring connections

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

    async def broadcast_frame(self, frame_data: Any, user_id: str, is_tool: bool = False):
        """Broadcasts a base64 CDP frame or tool log to all connected browser stream clients for a user."""
        if user_id in self.browser_connections:
            event_type = "tool_log" if is_tool else "frame"
            for connection in self.browser_connections[user_id]:
                try:
                    await connection.send_json({"event": event_type, "data": frame_data})
                except Exception:
                    pass

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
        # Save the cancellation message to DB so it persists on reload
        ai_msg_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as db:
            # CRITICAL: Ensure the session exists before adding a message to it
            # (In case the process was stopped before the session was created in brain.py)
            await brain.db_manager.get_or_create_chat_session(current_user.user_id, chat_id)
            
            ai_msg = Message(
                message_id=ai_msg_id,
                chat_id=chat_id,
                user_id=current_user.user_id,
                role="ai",
                content="Process stopped by user.",
                plan_data=json.dumps([]),
                created_at=datetime.now(timezone.utc)
            )
            db.add(ai_msg)
            await db.commit()

        return {
            "message": {
                "id": ai_msg_id,
                "role": "ai",
                "content": "Process stopped by user.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "plan": [],
                "log_id": str(uuid.uuid4())
            },
            "chat_id": chat_id,
            "plan": []
        }
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
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
    return {"status": "success" if stopped else "not_found"}

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
    
    # 2. Generate the Python script using the specialized code model
    generated_script = await brain.code_processor.run_script_generation(req.title, execution_history)
    
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
            await websocket.receive_text()
    except WebSocketDisconnect:
        plan_stream_manager.disconnect(chat_id, websocket)

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
    try:
        while True:
            # Keep connection alive, frames are pushed via broadcast_frame
            await websocket.receive_text()
    except WebSocketDisconnect:
        plan_stream_manager.disconnect(user.user_id, websocket, is_browser=True)
    except Exception as e:
        logger.error(f"Browser stream error: {e}")

@app.post("/sciparser/v1/browser/state")
async def toggle_browser_state(req: Dict[str, Any], current_user: User = Depends(ChatService.get_current_user)):
    return {"status": "success", "is_active": req.get("is_active")}

@app.post("/sciparser/v1/browser/close")
async def close_browser_session(current_user: User = Depends(ChatService.get_current_user)):
    """Manually close the browser session for the current user."""
    await brain.session_manager.shutdown_session(current_user.user_id)
    return {"status": "success", "message": "Browser session closed."}

@app.get("/sciparser/v1/browser/check")
async def check_browser_session(current_user: User = Depends(ChatService.get_current_user)):
    """Check if a browser session is active for the current user."""
    session = brain.session_manager.get_session(current_user.user_id)
    is_active = session.get("mcp_manager") is not None
    return {"status": "success", "is_active": is_active}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)