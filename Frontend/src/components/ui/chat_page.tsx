// ChatPage.tsx
import * as React from "react";
import { Signup1 } from "./signup-1";
import { Button } from "./button";
import { sciparserApi, ChatMessage, UploadedFile, User } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { Component as AiLoader } from "./ai-loader";
import { MessageLoading } from "./message-loading";
import { BrowserPreview } from "./browser-preview";
import { SchedulesPage } from "./schedules-page";
import { ProcessingPanel } from "./processing-panel";
import { PremiumScheduler } from "./premium-scheduler";
import { 
  Sparkles, User2, Database, RefreshCw, CheckCircle2, 
  BookOpen, MessageSquare, Plus, LogOut, Trash, Pencil, Check, Menu, X, 
  ChevronDown, Globe, Send, PanelLeftClose, PanelLeftOpen, Search, Code, Terminal,
  Sun, Moon, FileText, Paperclip, X as XIcon,
  Loader2, Download, Table as TableIcon, Calendar, Clock
} from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import Plan, { Task } from "./agent-plan";

import { AnimatePresence, motion } from "framer-motion";

interface ChatPageProps {
  onLoginStateChange?: (isLoggedIn: boolean) => void;
}

interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  created_at: string;
  updated_at: string;
}

interface Thread {
  id: string;
  title: string;
  messages: ChatMessage[];
  uploads: UploadedFile[];
  createdAt: string;
}

const ChatPage = ({ onLoginStateChange }: ChatPageProps) => {
  const { theme, toggleTheme } = useTheme();
  const [userProfile, setUserProfile] = React.useState<UserProfile | null>(null);
  const [isNavigating, setIsNavigating] = React.useState(false);
  const [loaderText, setLoaderText] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState("");
  const [isLoginMode, setIsLoginMode] = React.useState(true);
  const [textareaValue, setTextareaValue] = React.useState("");
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [uploads, setUploads] = React.useState<UploadedFile[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = React.useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);
  const [isMobile, setIsMobile] = React.useState(() => window.innerWidth < 768);
  const [threads, setThreads] = React.useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = React.useState<string | undefined>(undefined);
  const [browserActive, setBrowserActive] = React.useState(false);
  const [browserFrame, setBrowserFrame] = React.useState<string | null>(null);
  const [lastManualToggle, setLastManualToggle] = React.useState<number>(0);
  const [browserBlink, setBrowserBlink] = React.useState<"green" | "red" | null>(null);
  const [userInterruptedBrowser, setUserInterruptedBrowser] = React.useState(false);
  const isFirstFrame = React.useRef<boolean>(true);
  
  const [showBrowserPreview, setShowBrowserPreview] = React.useState(false);
  const [preferLiveBrowser, setPreferLiveBrowser] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [voiceEnabled, setVoiceEnabled] = React.useState(false);
  const [isAiTyping, setIsAiTyping] = React.useState(false);
  const [currentPlan, setCurrentPlan] = React.useState<Task[] | null>(null);
  const [toolLogs, setToolLogs] = React.useState<any[]>([]);
  const [aiThinking, setAiThinking] = React.useState<string | null>(null);
  const [showExecutionPlan, setShowExecutionPlan] = React.useState(true);
  const [userInterruptedHide, setUserInterruptedHide] = React.useState(false);
  const [visiblePlans, setVisiblePlans] = React.useState<Record<string, boolean>>({});
  const [visibleTools, setVisibleTools] = React.useState<Record<string, boolean>>({});

  const [agentHistory, setAgentHistory] = React.useState<any[]>([]);
  const [showHistory, setShowHistory] = React.useState(false);

  const togglePlanVisibility = (msgId: string) => {
    setVisiblePlans(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };

  const toggleToolVisibility = (msgId: string) => {
    setVisibleTools(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };

  const [activeModel, setActiveModel] = React.useState("SciParser AI Core");
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false);
  const [editingThreadId, setEditingThreadId] = React.useState<string | null>(null);
  const [editingTitleText, setEditingTitleText] = React.useState("");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [deletingThreadId, setDeletingThreadId] = React.useState<string | null>(null);
  
  // Navigation State
  const [currentView, setCurrentView] = React.useState<"chat" | "schedules">("chat");
  
  // Scheduler State
  const [isSchedulerOpen, setIsSchedulerOpen] = React.useState(false);
  const [isReviewOpen, setIsReviewOpen] = React.useState(false);
  const [selectedMessages, setSelectedMessages] = React.useState<string[]>([]);
  const [selectedTools, setSelectedToolIds] = React.useState<string[]>([]);
  const [isSelectionMode, setIsSelectionMode] = React.useState(false);
  const [scheduleType, setScheduleType] = React.useState("daily");
  const [emailRecipient, setEmailRecipient] = React.useState("");
  
  // Form Popup State
  const [activeForm, setActiveForm] = React.useState<any>(null);
  const [formData, setFormData] = React.useState<Record<string, string>>({});
  
  // Resizable panel states
  const [browserPanelWidth, setBrowserPanelWidth] = React.useState(50); // percentage
  const [historyPanelWidth, setHistoryPanelWidth] = React.useState(320); // pixels
  
  // File upload states
  const [isDraggingFile, setIsDraggingFile] = React.useState(false);
  const [uploadingFiles, setUploadingFiles] = React.useState<string[]>([]);
  
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const toolLogsScrollRef = React.useRef<HTMLDivElement>(null);
  const browserPanelRef = React.useRef<HTMLDivElement>(null);
  const historyPanelRef = React.useRef<HTMLDivElement>(null);
  const [resizingPanel, setResizingPanel] = React.useState<'browser' | 'history' | null>(null);
  const [isAtBottom, setIsAtBottom] = React.useState(true);

  // Handle tool logs auto-scroll
  const handleToolLogsScroll = () => {
    if (toolLogsScrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = toolLogsScrollRef.current;
      const atBottom = scrollHeight - scrollTop <= clientHeight + 50; // 50px buffer
      setIsAtBottom(atBottom);
    }
  };

  const normalizeJsonValue = (value: any) => {
    if (typeof value === "string") {
      try {
        return JSON.parse(value);
      } catch {
        return value;
      }
    }
    return value;
  };

  const loadExecutionLogs = async (chatId: string) => {
    try {
      const [agentLogsRes, toolLogsRes] = await Promise.all([
        sciparserApi.getAgentExecutionLogs(chatId),
        sciparserApi.getToolExecutionLogs(chatId),
      ]);

      setAgentHistory(agentLogsRes || []);

      // Prefer persisted tool logs when a thread is selected.
      const normalizedTools = (toolLogsRes || []).map((log: any) => ({
        ...log,
        tool_input: normalizeJsonValue(log.tool_input) || {},
        tool_output: normalizeJsonValue(log.tool_output) || {},
      }));
      setToolLogs(normalizedTools);

      // Rehydrate the latest execution plan from the agent log if it exists.
      const latestPlanLog = [...(agentLogsRes || [])].reverse().find((log: any) => {
        const output = normalizeJsonValue(log.output_data);
        return Array.isArray(output) || (output && typeof output === "object");
      });

      if (latestPlanLog) {
        const output = normalizeJsonValue(latestPlanLog.output_data);
        if (Array.isArray(output)) {
          setCurrentPlan(output as Task[]);
        }
      }
    } catch (err) {
      console.warn("Failed to load execution logs:", err);
    }
  };

  React.useEffect(() => {
    if (isAtBottom && toolLogsScrollRef.current) {
      toolLogsScrollRef.current.scrollTo({
        top: toolLogsScrollRef.current.scrollHeight,
        behavior: "smooth"
      });
    }
  }, [toolLogs, aiThinking, isAtBottom]);

  // File handling functions
  const handleFileDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingFile(false);
    
    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      setUploadingFiles(prev => [...prev, file.name]);
      await handleFileUploaded(file.name, file.size, file.type);
      setUploadingFiles(prev => prev.filter(name => name !== file.name));
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      for (const file of files) {
        setUploadingFiles(prev => [...prev, file.name]);
        await handleFileUploaded(file.name, file.size, file.type);
        setUploadingFiles(prev => prev.filter(name => name !== file.name));
      }
    }
  };

  // Resizable panel handlers
  const handleBrowserResizeStart = (e: React.MouseEvent) => {
    setResizingPanel('browser');
    e.preventDefault();
  };

  const handleHistoryResizeStart = (e: React.MouseEvent) => {
    setResizingPanel('history');
    e.preventDefault();
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingPanel) return;
      
      if (resizingPanel === 'browser' && browserPanelRef.current) {
        const containerRect = browserPanelRef.current.parentElement?.getBoundingClientRect();
        if (!containerRect) return;
        const newWidth = 100 - (((e.clientX - containerRect.left) / containerRect.width) * 100);
        if (newWidth > 10 && newWidth < 90) {
          setBrowserPanelWidth(Math.round(newWidth));
        }
      } else if (resizingPanel === 'history' && historyPanelRef.current) {
        const containerRect = historyPanelRef.current.parentElement?.getBoundingClientRect();
        if (!containerRect) return;
        
        // History panel is on the right of the chat column. 
        // The handle is on the LEFT of the history panel.
        // So width = historyRect.right - mouseX
        const historyRect = historyPanelRef.current.getBoundingClientRect();
        const newWidth = historyRect.right - e.clientX;
        
        if (newWidth > 160 && newWidth < 800) {
          setHistoryPanelWidth(Math.round(newWidth));
        }
      }
    };

    const handleMouseUp = () => {
      setResizingPanel(null);
    };

    if (resizingPanel) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'default';
    };
  }, [resizingPanel]);

  React.useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  React.useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      fetchUserProfile(token).catch(err => {
        console.error("Failed to load user profile:", err);
        localStorage.removeItem("access_token");
      });
    }
  }, []);

  React.useEffect(() => {
    if (scrollRef.current) {
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth"
          });
        }
      });
    }
  }, [messages, isAiTyping, currentPlan, toolLogs]);

  // Real-Time WebSocket stream connection for CDP frame screencasts
  React.useEffect(() => {
    // We want to listen for frames even if browserActive is false to support auto-open
    if (!userProfile?.user_id) return;
    if (!activeThreadId) return;

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/sciparser/v1/browser/stream?chat_id=${activeThreadId}&token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      // Use requestAnimationFrame to batch state updates and prevent UI lag
      requestAnimationFrame(() => {
        try {
          const msg = JSON.parse(event.data);
          const eventType = msg.event || (msg.frame ? 'frame' : null);
          const rawData = msg.data || msg.frame;

          if (eventType === 'frame') {
            // Parse the inner JSON which contains chat_id and frame
            let frameData;
            try {
              frameData = typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
            } catch (e) {
              frameData = { frame: rawData };
            }

            // --- FIX: Route frames by chat_id with fallback ---
            // If the frame doesn't have a chat_id, or if it matches the active thread,
            // or if we only have one active session, we should display it.
            const frameChatId = frameData.chat_id ? String(frameData.chat_id) : null;
            const activeId = activeThreadId ? String(activeThreadId) : null;
            
            if (frameChatId && activeId && frameChatId !== activeId) {
              // Only ignore if both IDs exist and they explicitly mismatch
              return;
            }

            // Extract the actual frame data (handle nested objects or raw strings)
            let actualFrame = frameData.frame;
            if (typeof actualFrame === 'object' && actualFrame !== null) {
              actualFrame = actualFrame.data || actualFrame.text || JSON.stringify(actualFrame);
            }

            if (!actualFrame && typeof rawData === "string") {
              try {
                const parsedRaw = JSON.parse(rawData);
                actualFrame = parsedRaw.frame || parsedRaw.screenshot || parsedRaw.data || parsedRaw.image;
              } catch {
                // ignore parse errors here
              }
            }

            if (actualFrame) {
              setBrowserFrame(actualFrame);
              
              // --- NEW: Auto-open on first frame with green blink ---
              if (isFirstFrame.current && !userInterruptedBrowser) {
                isFirstFrame.current = false;
                setBrowserBlink("green");
                
                // Blink 5 times (approx 2.5s) then open
                setTimeout(() => {
                  if (!userInterruptedBrowser) {
                    setBrowserActive(true);
                    setBrowserBlink(null);
                  }
                }, 2500);
              }
            }
          } else if (eventType === 'tool_log') {
            try {
              // --- FIX: Handle both stringified and object data ---
              const toolMsg = typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
              
              if (toolMsg.type === 'tool_start') {
                setToolLogs(prev => [...prev, {
                  id: toolMsg.tool_call_id || uuidv4(),
                  tool_name: toolMsg.tool,
                  tool_input: toolMsg.args,
                  status: 'IN_PROGRESS',
                  created_at: new Date().toISOString()
                }]);
              } else if (toolMsg.type === 'tool_output') {
                setToolLogs(prev => prev.map(log => 
                  (log.id === toolMsg.tool_call_id) 
                    ? { ...log, status: toolMsg.status, tool_output: toolMsg.output, error_message: toolMsg.error } 
                    : log
                ));
              }
            } catch (e) {
              console.error("Failed to parse tool log data:", e);
            }
          }
        } catch (err) {
          console.error("Failed to parse browser stream message:", err);
        }
      });
    };

    ws.onopen = () => console.log("Browser stream connected for", activeThreadId);
    ws.onclose = () => console.log("Browser stream disconnected");

    return () => ws.close();
  }, [activeThreadId, userProfile?.user_id]);

  // WebSocket for Live Agent Plan (Analysis -> Strategy -> Execution)
  React.useEffect(() => {
    if (!activeThreadId) {
      setCurrentPlan(null);
      return;
    }

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/sciparser/v1/ws/plan/${activeThreadId}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "plan_update") {
          setCurrentPlan(msg.data);
          // If we receive a plan update, it means a task is active
          setIsAiTyping(true);
        } else if (msg.type === "thought_update") {
          setAiThinking(msg.data);
        }
      } catch (err) {
        console.error("Plan stream error:", err);
      }
    };

    return () => ws.close();
  }, [activeThreadId]);

  const adjustHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  };

  const fetchUserProfile = async (token: string) => {
    try {
      localStorage.setItem("access_token", token);
      
      const user = await sciparserApi.getMe();
      
      setUserProfile({
        user_id: user.user_id,
        username: user.username,
        email: user.email,
        created_at: user.created_at,
        updated_at: user.updated_at,
      });
      
      onLoginStateChange?.(true);
      await loadThreadsAndLatestHistory();
    } catch (e) {
      console.error("Failed to fetch user profile:", e);
      localStorage.removeItem("access_token");
      onLoginStateChange?.(false);
    }
  };

  const loadThreadsAndLatestHistory = async () => {
    setIsNavigating(true);
    setLoaderText("Syncing Workspace");
    try {
      const sessions = await sciparserApi.getChatSessions();
      if (!sessions || sessions.length === 0) {
        handleNewChat();
        return;
      }

      const loadedThreads: Thread[] = sessions.map((s: any) => ({
        id: s.id,
        title: s.title || "Untitled Chat",
        messages: [],
        uploads: [],
        createdAt: s.createdAt || new Date().toISOString()
      }));
      
      setThreads(loadedThreads);
      
      const latestThreadId = loadedThreads[0].id;
      setActiveThreadId(latestThreadId);
      
      try {
        const historyData = await sciparserApi.getChatHistory(latestThreadId);
        if (historyData && historyData.messages) {
          setMessages(historyData.messages);
          setThreads(prev => prev.map(t => 
            t.id === latestThreadId ? { ...t, messages: historyData.messages } : t
          ));
        }
        await loadExecutionLogs(latestThreadId);
      } catch (historyErr: any) {
        console.warn(`Could not load history for thread ${latestThreadId}:`, historyErr);
        setMessages([]);
      }
    } catch (e) {
      console.error("Failed to load user threads:", e);
      handleNewChat(); 
    } finally {
      setTimeout(() => setIsNavigating(false), 800);
    }
  };

  const handleAuthSubmit = async (formData: any) => {
    setIsNavigating(true);
    setLoaderText(isLoginMode ? "Authenticating" : "Creating Account");
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      if (isLoginMode) {
        const res = await sciparserApi.signin(formData.username, formData.password);
        if (!res.access_token) {
          throw new Error("No access token received from server");
        }
        
        localStorage.setItem("access_token", res.access_token);
        setSuccess("Successfully authenticated!");
        
        await fetchUserProfile(res.access_token);
        onLoginStateChange?.(true);
        
        setIsNavigating(false);
        setLoading(false);
      } else {
        await sciparserApi.signup(formData.username, formData.email, formData.password);
        setSuccess("Account created successfully! Switching to Login...");
        setTimeout(() => {
          setIsLoginMode(true);
          setSuccess("");
        }, 1500);
      }
    } catch (err: any) {
      console.error("Auth error:", err);
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
      setTimeout(() => setIsNavigating(false), 700);
    }
  };

  const handleLogout = () => {
    setIsNavigating(true);
    setLoaderText("Signing Out");
     
    setTimeout(() => {
      localStorage.removeItem("access_token");
      sciparserApi.logout();
      setUserProfile(null);
      onLoginStateChange?.(false);
      setMessages([]);
      setUploads([]);
      setBrowserActive(false);
      setSuccess("Logged out successfully");
      setError("");
      setIsNavigating(false);
    }, 950);
  };

  const handleSelectThread = async (threadId: string | number) => {
    const idStr = String(threadId);
    
    // If clicking the already active thread, do nothing
    if (idStr === activeThreadId && messages.length > 0) return;

    setIsNavigating(true);
    setLoaderText("Loading Chat");
    setCurrentView("chat"); // Ensure we switch back to chat view
    
    setActiveThreadId(idStr);
    setIsMobileSidebarOpen(false);
    
    try {
      const res = await sciparserApi.getChatHistory(idStr);
      setMessages(res?.messages || []);
      
      await loadExecutionLogs(idStr);
    } catch (e: any) {
      console.error("Failed to load thread data:", e);
      if (e.message?.includes("404") || e.message?.includes("Not Found")) {
        setThreads(prev => prev.filter(t => t.id !== idStr));
        handleNewChat();
      }
    } finally {
      setTimeout(() => setIsNavigating(false), 500);
    }
  };

  const handleDeleteThread = async (threadId: string | number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const idStr = String(threadId);
    
    try {
      setIsNavigating(true);
      setLoaderText("Deleting Chat");

      // 1. Call API to delete from database
      await sciparserApi.deleteChatSession(idStr);

      // 2. Update local state
      const updatedThreads = threads.filter(t => String(t.id) !== idStr);
      setThreads(updatedThreads);
      
      // 3. Handle navigation if the deleted thread was active
      if (String(activeThreadId) === idStr) {
        if (updatedThreads.length > 0) {
          handleSelectThread(updatedThreads[0].id);
        } else {
          handleNewChat();
        }
      }
      
      setDeletingThreadId(null);
      setSuccess("Chat deleted successfully");
    } catch (err) {
      console.error("Delete failed:", err);
      setError("Failed to delete chat");
    } finally {
      setTimeout(() => {
        setIsNavigating(false);
        setSuccess("");
        setError("");
      }, 500);
    }
  };

  const handleNewChat = (force: boolean = false) => {
    // Professional check: Don't create a new chat if the current one is already empty, 
    // unless explicitly forced (e.g. by clicking the '+' button)
    if (!force && messages.length === 0 && activeThreadId && String(activeThreadId).startsWith("thread-")) {
      return;
    }

    const newId = `thread-${uuidv4()}`; 
    const newThread: Thread = {
      id: newId,
      title: "New Chat",
      messages: [],
      uploads: [],
      createdAt: new Date().toISOString(),
    };
    setThreads(prev => [newThread, ...prev]);
    setActiveThreadId(newId);
    setMessages([]);
    setBrowserActive(false);
    setCurrentView("chat");
    setIsMobileSidebarOpen(false);
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    const currentThreadId = activeThreadId ? String(activeThreadId) : uuidv4();
    // ... (rest of the function)
    
    if (!activeThreadId) {
      setActiveThreadId(currentThreadId);
      const newThread: Thread = {
        id: currentThreadId,
        title: text.length > 30 ? text.substring(0, 30) + "..." : text,
        messages: [],
        uploads: [],
        createdAt: new Date().toISOString()
      };
      setThreads(prev => [newThread, ...prev]);
    }

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
      form: undefined
    };

    setMessages(prev => [...prev, userMsg]);
    setTextareaValue("");
    setIsAiTyping(true);
    setShowExecutionPlan(true); // Always show when new process starts
    setUserInterruptedHide(false); // Reset interruption flag
    setUserInterruptedBrowser(false); // Reset browser interruption flag
    isFirstFrame.current = true; // Reset for new message
    setToolLogs([]); // Clear tool logs for the new live process
    setAiThinking(null); // Clear thinking for new process

    try {
      const response = await sciparserApi.sendChatMessage(
        text,
        [],
        preferLiveBrowser,
        currentThreadId
      );
      
      const aiMsg = response.message;
      const responsePlan = response.plan || aiMsg?.plan;
      if (responsePlan && aiMsg) {
        aiMsg.plan = responsePlan;
        setCurrentPlan(responsePlan);
      }

      if (aiMsg) {
        setMessages(prev => [...prev, aiMsg]);
        setThreads(prev => prev.map(t => 
          t.id === currentThreadId ? { ...t, messages: [...t.messages, userMsg, aiMsg] } : t
        ));

        // --- NEW: Auto-hide execution plan if task completed successfully ---
        const contentLower = (aiMsg.content || "").toLowerCase();
        if (!userInterruptedHide && (contentLower.includes("successfully") || contentLower.includes("completed"))) {
          setTimeout(() => {
            if (!userInterruptedHide) {
              setShowExecutionPlan(false);
            }
          }, 3000);
        }

        // --- NEW: Auto-hide browser if task completed successfully ---
        if (!userInterruptedBrowser && (contentLower.includes("successfully") || contentLower.includes("completed"))) {
          setTimeout(() => {
            // Only auto-hide if the user hasn't manually toggled the browser
            if (!userInterruptedBrowser) {
              setBrowserBlink("red");
              // Blink 3 times (approx 1.5s) then close
              setTimeout(() => {
                if (!userInterruptedBrowser) {
                  setBrowserActive(false);
                  setBrowserBlink(null);
                }
              }, 1500);
            }
          }, 3000);
        }

        // If the message has a form, open the popup
        if (aiMsg.form) {
          setActiveForm(aiMsg.form);
          // Initialize form data with empty strings
          const initialData: Record<string, string> = {};
          aiMsg.form.sections.forEach((s: any) => {
            s.fields.forEach((f: any) => {
              initialData[f.id] = "";
            });
          });
          setFormData(initialData);
        }
      }
    } catch (e: any) {
      console.error("Message sending failed:", e);
      // Extract readable message from FastAPI JSON error responses
      let errText = e?.message || "An unexpected error occurred.";
      try {
        const parsed = JSON.parse(errText);
        errText = parsed?.detail || parsed?.message || errText;
        if (typeof errText === "object") errText = JSON.stringify(errText);
      } catch {}
      const errorMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: `⚠️ ${errText}`,
        timestamp: new Date().toISOString(),
        form: undefined
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsAiTyping(false);
    }
  };

  const handleStopProcess = async () => {
    if (!activeThreadId) return;
    try {
      await sciparserApi.stopChatProcess(activeThreadId);
      setIsAiTyping(false);
    } catch (e) {
      console.error("Failed to stop process:", e);
    }
  };

  const handleFormSubmit = () => {
    if (!activeForm) return;
    
    // Construct a message from form data
    const responseParts = Object.entries(formData)
      .filter(([_, val]) => val.trim() !== "")
      .map(([key, val]) => {
        // Find the label for this ID
        let label = key;
        activeForm.sections.forEach((s: any) => {
          const field = s.fields.find((f: any) => f.id === key);
          if (field) label = field.label;
        });
        return `${label}: ${val}`;
      });
    
    if (responseParts.length > 0) {
      handleSendMessage(responseParts.join(", "));
      setActiveForm(null);
      setFormData({});
    }
  };

  const renderMessage = (msg: ChatMessage) => {
    const isSelected = selectedMessages.includes(msg.id || "");
    const isPlanVisible = visiblePlans[msg.id || ""] ?? (msg.role === 'ai' && msg.plan && msg.plan.length > 0);
    const isUser = msg.role === "user" || msg.role === "human";

    return (
      <div 
        key={msg.id || `msg-${msg.timestamp}-${Math.random()}`} 
        className={cn(
          "flex flex-col gap-4 transition-all duration-300", 
          isUser ? "items-end" : "items-start",
          isSelectionMode && "cursor-pointer hover:opacity-80"
        )}
        onClick={() => {
          if (isSelectionMode && msg.id) {
            setSelectedMessages(prev => 
              prev.includes(msg.id) ? prev.filter(id => id !== msg.id) : [...prev, msg.id]
            );
          }
        }}
      >
        {/* Agent Plan Section (Above AI Response) */}
        {!isUser && msg.plan && msg.plan.length > 0 && (
          <div className="w-full max-w-2xl ml-12 mb-2">
            <div className="flex items-center gap-3 mb-3 px-1">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-[10px] font-black text-[#F8FAFC] uppercase tracking-[0.2em]">Execution Trace</span>
              </div>
              <div className="h-px flex-1 bg-[#2A2A2A]" />
            </div>
            <Plan tasks={msg.plan} />
          </div>
        )}

        <div className={cn(
          "group relative flex gap-4 max-w-[85%] transition-all duration-300",
          isUser ? "flex-row-reverse" : "flex-row"
        )}>
          {/* Selection Checkbox Overlay */}
          {isSelectionMode && msg.id && (
            <div className={cn(
              "absolute -top-2 -right-2 z-10 h-6 w-6 rounded-full border-2 flex items-center justify-center transition-all shadow-lg",
              isSelected ? "bg-indigo-600 border-indigo-500 text-white" : "bg-slate-900 border-slate-700 text-transparent"
            )}>
              <Check className="h-3.5 w-3.5" />
            </div>
          )}

          {/* Avatar */}
          <div className={cn(
            "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-lg transition-transform duration-300 group-hover:scale-110",
            isUser ? "bg-emerald-600 text-white" : "bg-[#1E1E1E] border border-[#2A2A2A] text-white"
          )}>
            {isUser ? <User2 className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
          </div>

          {/* Message Bubble */}
          <div className="flex flex-col gap-2 min-w-0">
            <div className={cn(
              "px-5 py-3.5 rounded-2xl shadow-sm border transition-all duration-200",
              isUser 
                ? "bg-emerald-600 border-emerald-500 text-white rounded-tr-none shadow-emerald-500/10" 
                : "bg-[#1a1a1a] border-[#343434] text-slate-100 rounded-tl-none hover:border-[#4a4a4a]",
              isSelectionMode && isSelected && "ring-2 ring-indigo-500 border-indigo-500"
            )}>
              <div className={cn(
                "text-sm leading-relaxed font-medium whitespace-pre-wrap break-words",
                isUser ? "text-white" : "text-slate-100"
              )}>
                {renderFormattedContent(msg.content, isUser)}
              </div>
            </div>
            
            {/* Timestamp & Actions */}
            <div className={cn(
              "flex items-center gap-3 px-1 opacity-0 group-hover:opacity-100 transition-opacity",
              isUser ? "flex-row-reverse" : "flex-row"
            )}>
              <span className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-wider">
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleFileUploaded = async (fileName: string, fileSize: number, fileType: string) => {
    try {
      await sciparserApi.uploadFileMetadata(fileName, fileSize, fileType);
      
      const uploadRes = await sciparserApi.getUploadedFiles();
      const freshUpload = uploadRes.uploads.find((u: UploadedFile) => u.name === fileName) || {
        id: "upl-" + Date.now(),
        name: fileName,
        size: fileSize,
        type: fileType,
        uploadedAt: new Date().toISOString()
      };

      setThreads(prev => prev.map(t => {
        if (t.id === activeThreadId) {
          const uploadsList = t.uploads.some((u: UploadedFile) => u.name === fileName)
            ? t.uploads
            : [...t.uploads, freshUpload];
          return { ...t, uploads: uploadsList };
        }
        return t;
      }));
      setUploads(prev => prev.some((u: UploadedFile) => u.name === fileName) ? prev : [...prev, freshUpload]);

      const autoQuery = `I have attached the document "${fileName}". Please parse and analyze its structures.`;
      await handleSendMessage(autoQuery);
    } catch (e) {
      console.error("File upload failed:", e);
    }
  };

  const sendQuickPrompt = (promptText: string) => {
    handleSendMessage(promptText);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = 1;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  const toggleVoiceMock = () => {
    sendQuickPrompt("Analyze the vocal context frequencies and synthesize SciParser audio.");
  };

  const parseInlineFormatting = (text: string, isUser: boolean = false) => {
    const boldParts = text.split(/(\*\*.*?\*\*)/g);
    return boldParts.map((bPart, bIdx) => {
      if (bPart.startsWith("**") && bPart.endsWith("**")) {
        return (
          <strong key={bIdx} className={cn("font-extrabold", isUser ? "text-white" : "text-white dark:text-white")}>
            {bPart.slice(2, -2)}
          </strong>
        );
      }
      const inlineParts = bPart.split(/(\`.*?\`)/g);
      return inlineParts.map((iPart, iIdx) => {
        if (iPart.startsWith("`") && iPart.endsWith("`")) {
          return (
            <code key={iIdx} className={cn(
              "px-1.5 py-0.5 mx-0.5 rounded font-mono text-[13px] font-bold",
              isUser ? "bg-white/20 text-white" : "bg-white/90 text-sky-500 dark:bg-white/90 dark:text-sky-600"
            )}>
              {iPart.slice(1, -1)}
            </code>
          );
        }
        const urlRegex = /(https?:\/\/[^\s)]+)|www\.[^\s)]+/g;
        return iPart.split(urlRegex).map((segment, segIdx) => {
          if (!segment) return null;
          if (urlRegex.test(segment)) {
            urlRegex.lastIndex = 0;
            const href = segment.startsWith("http") ? segment : `https://${segment}`;
            return (
              <a key={`${iIdx}-${segIdx}`} href={href} target="_blank" rel="noreferrer" className="text-sky-400 underline underline-offset-2 decoration-sky-400/50 hover:text-sky-300">
                {segment}
              </a>
            );
          }
          return segment;
        });
      });
    });
  };

  const parseTableCellContent = (text: string, isUser: boolean = false) => {
    return parseInlineFormatting(text.replace(/\s+/g, " ").trim(), isUser);
  };

  const downloadTableData = (data: any[][], filename: string) => {
    const csvContent = data.map(row => row.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${filename}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderFormattedContent = (content: string, isUser: boolean = false) => {
    if (!content) return null;
    
    // Detect Markdown Tables
    const tableRegex = /\|(.+)\|/g;
    const hasTable = content.includes("|") && content.split("\n").some(line => line.trim().startsWith("|"));

    const parts = content.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        // ... (existing code block rendering)
        const lines = part.slice(3, -3).trim().split("\n");
        const language = lines[0] && !lines[0].includes(" ") ? lines[0] : "";
        const code = language ? lines.slice(1).join("\n") : lines.join("\n");
        
        return (
          <div key={index} className="my-3.5 rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] overflow-hidden font-mono text-[13px] shadow-md">
            <div className="flex justify-between items-center px-4 py-1.5 bg-[#232323] text-xs text-slate-400 font-sans border-b border-[#2A2A2A] select-none font-bold">
              <span className="uppercase text-[10px] tracking-widest text-white">{language || "text"}</span>
              <span className="text-[10px] lowercase font-medium">ready</span>
            </div>
            <pre className="p-4 overflow-x-auto text-[#E5E7EB] leading-relaxed whitespace-pre font-medium">
              {code}
            </pre>
          </div>
        );
      }
      
      // Handle Tables
      if (hasTable && part.includes("|")) {
        const lines = part.split("\n");
        const tableLines = lines.filter(l => l.trim().startsWith("|"));
        if (tableLines.length > 1) {
          const rows = tableLines.map(line => 
            line.split("|").filter(cell => cell.trim() !== "").map(cell => cell.trim())
          );
          const isSeparatorRow = (row: string[]) =>
            row.every(cell => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")));

          const headerRow = rows.find(row => !isSeparatorRow(row)) || [];
          const separatorIndex = rows.findIndex(isSeparatorRow);
          const body = separatorIndex >= 0 ? rows.slice(separatorIndex + 1).filter(row => !isSeparatorRow(row)) : rows.slice(1);

          return (
            <div className="my-5 overflow-hidden rounded-2xl border border-[#2A2A2A] bg-[#1A1A1A] shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
              <div className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3 bg-[#232323] border-b border-[#2A2A2A]">
                <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                  <TableIcon className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Data Table</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => downloadTableData(rows.filter((_, i) => i !== 1), "sciparser_data")}
                  className="h-8 px-3 text-[10px] font-black text-sky-400 hover:bg-sky-500/10 gap-1.5 rounded-xl"
                >
                  <Download className="w-3.5 h-3.5" />
                  DOWNLOAD CSV
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[13px] border-collapse min-w-max">
                  <thead>
                    <tr className="bg-[#232323]">
                      {headerRow.map((h, i) => (
                        <th key={i} className="px-4 sm:px-5 py-3.5 font-black text-white border-b border-[#2A2A2A] whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {i === 0 && <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500/70" />}
                            <span className={cn(isUser ? "text-white" : "text-white dark:text-white")}>{parseTableCellContent(h, isUser)}</span>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {body.map((row, ri) => (
                      <tr
                        key={ri}
                        className={cn(
                          "transition-colors border-b border-[#2A2A2A]",
                          ri % 2 === 0 ? "bg-[#1A1A1A]" : "bg-[#202020]",
                          "hover:bg-[#262626]"
                        )}
                      >
                        {row.map((cell, ci) => (
                          <td
                            key={ci}
                            className={cn(
                                "px-4 sm:px-5 py-3.5 text-[#E5E7EB] align-top",
                                ci === 0 ? "font-medium text-[#E5E7EB] min-w-[22rem]" : "whitespace-nowrap"
                            )}
                          >
                              <div className={cn(ci === 0 ? "whitespace-normal leading-relaxed" : "font-semibold text-[#D1D5DB]")}>{parseTableCellContent(cell, isUser)}</div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        }
      }

      const lines = part.split("\n");
      const firstRenderableLineIndex = lines.findIndex((line) => {
        const trimmed = line.trim();
        return !!trimmed && !trimmed.startsWith("|");
      });
      return (
        <div key={index} className="space-y-2.5">
          {lines.map((line, lineIdx) => {
            const trimmedLine = line.trim();
            if (!trimmedLine || trimmedLine.startsWith("|")) return null;
            
            if (trimmedLine.startsWith("- ") || trimmedLine.startsWith("* ") || trimmedLine.startsWith("• ")) {
              const listContent = trimmedLine.replace(/^[-*•]\s+/, "");
              return (
                <li key={lineIdx} className={cn(
                  "ml-5 list-disc leading-relaxed pr-2",
                  isUser ? "text-white" : "text-foreground/90"
                )}>
                  {parseInlineFormatting(listContent, isUser)}
                </li>
              );
            }
            
            const numMatch = trimmedLine.match(/^(\d+)\.\s+(.*)/);
            if (numMatch) {
              const listContent = numMatch[2];
              return (
                <li key={lineIdx} className={cn(
                  "ml-5 list-decimal leading-relaxed pr-2",
                  isUser ? "text-white" : "text-foreground/90"
                )} style={{ listStyleType: "decimal" }}>
                  {parseInlineFormatting(listContent, isUser)}
                </li>
              );
            }
            
            const isLeadSentence = !isUser && lineIdx === firstRenderableLineIndex;
            const isSectionHeading = !isUser && (/^Current Status:$/i.test(trimmedLine) || /^Verification Details:$/i.test(trimmedLine) || /^Verification Details:$/i.test(trimmedLine) || /^Current State:$/i.test(trimmedLine));

            return (
              <p key={lineIdx} className={cn(
                "relative leading-relaxed text-[15px] font-medium font-sans",
                isUser
                  ? "text-white"
                  : isLeadSentence
                    ? "text-[#E5E7EB]"
                    : isSectionHeading
                      ? "text-white dark:text-white font-bold"
                      : (line.includes("--- Execution Summary ---") ? "text-slate-400 dark:text-slate-400 mt-4 pt-4 border-t border-border font-bold" : "text-[#E5E7EB]")
              )}>
                {parseInlineFormatting(line, isUser)}
              </p>
            );
          })}
        </div>
      );
    });
  };

  const filteredThreads = threads.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggleLiveBrowser = async (isActive: boolean) => {
    if (isActive) {
      try {
        const res = await sciparserApi.checkBrowserSession();
        if (!res.is_active) {
          setSuccess("Browser is not initialized yet. Opening the preview panel anyway.");
          setTimeout(() => setSuccess(""), 3000);
        }
      } catch (err) {
        console.error("Failed to check browser session:", err);
        setSuccess("Browser session check failed. Opening the preview panel anyway.");
        setTimeout(() => setSuccess(""), 3000);
      }
    }
    
    setBrowserActive(isActive);
    setLastManualToggle(Date.now()); // Track manual interaction
  };

  const sidebarItemBase = "group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm font-medium";
  const sidebarItemInactive = "text-[#D1D5DB] hover:text-white hover:bg-[#232323]";
  const sidebarItemActive = "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20";

  const handleCreateSchedule = async () => {
    if (!activeThreadId) return;
    
    try {
      setIsNavigating(true);
      setLoaderText("Creating Schedule");
      
      await sciparserApi.createSchedule({
        chat_id: activeThreadId,
        title: threads.find(t => t.id === activeThreadId)?.title || "New Schedule",
        selected_message_ids: selectedMessages,
        selected_tool_ids: selectedTools,
        schedule_type: scheduleType,
        email_recipient: emailRecipient || userProfile?.email
      });
      
      setSuccess("Schedule created successfully!");
      setIsSchedulerOpen(false);
      setIsSelectionMode(false);
      setSelectedMessages([]);
      setSelectedToolIds([]);
    } catch (err) {
      console.error("Failed to create schedule:", err);
      setError("Failed to create schedule.");
    } finally {
      setIsNavigating(false);
      setTimeout(() => setSuccess(""), 3000);
    }
  };

  const toggleSelectionMode = () => {
    setIsSelectionMode(!isSelectionMode);
    if (isSelectionMode) {
      setSelectedMessages([]);
      setSelectedToolIds([]);
    }
  };

  const handleClearSelection = () => {
    setSelectedMessages([]);
    setSelectedToolIds([]);
  };

  const handleCloseBrowser = async () => {
    try {
      await sciparserApi.closeBrowser();
      setBrowserActive(false);
      setBrowserFrame(null);
      setSuccess("Browser session closed successfully.");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      console.error("Failed to close browser:", err);
      setError("Failed to close browser session.");
      setTimeout(() => setError(""), 3000);
    }
  };

  const handleSwitchView = (view: "chat" | "schedules") => {
    if (currentView === view) return;
    
    setIsNavigating(true);
    setLoaderText(view === "chat" ? "Switching to Chat" : "Opening Schedules");
    
    setTimeout(() => {
      setCurrentView(view);
      setIsNavigating(false);
    }, 800);
  };

  // --- Authentication Screen ---
  if (!userProfile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        {isNavigating && <AiLoader text={loaderText} />}
        <Signup1
          isLoginMode={isLoginMode}
          onToggleMode={() => setIsLoginMode(!isLoginMode)}
          onSubmit={handleAuthSubmit}
          loading={loading}
          error={error}
          success={success}
        />
      </div>
    );
  }

  // --- Main Workspace ---
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans">
      {isNavigating && <AiLoader text={loaderText} />}

      {/* Form Popup Overlay */}
      {activeForm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="w-full max-w-lg bg-card rounded-2xl shadow-2xl border border-border overflow-hidden flex flex-col max-h-[90vh]"
          >
            {/* Popup Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
              <div>
                <h3 className="font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider text-xs">
                  {activeForm.title}
                </h3>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Action Required: Please provide the details below.
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setActiveForm(null)} className="h-8 w-8 rounded-full">
                <X className="w-4 h-4" />
              </Button>
            </div>

            {/* Popup Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {activeForm.sections.map((section: any, sIdx: number) => (
                <div key={sIdx} className="space-y-4">
                  {section.section_title && (
                    <div className="flex items-center gap-2">
                      <div className="h-px flex-1 bg-border" />
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest px-2">
                        {section.section_title}
                      </span>
                      <div className="h-px flex-1 bg-border" />
                    </div>
                  )}
                  <div className="grid gap-4">
                    {section.fields.map((field: any) => (
                      <div key={field.id} className="space-y-1.5">
                        <label className="text-xs font-bold text-foreground/80 flex items-center justify-between">
                          <span>{field.label} {field.required && <span className="text-red-500">*</span>}</span>
                          {field.type === 'password' && <span className="text-[9px] text-muted-foreground font-normal italic">Encrypted</span>}
                        </label>
                        <input
                          type={field.type || "text"}
                          placeholder={field.placeholder}
                          value={formData[field.id] || ""}
                          onChange={(e) => setFormData(prev => ({ ...prev, [field.id]: e.target.value }))}
                          className="w-full px-4 py-2.5 text-sm rounded-xl bg-muted/50 border border-border focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all placeholder:text-muted-foreground"
                        />
                        {field.note && <p className="text-[10px] text-muted-foreground italic pl-1">{field.note}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {activeForm.security_note && (
                <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 text-[11px] text-amber-700 dark:text-amber-400 flex items-start gap-3">
                  <div className="w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
                    <CheckCircle2 className="w-3 h-3" />
                  </div>
                  <span>{activeForm.security_note}</span>
                </div>
              )}
            </div>

            {/* Popup Footer */}
            <div className="px-6 py-4 border-t border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/5 flex items-center justify-end gap-3">
              <Button variant="ghost" onClick={() => setActiveForm(null)} className="text-xs font-bold">
                CANCEL
              </Button>
              <Button 
                onClick={handleFormSubmit}
                className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-6 rounded-xl shadow-lg shadow-indigo-500/20"
              >
                SUBMIT & PROCESS
              </Button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Premium AI Scheduler Workspace */}
      <PremiumScheduler 
        isOpen={isSchedulerOpen}
        onClose={() => setIsSchedulerOpen(false)}
        selectedMessages={selectedMessages}
        selectedTools={selectedTools}
        chatId={activeThreadId}
        messages={messages}
        currentPlan={currentPlan}
        toolLogs={toolLogs}
      />

      {/* NEW: Detailed Review Popup (Opens over Scheduler) */}
      {isReviewOpen && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-3xl max-h-[80vh] bg-white dark:bg-[#0f0f12] rounded-[32px] shadow-2xl border border-slate-200 dark:border-white/5 overflow-hidden flex flex-col"
          >
            <div className="px-8 py-6 border-b border-slate-100 dark:border-white/5 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                  <BookOpen className="w-4 h-4 text-indigo-500" />
                </div>
                <h3 className="font-black text-slate-900 dark:text-white text-lg tracking-tight uppercase">Review Selection</h3>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setIsReviewOpen(false)} className="h-10 w-10 rounded-2xl">
                <X className="w-5 h-5 text-slate-400" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-4 hide-scrollbar">
              {selectedMessages.map(id => {
                const msg = messages.find(m => m.id === id);
                return (
                  <div key={id} className="flex flex-col gap-3 bg-slate-50 dark:bg-white/2 p-5 rounded-2xl border border-slate-100 dark:border-white/5">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-3.5 h-3.5 text-indigo-500" />
                      <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">User Message</span>
                    </div>
                    <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium">
                      {msg?.content}
                    </div>
                  </div>
                );
              })}
              {selectedTools.map(id => {
                const log = toolLogs.find(l => l.id === id);
                if (!log) return null;
                return (
                  <div key={id} className="flex flex-col gap-4 bg-slate-50 dark:bg-white/2 p-6 rounded-[24px] border border-slate-100 dark:border-white/5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Code className="w-4 h-4 text-emerald-500" />
                        <span className="text-[11px] font-black text-slate-700 dark:text-slate-200 uppercase tracking-wider">{log.tool_name}</span>
                      </div>
                      <div className={cn(
                        "px-2 py-0.5 rounded-md text-[9px] font-black uppercase",
                        log.status === 'SUCCESS' ? "bg-emerald-500/10 text-emerald-600" : 
                        log.status === 'FAILED' ? "bg-red-500/10 text-red-600" : "bg-blue-500/10 text-blue-600"
                      )}>
                        {log.status}
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="space-y-1.5">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest ml-1">Input</span>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-white dark:bg-black/20 p-3 rounded-xl border border-slate-100 dark:border-white/5 font-mono break-all">
                          {typeof log.tool_input === 'string' ? log.tool_input : JSON.stringify(log.tool_input, null, 2)}
                        </div>
                      </div>
                      {log.tool_output && (
                        <div className="space-y-1.5">
                          <span className="text-[9px] font-bold text-emerald-500/70 uppercase tracking-widest ml-1">Output</span>
                          <div className="text-[11px] text-slate-600 dark:text-slate-300 bg-emerald-50/30 dark:bg-emerald-500/5 p-3 rounded-xl border border-emerald-100/30 dark:border-emerald-500/10 font-mono whitespace-pre-wrap">
                            {log.tool_output}
                          </div>
                        </div>
                      )}
                      {log.error_message && (
                        <div className="space-y-1.5">
                          <span className="text-[9px] font-bold text-red-500/70 uppercase tracking-widest ml-1">Error</span>
                          <div className="text-[11px] text-red-600 dark:text-red-400 bg-red-50/30 dark:bg-red-500/5 p-3 rounded-xl border border-red-100/30 dark:border-red-500/10 font-mono whitespace-pre-wrap">
                            {log.error_message}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="px-8 py-6 border-t border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/5 flex justify-center shrink-0">
              <Button 
                onClick={() => setIsReviewOpen(false)}
                className="bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-xs font-black uppercase tracking-widest px-10 rounded-2xl h-12"
              >
                Close Review
              </Button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Mobile sidebar backdrop */}
      {isMobile && isMobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div 
        className={cn(
          "flex flex-col shrink-0 transition-all duration-300 overflow-hidden border-[#232B36] backdrop-blur-xl bg-[#05070A]/95",
          isMobile
            ? cn(
                "fixed inset-y-0 left-0 z-50 h-full w-[320px] max-w-[85vw] border-r",
                isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
              )
            : cn(
                "relative h-full z-20 border-r",
                isSidebarCollapsed
                  ? "w-0 border-r-0"
                  : currentView === "schedules"
                    ? "w-16"
                    : "w-[320px] lg:w-[340px] xl:w-[360px]"
              )
        )}
      >
        {/* Icon-only rail shown when on Automation page (desktop only) */}
        {!isMobile && !isSidebarCollapsed && currentView === "schedules" && (
          <div className="flex h-full flex-col items-center py-4 gap-3">
            <div className="pointer-events-none absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_28%)]" />
            {/* Logo */}
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full border border-[#22D3EE]/20 bg-[#0B0F14] text-[#10B981] shadow-[0_0_18px_rgba(16,185,129,0.16)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="relative z-10 w-8 h-px bg-[#232B36]" />
            {/* Chat nav icon */}
            <button
              onClick={() => handleSwitchView("chat")}
              title="AI Chat"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#232B36] bg-white/[0.02] text-[#9CA3AF] hover:border-[#22D3EE]/25 hover:bg-[#161B22] hover:text-[#F8FAFC] transition-all"
            >
              <MessageSquare className="h-5 w-5" />
            </button>
            {/* Automation nav icon (active) */}
            <button
              onClick={() => handleSwitchView("schedules")}
              title="Automation"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#22D3EE]/35 bg-gradient-to-b from-[#10B981]/20 to-[#22D3EE]/15 text-[#F8FAFC] shadow-[0_0_16px_rgba(34,211,238,0.15)] transition-all"
            >
              <Calendar className="h-5 w-5" />
            </button>
            {/* Spacer */}
            <div className="flex-1" />
            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              title="Toggle theme"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#232B36] bg-[#0B0F14] text-[#9CA3AF] hover:bg-[#161B22] hover:text-[#F8FAFC] transition-all"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {/* Logout */}
            <button
              onClick={handleLogout}
              title="Log out"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#232B36] bg-[#0B0F14] text-red-400 hover:bg-[#161B22] hover:text-red-300 transition-all"
            >
              <LogOut className="w-4 h-4" />
            </button>
            {/* User avatar */}
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-[#10B981] text-white text-xs font-black shadow-[0_0_18px_rgba(16,185,129,0.3)]">
              {userProfile?.username.slice(0, 2).toUpperCase()}
            </div>
          </div>
        )}
        <div className={cn("relative flex h-full flex-col bg-[#05070A]/95", (!isMobile && !isSidebarCollapsed && currentView === "schedules") && "hidden")}>
          <div className="pointer-events-none absolute inset-0 opacity-30 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_28%),radial-gradient(circle_at_bottom,rgba(16,185,129,0.06),transparent_22%)]" />

          {/* Sidebar Header */}
          <div className="relative z-10 px-4 pt-4 pb-3">
            <div className="rounded-[18px] border border-[#232B36] bg-white/[0.03] px-4 py-4 shadow-[0_14px_40px_rgba(0,0,0,0.24)] backdrop-blur-xl">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#22D3EE]/20 bg-[#0B0F14] text-[#10B981] shadow-[0_0_18px_rgba(16,185,129,0.16)]">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-[17px] font-semibold tracking-tight text-[#F8FAFC]">SciParser AI</div>
                    <div className="text-[11px] text-[#6B7280]">Orchestration dashboard</div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {isMobile && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setIsMobileSidebarOpen(false)}
                      className="h-10 w-10 rounded-[14px] border border-[#232B36] bg-[#111827]/60 text-[#9CA3AF] hover:bg-[#161B22] hover:text-[#F8FAFC]"
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleNewChat(true)}
                    className="h-10 w-10 rounded-[14px] border border-[#232B36] bg-[#111827]/60 text-[#F8FAFC] hover:bg-[#161B22] hover:text-[#22D3EE]"
                  >
                    <Plus className="h-5 w-5" />
                  </Button>
                </div>
              </div>

              {/* Sidebar Search */}
              <div className="mt-4 relative">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-[14px] border border-[#232B36] bg-[#0B0F14]/80 py-3 pl-10 pr-12 text-sm text-[#E5E7EB] outline-none placeholder:text-[#64748B] focus:border-[#22D3EE]/50 focus:ring-2 focus:ring-[#22D3EE]/15"
                />
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-[#232B36] bg-white/[0.03] px-2 py-0.5 text-[10px] font-semibold text-[#64748B]">
                  ⌘K
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleSwitchView("chat")}
                  className={cn(
                    "flex items-center justify-between rounded-[14px] border px-3 py-3 text-left transition-all duration-200",
                    currentView === "chat"
                      ? "border-[#22D3EE]/35 bg-gradient-to-r from-[#10B981]/20 to-[#22D3EE]/15 text-[#F8FAFC] shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                      : "border-[#232B36] bg-white/[0.02] text-[#D1D5DB] hover:border-[#22D3EE]/25 hover:bg-[#161B22] hover:text-[#F8FAFC]"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare className="h-4 w-4 shrink-0" />
                    <span className="truncate text-sm font-semibold">AI Chat Core</span>
                  </div>
                  <Sparkles className="h-4 w-4 shrink-0 text-[#22D3EE]" />
                </button>

                <button
                  onClick={() => handleSwitchView("schedules")}
                  className={cn(
                    "flex items-center justify-between rounded-[14px] border px-3 py-3 text-left transition-all duration-200",
                    currentView === "schedules"
                      ? "border-[#22D3EE]/35 bg-gradient-to-r from-[#10B981]/20 to-[#22D3EE]/15 text-[#F8FAFC] shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                      : "border-[#232B36] bg-white/[0.02] text-[#D1D5DB] hover:border-[#22D3EE]/25 hover:bg-[#161B22] hover:text-[#F8FAFC]"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Calendar className="h-4 w-4 shrink-0" />
                    <span className="truncate text-sm font-semibold">Automation</span>
                  </div>
                  <div className="h-2 w-2 rounded-full bg-[#22D3EE]" />
                </button>
              </div>
            </div>
          </div>

          {/* Sidebar Thread List */}
          <div className="relative z-10 flex-1 overflow-y-auto px-4 pb-3 pt-1 hide-scrollbar">
            <div className="flex items-center gap-3 px-1.5 pb-3 pt-1">
              <div className="h-px flex-1 bg-[#232B36]" />
              <span className="text-[10px] font-black uppercase tracking-[0.24em] text-[#10B981]">Recent Chats</span>
              <div className="h-px flex-1 bg-[#232B36]" />
            </div>

            <div className="space-y-2">
              {filteredThreads.map((t) => {
                const isActive = t.id === activeThreadId;
                return (
                  <div
                    key={t.id}
                    onClick={() => handleSelectThread(t.id)}
                    className={cn(
                      "group relative overflow-hidden rounded-[14px] border px-3.5 py-3 transition-all duration-200 cursor-pointer",
                      isActive
                        ? "border-[#10B981]/35 bg-gradient-to-r from-[#10B981]/16 to-[#22D3EE]/10 shadow-[0_0_30px_rgba(16,185,129,0.12)]"
                        : "border-[#232B36] bg-white/[0.02] hover:border-[#22D3EE]/25 hover:bg-[#161B22]"
                    )}
                  >
                    {isActive && <div className="absolute left-0 top-0 h-full w-1 bg-[#10B981] shadow-[0_0_14px_rgba(16,185,129,0.65)]" />}
                    <div className="flex items-start gap-3 pl-1">
                      <div className={cn(
                        "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] border",
                        isActive ? "border-[#10B981]/20 bg-[#10B981]/10 text-[#10B981]" : "border-[#232B36] bg-[#0B0F14] text-[#9CA3AF]"
                      )}>
                        <MessageSquare className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className={cn(
                            "truncate text-[14px] font-semibold tracking-tight",
                            isActive ? "text-[#F8FAFC]" : "text-[#D1D5DB] group-hover:text-[#F8FAFC]"
                          )}>
                            {t.title}
                          </span>
                          <div className="flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeletingThreadId(String(t.id));
                              }}
                              className="rounded-md border border-[#232B36] bg-white/[0.03] p-1.5 text-[#9CA3AF] hover:border-red-500/30 hover:text-red-400"
                            >
                              <Trash className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <span className="text-[11px] text-[#9CA3AF]">{isActive ? "Pinned chat" : `${t.messages?.length || 0} messages`}</span>
                          <span className="text-[10px] text-[#6B7280]">
                            {t.createdAt ? new Date(t.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' }) : ""}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              onClick={() => handleNewChat(true)}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-[14px] border border-[#232B36] bg-[#0B0F14]/80 px-3 py-3 text-sm font-semibold text-[#10B981] transition-all hover:border-[#10B981]/30 hover:bg-[#161B22] hover:text-[#34D399]"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-[#10B981]/30 bg-[#10B981]/10 text-[#10B981]">+</span>
              New Chat
            </button>
          </div>

          {/* Sidebar Footer */}
          <div className="relative z-10 px-4 pb-4 pt-2">
            <div className="rounded-[16px] border border-[#232B36] bg-white/[0.03] px-4 py-3 backdrop-blur-xl shadow-[0_14px_40px_rgba(0,0,0,0.24)]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#10B981] text-white font-black shadow-[0_0_24px_rgba(16,185,129,0.38)]">
                    {userProfile?.username.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#F8FAFC]">{userProfile?.username}</p>
                    <p className="truncate text-[11px] text-[#9CA3AF]">{userProfile?.email}</p>
                  </div>
                </div>
                <button className="rounded-lg border border-[#232B36] bg-[#0B0F14] p-2 text-[#9CA3AF] transition-colors hover:border-[#22D3EE]/25 hover:text-[#F8FAFC]">
                  <ChevronDown className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 flex items-center justify-between gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleTheme}
                  className="h-10 w-10 rounded-[12px] border border-[#232B36] bg-[#0B0F14] text-[#9CA3AF] transition-all hover:bg-[#161B22] hover:text-[#F8FAFC] active:scale-90"
                >
                  {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  className="h-10 w-10 rounded-[12px] border border-[#232B36] bg-[#0B0F14] text-red-400 transition-all hover:bg-[#161B22] hover:text-red-300 active:scale-90"
                >
                  <LogOut className="w-5 h-5" />
                </Button>
              </div>
            </div>
          </div>

          {/* Delete Chat Confirmation Modal */}
          {deletingThreadId && (
            <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/65 backdrop-blur-sm p-4">
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                className="w-full max-w-sm rounded-[20px] border border-[#232B36] bg-[#111827] p-6 text-center shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-red-500/20 bg-red-500/10">
                  <Trash className="h-6 w-6 text-red-400" />
                </div>
                <div className="mt-4 space-y-2">
                  <h3 className="text-lg font-bold text-[#F8FAFC]">Delete chat?</h3>
                  <p className="text-sm text-[#9CA3AF]">This will permanently remove this conversation and all its history.</p>
                </div>
                <div className="mt-5 flex gap-3">
                  <Button
                    variant="ghost"
                    onClick={() => setDeletingThreadId(null)}
                    className="flex-1 rounded-xl border border-[#232B36] bg-white/[0.03] text-xs font-bold text-[#E5E7EB] hover:bg-[#161B22]"
                  >
                    CANCEL
                  </Button>
                  <Button
                    onClick={() => handleDeleteThread(deletingThreadId)}
                    className="flex-1 rounded-xl bg-red-500 text-xs font-bold text-white hover:bg-red-600"
                  >
                    DELETE
                  </Button>
                </div>
              </motion.div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-row overflow-hidden h-full min-h-0 relative">
        {currentView === "schedules" ? (
          <SchedulesPage onBack={() => handleSwitchView("chat")} />
        ) : (
          <>
            {/* Chat Column */}
            <div 
              className="flex flex-col h-full min-w-[320px] bg-background transition-all duration-300"
              style={{ flex: `1 1 ${100 - (browserActive ? browserPanelWidth : 0)}%` }}
            >
              
              {/* Chat Header */}
              <div className="h-14 border-b border-[#2A2A2A] bg-[#1A1A1A] px-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => {
                      if (isMobile) {
                        setIsMobileSidebarOpen(!isMobileSidebarOpen);
                      } else {
                        setIsSidebarCollapsed(!isSidebarCollapsed);
                      }
                    }}
                    className="hover:bg-muted"
                  >
                    {(isMobile ? isMobileSidebarOpen : !isSidebarCollapsed) ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
                  </Button>
                  <div className="font-semibold text-sm text-[#F8FAFC]">{activeModel}</div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant={showHistory ? "default" : "outline"}
                    size="sm"
                    onClick={() => setShowHistory(!showHistory)}
                    className={cn(
                      "gap-1.5 text-xs font-semibold",
                      showHistory && "bg-indigo-600 hover:bg-indigo-700 text-white border-none"
                    )}
                  >
                    <Clock className="w-4 h-4" />
                    <span>History</span>
                  </Button>

                  <Button
                    variant={isSelectionMode ? "default" : "outline"}
                    size="sm"
                    onClick={toggleSelectionMode}
                    className={cn(
                      "gap-1.5 text-xs font-semibold",
                      isSelectionMode && "bg-indigo-600 hover:bg-indigo-700 text-white border-none"
                    )}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{isSelectionMode ? "Cancel Selection" : "Schedule Task"}</span>
                  </Button>

                  {isSelectionMode && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleClearSelection}
                      className="gap-1.5 text-xs font-semibold text-slate-500 border-slate-200 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
                    >
                      <Trash className="w-4 h-4" />
                      <span>Clear All</span>
                    </Button>
                  )}

                  {isSelectionMode && (selectedMessages.length > 0 || selectedTools.length > 0) && (
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => setIsSchedulerOpen(true)}
                      className="gap-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white border-none"
                    >
                      <RefreshCw className="w-4 h-4" />
                      <span>Configure Schedule ({selectedMessages.length + selectedTools.length})</span>
                    </Button>
                  )}

                  <Button
                    variant={browserActive ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      const nextState = !browserActive;
                      handleToggleLiveBrowser(nextState);
                      setUserInterruptedBrowser(!nextState); // Only suppress auto-open when manually closing
                    }}
                    className={cn(
                      "gap-1.5 text-xs font-semibold transition-all duration-500",
                      browserActive && "bg-emerald-600 hover:bg-emerald-700 text-white border-none",
                      browserBlink === "green" && "ring-4 ring-emerald-500 animate-pulse border-emerald-500",
                      browserBlink === "red" && "ring-4 ring-red-500 animate-pulse border-red-500"
                    )}
                  >
                    <Globe className="w-4 h-4" />
                    <span>Live Browser</span>
                  </Button>

                  {/* NEW: Close Browser Button - Only visible when browser is active */}
                  {browserActive && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCloseBrowser}
                      className="gap-1.5 text-xs font-semibold text-red-500 border-red-200 hover:bg-red-50 dark:border-red-900/30 dark:hover:bg-red-900/10"
                    >
                      <XIcon className="w-4 h-4" />
                      <span>Close Browser</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* Messages Container */}
              <div className="flex-1 flex flex-row overflow-hidden">
                <div 
                  ref={scrollRef}
                  className="flex-1 overflow-y-auto p-6 space-y-6"
                >
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
                      <div className="w-12 h-12 rounded-2xl bg-[#1E1E1E] flex items-center justify-center text-[#22D3EE] border border-[#2A2A2A]">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <h2 className="text-xl font-bold text-[#F8FAFC]">How can I assist you today?</h2>
                      <p className="text-sm text-[#9CA3AF]">
                        SciParser can browse the web, analyze documents, and run complex multi-agent workflows.
                      </p>
                      <div className="grid grid-cols-2 gap-2 w-full pt-4">
                        <button 
                          onClick={() => sendQuickPrompt("Go to Hacker News and extract top stories")}
                          className="p-3 text-xs font-medium text-left rounded-xl border border-[#2A2A2A] text-[#E5E7EB] hover:bg-[#232323] transition-colors"
                        >
                          📰 Extract Hacker News
                        </button>
                        <button 
                          onClick={() => sendQuickPrompt("Search for latest AI research papers")}
                          className="p-3 text-xs font-medium text-left rounded-xl border border-[#2A2A2A] text-[#E5E7EB] hover:bg-[#232323] transition-colors"
                        >
                          🔬 Search AI Papers
                        </button>
                      </div>
                    </div>
                  ) : (
                    messages.map(renderMessage)
                  )}

                  {/* Live Plan / Loading State */}
                  {isAiTyping && (
                    <div className="mt-4 max-w-2xl space-y-4">
                      <div className="flex items-center justify-between px-1">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                            <div className="text-[10px] font-black text-[#9CA3AF] uppercase tracking-[0.2em]">Live Execution</div>
                          </div>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={handleStopProcess}
                          className="h-7 px-2 text-[10px] font-bold text-red-500 hover:text-red-600 hover:bg-red-500/10 gap-1.5"
                        >
                          <X className="w-3 h-3" />
                          STOP PROCESS
                        </Button>
                      </div>
                      
                      <AnimatePresence>
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 10 }}
                          className="overflow-hidden"
                        >
                          {currentPlan ? (
                            <Plan 
                              tasks={currentPlan} 
                              thoughts={aiThinking ? [aiThinking] : []} 
                            />
                          ) : (
                            <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-5 shadow-sm">
                              <MessageLoading />
                            </div>
                          )}
                        </motion.div>
                      </AnimatePresence>
                    </div>
                  )}
                </div>

                {/* History Panel */}
                <AnimatePresence>
                  {showHistory && (
                    <>
                      {/* Resize Handle for History */}
                      <div 
                        onMouseDown={handleHistoryResizeStart}
                        className="w-1 bg-[#2A2A2A] hover:bg-indigo-500 cursor-col-resize transition-colors z-30 relative group"
                      >
                        <div className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize" />
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-12 rounded-full bg-[#3A3A3A] group-hover:bg-white transition-colors" />
                      </div>

                      <motion.div
                        ref={historyPanelRef}
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: historyPanelWidth, opacity: 1 }}
                        exit={{ width: 0, opacity: 0 }}
                        className="border-l border-[#2A2A2A] bg-[#0D0D0F] overflow-hidden flex flex-col shrink-0"
                      >
                        <div className="p-4 border-b border-[#2A2A2A] flex items-center justify-between bg-[#1A1A1A]">
                          <div className="flex items-center gap-2">
                            <Clock className="w-4 h-4 text-indigo-400" />
                            <span className="text-xs font-bold uppercase tracking-widest text-[#F8FAFC]">Agent History</span>
                          </div>
                          <Button variant="ghost" size="icon" onClick={() => setShowHistory(false)} className="h-6 w-6 rounded-full">
                            <X className="w-3 h-3" />
                          </Button>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                          <ProcessingPanel 
                            agentHistory={agentHistory} 
                            toolHistory={toolLogs} 
                            isBrowserActive={false} 
                            browserFrame={null} 
                          />
                        </div>
                      </motion.div>
                    </>
                  )}
                </AnimatePresence>
              </div>

              {/* Chat Input Area */}
              <div className="p-4 bg-[#1A1A1A] border-t border-[#2A2A2A]">
                <div className="max-w-3xl mx-auto relative flex items-end gap-2 bg-[#111111] border border-[#2A2A2A] rounded-xl p-2">
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={handleFileSelect} 
                    className="hidden" 
                    multiple 
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => fileInputRef.current?.click()}
                    className="hover:bg-[#232323] shrink-0"
                  >
                    <Paperclip className="w-5 h-5 text-[#9CA3AF]" />
                  </Button>
                  <textarea
                    ref={textareaRef}
                    rows={1}
                    value={textareaValue}
                    onChange={(e) => {
                      setTextareaValue(e.target.value);
                      adjustHeight();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(textareaValue);
                      }
                    }}
                    placeholder="Ask SciParser anything..."
                    className="flex-1 max-h-48 resize-none bg-transparent border-none focus:outline-none text-sm py-2 px-1 text-[#E5E7EB] placeholder:text-[#6B7280]"
                  />
                  <Button
                    onClick={() => handleSendMessage(textareaValue)}
                    disabled={!textareaValue.trim()}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white shrink-0"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>

            </div>

            {/* Resizable Live Browser Panel */}
            {browserActive && (
              <>
                {/* Resize Handle */}
                <div 
                  onMouseDown={handleBrowserResizeStart}
                  className="w-1.5 bg-[#2A2A2A] hover:bg-indigo-500 cursor-col-resize transition-colors z-30 relative group"
                >
                  <div className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize" />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-12 rounded-full bg-[#3A3A3A] group-hover:bg-white transition-colors" />
                </div>
                
                <div 
                  ref={browserPanelRef}
                  style={{ width: `${browserPanelWidth}%` }}
                  className="h-full overflow-hidden bg-[#000000] flex flex-col shrink-0 transition-[width] duration-75 ease-out"
                >
                  <BrowserPreview 
                    frame={browserFrame} 
                    isActive={browserActive} 
                    onClose={() => setBrowserActive(false)}
                    toolLogs={toolLogs}
                    isAiTyping={isAiTyping}
                    activeThreadId={activeThreadId}
                    isSelectionMode={isSelectionMode}
                    selectedTools={selectedTools}
                    onToggleToolSelection={(id) => {
                      setSelectedToolIds(prev => 
                        prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
                      );
                    }}
                    onClearLogs={() => setToolLogs([])}
                  />
                </div>
              </>
            )}
          </>
        )}

      </div>
    </div>
  );
};

export default ChatPage;