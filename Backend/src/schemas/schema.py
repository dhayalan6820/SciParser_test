from datetime import datetime
from typing import List, TypedDict, Annotated, Sequence, Dict, Any, Optional
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
    created_at: datetime 
    updated_at: datetime 

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 style

class BackendChatMessage(BaseModel):
    id: Optional[str] = None # Added to match frontend 'id'
    log_id: Optional[str] = None # Changed to Optional to prevent validation failure
    role: str
    content: str
    timestamp: str
    plan: Optional[List[Dict[str, Any]]] = None # Added to support saving the agent process
    form: Optional[Dict[str, Any]] = None # Added to support dynamic forms for NEEDS_INPUT status

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

class ScheduleRequest(BaseModel):
    chat_id: str
    title: str
    selected_message_ids: List[str]
    selected_tool_ids: List[str]
    schedule_type: str # daily, weekly, monthly
    email_recipient: str

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
