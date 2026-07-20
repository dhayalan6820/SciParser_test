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
    credit_balance: float = 5.0
    created_at: datetime 
    updated_at: datetime 

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 style


class AdminUpdateUserRequest(BaseModel):
    role: Optional[Literal["admin", "user"]] = None
    status: Optional[Literal["active", "suspended"]] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class AdminSetCreditsRequest(BaseModel):
    """Either set an absolute balance or apply a +/- delta (exactly one)."""
    credits: Optional[float] = None
    delta: Optional[float] = None


class LlmProviderRequest(BaseModel):
    """Set or update a custom LLM provider for the current user."""
    provider: Literal["openrouter", "groq", "nvidia", "ollama"]
    model: str
    api_key: str
    base_url: Optional[str] = None


class LlmProviderResponse(BaseModel):
    """Return the current user's LLM provider config with the API key masked."""
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key_masked: Optional[str] = None
    base_url: Optional[str] = None
    active: bool = False


class ConversationTokenUsage(BaseModel):
    chat_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


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
    total_cost: float = 0.0
    is_running: bool = False


class AdminUserListItem(UserResponse):
    """UserResponse plus lightweight per-user analytics for the admin Users table."""
    last_active: Optional[datetime] = None
    total_runs: int = 0
    success_rate: float = 0.0
    total_cost: float = 0.0
    automation_count: int = 0


class AdminUserListResponse(BaseModel):
    users: List[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminUserAnalyticsUsagePoint(BaseModel):
    date: str
    tokens: int
    cost: float


class AdminUserAnalyticsActivity(BaseModel):
    last_active: Optional[datetime] = None
    total_sessions: int = 0
    total_messages: int = 0
    recent_logins: List[Dict[str, Any]] = []


class AdminUserAnalyticsAutomations(BaseModel):
    total: int = 0
    active: int = 0
    success_rate: float = 0.0
    items: List[AdminAutomationSummary] = []


class AdminUserAnalyticsResponse(BaseModel):
    """Full drill-down analytics for a single user, covering usage/cost, success rate,
    activity, and automation usage — all computed from real recorded data."""
    user_id: str
    username: str
    email: str
    days: int
    total_tokens: int
    total_cost: float
    total_runs: int
    success_count: int
    failed_count: int
    success_rate: float
    daily_usage: List[AdminUserAnalyticsUsagePoint]
    status_breakdown: List[Dict[str, Any]]
    activity: AdminUserAnalyticsActivity
    automations: AdminUserAnalyticsAutomations
    credit_balance: float = 0.0
    conversations: List[ConversationTokenUsage] = []
    model_breakdown: List[Dict[str, Any]] = []
    recent_runs: List[Dict[str, Any]] = []


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
    user_id: Optional[str] = None
    username: Optional[str] = None


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


class AdminAutomationsResponse(BaseModel):
    automations: List[AdminAutomationSummary]
    total: int


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
    recent_logins: List[Dict[str, Any]]
    failed_logins: List[Dict[str, Any]]


class AdminAgentRunTimelineResponse(BaseModel):
    chat_id: str
    stages: List[Dict[str, Any]]


class AdminAgentActionResponse(BaseModel):
    chat_id: str
    action: str
    success: bool
    detail: Optional[str] = None


class AdminAnalyticsResponse(BaseModel):
    """Unified analytics data for the Analytics section, covering runs, success/error rate,
    token consumption, and browser session volume over a selectable date range."""
    days: int
    daily_runs: List[Dict[str, Any]]
    daily_tokens: List[Dict[str, Any]]
    daily_sessions: List[Dict[str, Any]]
    total_runs: int
    total_success: int
    total_failed: int
    overall_success_rate: float


class OperationsLogEntry(BaseModel):
    id: str
    chat_id: str
    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    agent_stage: str
    stage_name: str
    status: str
    error_message: Optional[str] = None
    tokens: int
    cost: float
    created_at: str


class OperationsLogListResponse(BaseModel):
    logs: List[OperationsLogEntry]
    total: int
    page: int
    page_size: int

class AppLogEntry(BaseModel):
    id: int
    timestamp: str
    level: str
    logger_name: str
    message: str
    module: Optional[str] = None
    func_name: Optional[str] = None
    line_no: Optional[int] = None


class AppLogListResponse(BaseModel):
    logs: List[AppLogEntry]
    total: int
    page: int
    page_size: int


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


# --- New Enterprise Admin Portal Schemas ---

class AdminCostBreakdownPoint(BaseModel):
    category: str
    cost: float

class AdminCostAnalyticsResponse(BaseModel):
    total_cost: float
    breakdown: List[AdminCostBreakdownPoint]
    daily_trends: List[Dict[str, Any]]

class AdminModelMetricsItem(BaseModel):
    model_name: str
    requests: int
    success_rate: float
    avg_latency_ms: float
    avg_tokens: float
    avg_cost: float
    failure_rate: float

class AdminModelAnalyticsResponse(BaseModel):
    models: List[AdminModelMetricsItem]

class AdminToolMetricsItem(BaseModel):
    tool_name: str
    usage_count: int
    success_rate: float
    failure_rate: float
    avg_latency_ms: float

class AdminToolAnalyticsResponse(BaseModel):
    tools: List[AdminToolMetricsItem]

class AdminBrowserAnalyticsResponse(BaseModel):
    total_sessions: int
    pages_visited: int
    avg_load_time_ms: float
    actions_breakdown: Dict[str, int]

class AdminContextAnalyticsResponse(BaseModel):
    avg_prompt_size_tokens: float
    avg_memory_size_tokens: float
    summarization_events: int
    window_utilization_percent: float

class AdminRetrievalAnalyticsResponse(BaseModel):
    embedding_calls: int
    embedding_cost: float
    vector_searches: int
    avg_recall: float
    avg_precision: float

class AdminResourceSnapshot(BaseModel):
    cpu_percent: float
    ram_percent: float
    active_websockets: int
    active_browser_instances: int
    db_size_bytes: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class AdminResourcesResponse(BaseModel):
    current: AdminResourceSnapshot
    history: List[AdminResourceSnapshot]

class AdminSetBudgetRequest(BaseModel):
    user_id: str
    daily_budget: Optional[float] = None
    monthly_budget: Optional[float] = None
    action_at_100: Optional[str] = "switch_cheaper_model"

class AdminAlertNotificationItem(BaseModel):
    id: str
    severity: str
    category: str
    title: str
    message: str
    resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AdminAlertsResponse(BaseModel):
    alerts: List[AdminAlertNotificationItem]

class AdminGenerateInsightsResponse(BaseModel):
    recommendations: List[str]
    analysis_timestamp: datetime


# Observability API response schemas
class ObservabilityOverviewResponse(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cached_tokens: int
    total_cost: float
    total_runs: int
    total_tool_calls: int
    overall_success_rate: float
    avg_latency_ms: float
    daily_trends: List[Dict[str, Any]]
    active_alerts: List[Dict[str, Any]]

class ObservabilityUsersResponse(BaseModel):
    users: List[Dict[str, Any]]
    total: int

class ObservabilityConversationsResponse(BaseModel):
    conversations: List[Dict[str, Any]]
    total: int

class ObservabilityLLMResponse(BaseModel):
    providers: List[Dict[str, Any]]
    models: List[Dict[str, Any]]

class ObservabilityAgentsToolsResponse(BaseModel):
    agents: List[Dict[str, Any]]
    tools: List[Dict[str, Any]]
    mcp_servers: List[Dict[str, Any]]

class ObservabilityCacheMemoryResponse(BaseModel):
    prompt_cache_hit_rate: float
    embedding_cache_hit_rate: float
    saved_tokens: int
    saved_cost_usd: float
    memory_reads: int
    memory_writes: int
    semantic_hits: int
    cache_hits: int
    cache_misses: int
    vector_searches: int
    embedding_calls: int

class ObservabilityPerformanceErrorsResponse(BaseModel):
    avg_latency: float
    median_latency: float
    p90_latency: float
    p95_latency: float
    p99_latency: float
    queue_time_avg: float
    inference_time_avg: float
    tool_time_avg: float
    browser_time_avg: float
    memory_time_avg: float
    recent_errors: List[Dict[str, Any]]

class ObservabilityWaterfallStage(BaseModel):
    id: str
    name: str
    stage_type: str  # "agent" | "tool" | "llm"
    status: str
    duration_ms: int
    tokens: int
    cost: float
    started_at: datetime
    error_message: Optional[str] = None

class ObservabilityWaterfallResponse(BaseModel):
    chat_id: str
    title: str
    total_duration_ms: int
    total_cost: float
    total_tokens: int
    stages: List[ObservabilityWaterfallStage]


class ObservabilityErrorsListResponse(BaseModel):
    errors: List[Dict[str, Any]]
    total: int
    aggregates: Dict[str, Any]

