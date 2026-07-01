// api.ts
const TOKEN_KEY = "access_token";
const BASE_URL = "";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function handleUnauthorized() {
  setStoredToken(null);
  if (typeof window !== "undefined") {
    window.location.reload();
  }
}

export const sciparserApi = {
  // Auth
  signup: async (username: string, email: string, password: string) => {
    const res = await fetch(`${BASE_URL}/sciparser/v1/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(errorText || "Signup failed");
    }
    return res.json();
  },

  signin: async (username: string, password: string) => {
    const res = await fetch(`${BASE_URL}/sciparser/v1/signin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(errorText || "Signin failed");
    }
    return res.json();
  },

  getMe: async (): Promise<User> => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    
    console.log("Fetching user profile with token:", token.substring(0, 20) + "...");
    
    const response = await fetch(`${BASE_URL}/sciparser/v1/me`, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
    
    console.log("GetMe response status:", response.status);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("GetMe failed with status:", response.status, errorData);
      throw new Error(errorData.detail || `Failed to fetch user profile: ${response.status}`);
    }
    
    return response.json();
  },

  // Chat Sessions
  getChatSessions: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  renameChatSession: async (chatId: string, title: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/rename`, {
      method: "PATCH",
      headers: {
        "Authorization": formattedToken,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getChatHistory: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    // Backend expects chat_id as a query parameter: ?chat_id=...
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/history?chat_id=${chatId}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // NEW: Get thread messages (Backend uses the history endpoint for this)
  getThreadMessages: async (threadId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    // Use the history endpoint with query param
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/history?chat_id=${threadId}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Chat Messages
  sendChatMessage: async (
    message: string,
    attachments: UploadedFile[],
    preferLiveBrowser: boolean,
    chatId?: string
  ) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    // FIX: Convert attachments to file paths for backend compatibility
    const files = attachments.map(file => file.id || file.name);
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify({
        message,
        files,  // FIX: Changed from 'attachments' to 'files'
        preferLiveBrowser,
        chat_id: chatId,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // File Upload
  uploadFileMetadata: async (fileName: string, fileSize: number, fileType: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/upload/metadata`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify({ fileName, fileSize, fileType }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  stopChatProcess: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/stop?chat_id=${chatId}`, {
      method: "POST",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getUploadedFiles: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/upload/files`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Browser State
  toggleBrowserState: async (chatId: string, isActive: boolean) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/state`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify({ chat_id: chatId, is_active: isActive }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  closeBrowser: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/close`, {
      method: "POST",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  checkBrowserSession: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/check`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Scheduler
  createSchedule: async (data: any) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getSchedules: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/list`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  deleteSchedule: async (scheduleId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  updateSchedule: async (scheduleId: string, data: any) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  runSchedule: async (scheduleId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}/run`, {
      method: "POST",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getScheduleRuns: async (scheduleId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}/runs`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Chat Session Management
  deleteChatSession: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    // Backend uses plural 'sessions' in the path
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Agent Status
  getAgentHistory: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/logs`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getAgentTools: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/tools`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getAgentStatus: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw new Error("No access token found");
    }
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/check`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // NEW: Get Agent Execution Logs
  getAgentExecutionLogs: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/logs`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // NEW: Get Tool Execution Logs
  getToolExecutionLogs: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/tools`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Logout
  logout: () => {
    localStorage.removeItem("access_token");
  },
};

export interface ChatMessage {
  form: any;
  id: string;
  role: "user" | "assistant" | "human" | "ai";
  content: string;
  timestamp: string;
  plan?: any[];
  screenshots?: string[];
}

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: string;
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface AgentStage {
  id: string;
  chat_id: string;
  user_id: string;
  agent_stage: string;
  stage_name: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  status: string;
  error_message?: string;
  created_at: string;
}

export interface ToolExecution {
  id: string;
  chat_id: string;
  agent_id: string;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output: Record<string, any>;
  status: string;
  error_message?: string;
  created_at: string;
}
