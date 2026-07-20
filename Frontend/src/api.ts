// api.ts
import { API_BASE_URL } from "./config";

const TOKEN_KEY = "access_token";
const BASE_URL = API_BASE_URL;

// Intercept global fetch to catch errors and display toast notifications, and automatically bypass ngrok warning pages
if (typeof window !== "undefined") {
  const originalFetch = window.fetch;
  window.fetch = async (input, init) => {
    let finalInput = input;
    let finalInit = init;

    const targetUrl =
      typeof input === "string"
        ? input
        : (input && typeof input === "object" && "url" in input)
          ? (input as any).url
          : input?.toString() || "";

    if (targetUrl && (targetUrl.includes("ngrok") || targetUrl.includes("ngrok-free.dev"))) {
      if (typeof input === "string" || (input && typeof input === "object" && "toString" in input && !(input instanceof Request))) {
        finalInit = finalInit || {};
        const headers = new Headers(finalInit.headers || {});
        headers.set("ngrok-skip-browser-warning", "true");
        finalInit.headers = headers;
      } else if (input instanceof Request) {
        try {
          const newHeaders = new Headers(input.headers);
          newHeaders.set("ngrok-skip-browser-warning", "true");
          finalInput = new Request(input, { headers: newHeaders });
        } catch (e) {
          try {
            input.headers.set("ngrok-skip-browser-warning", "true");
          } catch (err) {}
        }
      }
    }

    try {
      const response = await originalFetch(finalInput, finalInit);
      if (!response.ok) {
        const clone = response.clone();
        try {
          const body = await clone.json();
          if (body && body.success === false && body.error) {
            const err = body.error;
            const { toast } = await import("./components/ui/toast-notifications");
            toast(err.severity || "error", err.title || "Request Failed", err.message, err.id);
          }
        } catch {
          if (response.status === 401) {
            handleUnauthorized();
          }
        }
      }
      return response;
    } catch (err) {
      const { toast } = await import("./components/ui/toast-notifications");
      toast("error", "Connection Failed", "A connection error occurred. Please check your internet connection.");
      throw err;
    }
  };
}

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

const SUSPENSION_MESSAGE_KEY = "suspension_message";

// Task #130: called when an *already open* websocket (chat plan stream, browser
// stream, schedule monitor) is closed mid-session because the account was just
// suspended by an admin. We stash the reason so the login screen can surface a
// clear "account suspended" message instead of a silent logout / generic error,
// then reload so the whole app resets to its logged-out state.
export function handleSuspendedSession(detail?: string) {
  setStoredToken(null);
  if (typeof window !== "undefined") {
    try {
      sessionStorage.setItem(
        SUSPENSION_MESSAGE_KEY,
        detail || "Your account has been suspended. Please contact an administrator.",
      );
    } catch {
      /* sessionStorage unavailable — the reload will still log the user out */
    }
    window.location.reload();
  }
}

export function consumeSuspensionMessage(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const msg = sessionStorage.getItem(SUSPENSION_MESSAGE_KEY);
    if (msg) sessionStorage.removeItem(SUSPENSION_MESSAGE_KEY);
    return msg;
  } catch {
    return null;
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
      const errorData = await res.json().catch(() => null);
      throw new Error(errorData?.detail || "Signup failed");
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
      const errorData = await res.json().catch(() => null);
      // Surface the backend's specific reason (e.g. "Your account has been
      // suspended...") instead of a generic message, so suspended users
      // understand what happened rather than seeing a plain auth failure.
      throw new Error(errorData?.detail || "Signin failed");
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
    return res.json() as Promise<ChatSessionSummary[]>;
  },

  // Task #146: the current user's total token usage/cost across all conversations + credits.
  getMyUsage: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/usage`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<UserTotalUsage>;
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

  updateMessageScreenshots: async (messageId: string, screenshots: string[]) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/messages/${messageId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: formattedToken,
      },
      body: JSON.stringify({ screenshots }),
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

  resetSessionState: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/sessions/${chatId}/reset-session`, {
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

  activateSchedule: async (scheduleId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}/activate`, {
      method: "POST",
      headers: { Authorization: formattedToken },
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

  stopSchedule: async (scheduleId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/sciparser/v1/scheduler/${scheduleId}/stop`, {
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

  // CDP (Connect Your Browser)
  connectCdp: async (cdpUrl: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/connect-cdp`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ cdp_url: cdpUrl }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to connect CDP");
    }
    return res.json();
  },

  disconnectCdp: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/connect-cdp`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getCdpStatus: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/browser/cdp-status`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ connected: boolean; cdp_url: string | null }>;
  },

  // Residential Proxy
  setProxy: async (proxyUrl: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/proxy`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ proxy_url: proxyUrl }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to save proxy");
    }
    return res.json();
  },

  deleteProxy: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/proxy`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getProxyStatus: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/proxy`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ active: boolean; proxy_url_masked: string | null }>;
  },

  testProxy: async (proxyUrl?: string, testUrl?: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/proxy/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ proxy_url: proxyUrl || "", test_url: testUrl || "" }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Proxy test failed");
    }
    return res.json() as Promise<{ status: string; exit_ip: string; tested_url?: string }>;
  },

  // Browser Engine
  getBrowserEngine: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/browser-engine`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ engine: string }>;
  },

  setBrowserEngine: async (engine: "camoufox" | "chrome") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/browser-engine`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ engine }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || "Failed to save browser engine");
    }
    return res.json() as Promise<{ status: string; engine: string }>;
  },

  // LLM Provider (admin only)
  getLlmProvider: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/llm-provider`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load LLM provider settings");
    }
    return res.json() as Promise<{ provider: string | null; model: string | null; api_key_masked: string | null; base_url: string | null; active: boolean }>;
  },

  setLlmProvider: async (provider: string, model: string, apiKey: string, baseUrl?: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/llm-provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ provider, model, api_key: apiKey, base_url: baseUrl || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to save LLM provider");
    }
    return res.json() as Promise<{ provider: string; model: string; api_key_masked: string; base_url: string | null; active: boolean }>;
  },

  deleteLlmProvider: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/llm-provider`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to remove LLM provider");
    }
    return res.json() as Promise<{ status: string }>;
  },

  testLlmProvider: async (provider: string, model: string, apiKey: string, baseUrl?: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/settings/llm-provider/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify({ provider, model, api_key: apiKey, base_url: baseUrl || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "LLM provider test failed");
    }
    return res.json() as Promise<{ status: string; provider: string; model: string; base_url: string }>;
  },

  // Logout
  logout: () => {
    localStorage.removeItem("access_token");
  },

  // Admin: User Management
  adminListUsers: async (page: number = 1, pageSize: number = 20, search?: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set("search", search);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ users: User[]; total: number; page: number; page_size: number }>;
  },

  adminUpdateUser: async (
    userId: string,
    data: Partial<{
      role: "admin" | "user";
      status: "active" | "suspended";
      username: string;
      email: string;
    }>
  ) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || "Failed to update user");
    }
    return res.json() as Promise<User>;
  },

  adminGetUser: async (userId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users/${userId}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<User>;
  },

  adminGetUserAnalytics: async (userId: string, days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users/${userId}/analytics?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminUserAnalytics>;
  },

  adminSetUserCredits: async (userId: string, data: { credits?: number; delta?: number }) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users/${userId}/credits`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: formattedToken },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || "Failed to update credits");
    }
    return res.json() as Promise<User>;
  },

  getMyConversationUsage: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/chat/usage/conversations`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<ConversationTokenUsage[]>;
  },

  getMyUserAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/user/analytics?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminUserAnalytics>;
  },

  adminDeleteUser: async (userId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/users/${userId}`, {
      method: "DELETE",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || "Failed to delete user");
    }
    return res.json();
  },

  // Admin: Operations Metrics
  adminGetOperationsMetrics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/metrics/operations?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<OperationsMetrics>;
  },

  // Admin: Overview KPIs
  adminGetOverviewMetrics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/metrics/overview?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminOverview>;
  },

  // Admin: Recent Activity
  adminGetActivity: async (
    limit: number = 20,
    filters?: { startDate?: string; endDate?: string; type?: string; user?: string }
  ) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters?.startDate) params.set("start_date", filters.startDate);
    if (filters?.endDate) params.set("end_date", filters.endDate);
    if (filters?.type) params.set("type", filters.type);
    if (filters?.user) params.set("user", filters.user);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/activity?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ items: AdminActivityItem[] }>;
  },

  // Admin: Agent Monitoring
  adminGetAgentRuns: async (
    page: number = 1,
    pageSize: number = 20,
    status?: string,
    search?: string,
    sortBy?: string,
    sortDir?: string
  ) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    if (sortBy) params.set("sort_by", sortBy);
    if (sortDir) params.set("sort_dir", sortDir);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/agents?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminAgentRunsResponse>;
  },

  adminGetAgentRunTimeline: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/agents/${encodeURIComponent(chatId)}/timeline`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminAgentRunTimeline>;
  },

  adminCancelAgentRun: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/agents/${encodeURIComponent(chatId)}/cancel`, {
      method: "POST",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ chat_id: string; action: string; success: boolean; detail?: string | null }>;
  },

  // Admin: Automation Monitoring
  adminGetAutomations: async (
    page: number = 1,
    pageSize: number = 20,
    search?: string,
    sortBy?: string,
    sortDir?: string
  ) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set("search", search);
    if (sortBy) params.set("sort_by", sortBy);
    if (sortDir) params.set("sort_dir", sortDir);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/automations?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ automations: AdminAutomation[]; total: number }>;
  },

  // Admin: Unified Analytics
  adminGetAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminAnalytics>;
  },

  // Admin: Browser Sessions
  adminGetBrowserSessions: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/browser-sessions`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ sessions: AdminBrowserSession[]; active_count: number }>;
  },

  // Admin: Usage Dashboard
  adminGetUsage: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/usage?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminUsage>;
  },

  // Admin: Security Overview
  adminGetSecurity: async (filters?: { startDate?: string; endDate?: string; user?: string; status?: string }) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams();
    if (filters?.startDate) params.set("start_date", filters.startDate);
    if (filters?.endDate) params.set("end_date", filters.endDate);
    if (filters?.user) params.set("user", filters.user);
    if (filters?.status) params.set("status", filters.status);
    const qs = params.toString();
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/security${qs ? `?${qs}` : ""}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AdminSecurity>;
  },

  adminGetCostAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/costs?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetModelAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/models?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetToolAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/tools?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetBrowserAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/browser?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetContextAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/context?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetRetrievalAnalytics: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/retrieval?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetResourceSnapshots: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/analytics/resources`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminSetBudget: async (userId: string, dailyBudget?: number, monthlyBudget?: number, actionAt100: string = "switch_cheaper_model") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/cost-control/budgets`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        Authorization: formattedToken 
      },
      body: JSON.stringify({
        user_id: userId,
        daily_budget: dailyBudget,
        monthly_budget: monthlyBudget,
        action_at_100: actionAt100
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGetAlerts: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/alerts`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminGenerateInsights: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/insights/generate`, {
      method: "POST",
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  adminDownloadReport: async (format: "csv" | "json" | "md", days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/reports/download?format=${format}&days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename=([^;]+)/);
    const filename = match ? match[1].trim() : `platform_report.${format}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },

  // Observability Platform API calls
  observabilityGetOverview: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/overview?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetUsers: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/users?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetConversations: async (days: number = 30, page: number = 1, limit: number = 10, search: string = "", status: string = "", userId: string = "") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({
      days: days.toString(),
      page: page.toString(),
      limit: limit.toString(),
      search,
      status,
      user_id: userId,
    });
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/conversations?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetLLM: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/llm?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetAgentsTools: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/agents-tools?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetCacheMemory: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/cache-memory?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetPerformanceErrors: async (days: number = 30) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/performance-errors?days=${days}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetWaterfall: async (chatId: string) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/conversations/${chatId}/waterfall`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  observabilityGetErrors: async (days: number = 30, page: number = 1, limit: number = 10, search: string = "", severity: string = "", category: string = "") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = new URLSearchParams({
      days: days.toString(),
      page: page.toString(),
      limit: limit.toString(),
      search,
      severity,
      category,
    });
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/observability/errors?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ errors: any[]; total: number; aggregates: any }>;
  },


  // Admin: Application Logs (info/warning/error lines)
  adminGetAppLogs: async (filters: AppLogFilters) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = buildAppLogParams(filters);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/logs?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<AppLogListResponse>;
  },

  adminExportAppLogs: async (filters: AppLogFilters, format: "csv" | "json") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = buildAppLogParams(filters);
    params.set("format", format);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/logs/export?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename=([^;]+)/);
    const filename = match ? match[1].trim() : `app_logs_export.${format}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },

  // Admin: Operations Logs (filter/audit)
  adminGetOperationsLogs: async (filters: OperationsLogFilters) => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = buildOperationsLogParams(filters);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/operations/logs?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<OperationsLogListResponse>;
  },

  adminExportOperationsLogs: async (filters: OperationsLogFilters, format: "csv" | "json") => {
    const token = localStorage.getItem("access_token");
    if (!token) throw new Error("No access token found");
    const formattedToken = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
    const params = buildOperationsLogParams(filters);
    params.set("format", format);
    const res = await fetch(`${BASE_URL}/sciparser/v1/admin/operations/export?${params.toString()}`, {
      headers: { Authorization: formattedToken },
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename=([^;]+)/);
    const filename = match ? match[1].trim() : `operations_export.${format}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};

function buildAppLogParams(filters: AppLogFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  if (filters.level) params.set("level", filters.level);
  if (filters.search) params.set("search", filters.search);
  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  return params;
}

function buildOperationsLogParams(filters: OperationsLogFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  if (filters.username) params.set("username", filters.username);
  if (filters.userId) params.set("user_id", filters.userId);
  if (filters.status) params.set("status", filters.status);
  if (filters.agentStage) params.set("agent_stage", filters.agentStage);
  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  return params;
}

export interface ChatMessage {
  form: any;
  id: string;
  role: "user" | "assistant" | "human" | "ai";
  content: string;
  timestamp: string;
  plan?: any[];
  screenshots?: string[];
  tool_calls?: Array<{
    id: string;
    tool_name: string;
    tool_input?: Record<string, any>;
    tool_output?: string;
    status?: string;
    created_at?: string;
  }>;
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
  role: "admin" | "user";
  status: "active" | "suspended";
  created_at: string;
  updated_at: string;
  last_active?: string | null;
  total_runs?: number;
  success_rate?: number;
  total_cost?: number;
  automation_count?: number;
  credit_balance?: number;
}

export interface ConversationTokenUsage {
  chat_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
}

export interface UserTotalUsage {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  credit_balance: number;
}

export interface AdminUserAnalytics {
  user_id: string;
  username: string;
  email: string;
  days: number;
  total_tokens: number;
  total_cost: number;
  total_runs: number;
  success_count: number;
  failed_count: number;
  success_rate: number;
  daily_usage: Array<{ date: string; tokens: number; cost: number }>;
  status_breakdown: Array<{ status: string; count: number }>;
  activity: {
    last_active?: string | null;
    total_sessions: number;
    total_messages: number;
    recent_logins: Array<{ created_at: string | null }>;
  };
  automations: {
    total: number;
    active: number;
    success_rate: number;
    items: AdminAutomation[];
  };
  credit_balance: number;
  conversations: ConversationTokenUsage[];
  model_breakdown?: Array<{
    model: string;
    requests: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    avg_latency: number;
  }>;
  recent_runs?: Array<{
    id: string;
    chat_id: string;
    agent_stage: string;
    stage_name: string;
    status: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost: number;
    error_message?: string | null;
    created_at?: string | null;
  }>;
}

export interface OperationsMetrics {
  total_runs: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  total_tokens: number;
  total_cost: number;
  daily_trends: Array<{
    date: string;
    runs: number;
    success: number;
    failure: number;
    tokens: number;
    cost: number;
  }>;
  top_errors: Array<{ error: string; count: number }>;
  status_breakdown: Array<{ status: string; count: number }>;
}

export interface AdminOverview {
  total_users: number;
  active_users: number;
  running_agents: number;
  completed_automations: number;
  success_rate: number;
  success_rate_change: number;
  total_tokens: number;
  total_tokens_change: number;
  total_cost: number;
  total_cost_change: number;
  total_runs: number;
  total_runs_change: number;
  runs_sparkline: number[];
  tokens_sparkline: number[];
}

export interface AdminActivityItem {
  type: string;
  title: string;
  detail?: string | null;
  status?: string | null;
  timestamp: string;
  user_id?: string | null;
  username?: string | null;
}

export interface AdminAgentRun {
  id: string;
  chat_id: string;
  user_id: string;
  stage_name: string;
  status: string;
  tokens: number;
  cost: number;
  error_message?: string | null;
  created_at: string;
}

export interface AdminAgentRunsResponse {
  runs: AdminAgentRun[];
  total: number;
  running_count: number;
  queued_count: number;
  failed_count: number;
  completed_count: number;
  avg_runtime_seconds: number;
}

export interface AdminAutomation {
  schedule_id: string;
  title?: string | null;
  status: string;
  schedule_type: string;
  last_run?: string | null;
  next_run?: string | null;
  total_runs: number;
  success_runs: number;
  failed_runs: number;
  success_rate: number;
  total_cost: number;
  is_running: boolean;
}

export interface AdminBrowserSession {
  user_id: string;
  username?: string | null;
  active_chat_count: number;
  browser_active: boolean;
  browser_engine?: string | null;
  proxy_configured: boolean;
}

export interface AdminUsage {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  daily_usage: Array<{ date: string; prompt_tokens: number; completion_tokens: number }>;
  top_users: Array<{ user_id: string; username: string; tokens: number; cost: number; runs: number }>;
}

export interface AdminSecurity {
  suspended_users: Array<{ user_id: string; username: string; email: string; updated_at: string | null }>;
  recent_signups: Array<{ user_id: string; username: string; email: string; created_at: string | null; role: string; status: string }>;
  recent_logins: Array<{ user_id: string | null; username: string; created_at: string | null }>;
  failed_logins: Array<{ username: string; reason: string | null; created_at: string | null }>;
}

export interface AdminAgentRunTimeline {
  chat_id: string;
  stages: Array<{
    id: string;
    agent_stage: string;
    stage_name: string;
    status: string;
    tokens: number;
    cost: number;
    error_message?: string | null;
    created_at: string;
    updated_at: string;
  }>;
}

export interface AdminAnalytics {
  days: number;
  daily_runs: Array<{ date: string; total: number; success: number; failed: number }>;
  daily_tokens: Array<{ date: string; tokens: number }>;
  daily_sessions: Array<{ date: string; sessions: number }>;
  total_runs: number;
  total_success: number;
  total_failed: number;
  overall_success_rate: number;
}
export interface AppLogFilters {
  page?: number;
  pageSize?: number;
  level?: string;
  search?: string;
  startDate?: string;
  endDate?: string;
}

export interface AppLogEntry {
  id: number;
  timestamp: string;
  level: string;
  logger_name: string;
  message: string;
  module: string | null;
  func_name: string | null;
  line_no: number | null;
}

export interface AppLogListResponse {
  logs: AppLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface OperationsLogFilters {
  page?: number;
  pageSize?: number;
  userId?: string;
  username?: string;
  status?: string;
  agentStage?: string;
  startDate?: string;
  endDate?: string;
}

export interface OperationsLogEntry {
  id: string;
  chat_id: string;
  user_id: string;
  username: string | null;
  email: string | null;
  agent_stage: string;
  stage_name: string;
  status: string;
  error_message: string | null;
  tokens: number;
  cost: number;
  created_at: string;
}

export interface OperationsLogListResponse {
  logs: OperationsLogEntry[];
  total: number;
  page: number;
  page_size: number;
}
