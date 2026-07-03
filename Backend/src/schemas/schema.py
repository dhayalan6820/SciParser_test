from datetime import datetime
from typing import List, TypedDict, Annotated, Sequence, Dict, Any, Optional, Literal
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, EmailStr

class Credentials(BaseModel):
    username: str
    password: str

class SignIn(BaseModel):
    username: str
    password: str

class SignUp(BaseModel):
    username: str
    email: EmailStr
    password: str

class FileUploadMetadata(BaseModel):
    fileName: str
    fileSize: int
    fileType: str

class FileResponse(BaseModel):
    id: str
    name: str
    size: int
    type: str
    url: str
    uploaded_at: str

class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str = "user"
    status: str = "active"
    created_at: datetime 
    updated_at: datetime 

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 style


class AdminUpdateUserRequest(BaseModel):
    role: Optional[Literal["admin", "user"]] = None
    status: Optional[Literal["active", "suspended"]] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class AdminUserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


class OperationsMetricsResponse(BaseModel):
    total_runs: int
    success_count: int
    failure_count: int
    success_rate: float
    total_tokens: int
    total_cost: float
    daily_trends: List[Dict[str, Any]]
    top_errors: List[Dict[str, Any]]
    status_breakdown: List[Dict[str, Any]]


class AdminOverviewResponse(BaseModel):
    """KPI cards for the Admin Dashboard overview, all from real recorded data."""
    total_users: int
    active_users: int
    running_agents: int
    completed_automations: int
    success_rate: float
    success_rate_change: float
    total_tokens: int
    total_tokens_change: float
    total_cost: float
    total_cost_change: float
    total_runs: int
    total_runs_change: float
    runs_sparkline: List[int]
    tokens_sparkline: List[int]


class AdminActivityItem(BaseModel):
    type: str
    title: str
    detail: Optional[str] = None
    status: Optional[str] = None
    timestamp: datetime


class AdminActivityResponse(BaseModel):
    items: List[AdminActivityItem]


class AdminAgentRun(BaseModel):
    id: str
    chat_id: str
    user_id: str
    stage_name: str
    status: str
    tokens: int
    cost: float
    error_message: Optional[str] = None
    created_at: datetime


class AdminAgentRunsResponse(BaseModel):
    runs: List[AdminAgentRun]
    total: int
    running_count: int
    queued_count: int
    failed_count: int
    completed_count: int
    avg_runtime_seconds: float


class AdminAutomationSummary(BaseModel):
    schedule_id: str
    title: Optional[str] = None
    status: str
    schedule_type: str
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    total_runs: int
    success_runs: int
    failed_runs: int
    success_rate: float


class AdminAutomationsResponse(BaseModel):
    automations: List[AdminAutomationSummary]


class AdminBrowserSession(BaseModel):
    user_id: str
    username: Optional[str] = None
    active_chat_count: int
    browser_active: bool
    browser_engine: Optional[str] = None
    proxy_configured: bool


class AdminBrowserSessionsResponse(BaseModel):
    sessions: List[AdminBrowserSession]
    active_count: int


class AdminUsageResponse(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    daily_usage: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]


class AdminSecurityResponse(BaseModel):
    suspended_users: List[Dict[str, Any]]
    recent_signups: List[Dict[str, Any]]

class BackendChatMessage(BaseModel):
    id: Optional[str] = None # Added to match frontend 'id'
    log_id: Optional[str] = None # Changed to Optional to prevent validation failure
    role: str
    content: str
    timestamp: str
    plan: Optional[List[Dict[str, Any]]] = None # Added to support saving the agent process
    form: Optional[Dict[str, Any]] = None # Added to support dynamic forms for NEEDS_INPUT status
    tool_calls: Optional[List[Dict[str, Any]]] = None # Real ToolExecutionLog ids used to produce this AI message

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None  # Matches frontend 'message'
    chat_id: Optional[str] = None
    files: Optional[List[str]] = None
    prefer_live_browser: bool = False
    preferLiveBrowser: Optional[bool] = None # Matches frontend 'preferLiveBrowser'

class ChatResponse(BaseModel):
    message: BackendChatMessage
    chat_id: Optional[str] = None
    plan: Optional[List[Dict[str, Any]]] = None # Added for top-level access during live updates

class RenameChatRequest(BaseModel):
    title: str
    log_id: Optional[str] = None
    success: bool = True

class ToolContextItem(BaseModel):
    tool_name: str
    output: Optional[str] = None

class AdvancedOptions(BaseModel):
    retry_count: int = 3
    timeout: int = 120
    headless: bool = True

class ScheduleRequest(BaseModel):
    chat_id: str
    title: str
    selected_message_ids: List[str]
    selected_tool_ids: List[str]
    schedule_type: str # daily, weekly, monthly
    schedule_time: Optional[str] = "09:00"  # HH:MM 24-hour
    schedule_day_of_week: Optional[str] = "mon"  # mon, tue, wed, thu, fri, sat, sun (used when schedule_type == "weekly")
    timezone: Optional[str] = "America/New_York"  # IANA timezone
    email_recipient: Optional[str] = None
    status: Optional[Literal["active", "draft"]] = "active"
    tool_context: Optional[List[ToolContextItem]] = None
    advanced_options: Optional[AdvancedOptions] = None

class ScheduleResponse(BaseModel):
    schedule_id: str
    status: str
    created_at: datetime

class MessageHistory(BaseModel):
    role: str
    content: str

class ChatHistoryResponse(BaseModel):
    messages: List[BackendChatMessage]
    current_chat_id: Optional[str] = None
    session_state: Dict[str, Any] = {}

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    user_id: str
    chat_id: str
    task_structure: Dict[str, Any]
    retry_count: int
    last_error: str
    atag_summary: str
    atag_prompt: str
    atag_phase: Optional[str]
    atag_form: Optional[Any]

class UserInDB(UserResponse):
    """
    Represents a user stored in the database.
    Inherits from UserResponse and adds the password hash.
    """
    hashed_password: str

    model_config = ConfigDict(from_attributes=True)
