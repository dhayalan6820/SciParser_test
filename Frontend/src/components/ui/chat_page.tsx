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
import { 
  Sparkles, User2, Database, RefreshCw, CheckCircle2, 
  BookOpen, MessageSquare, Plus, LogOut, Trash, Pencil, Check, Menu, X, 
  ChevronDown, Globe, Send, PanelLeftClose, PanelLeftOpen, Search, Code, Terminal,
  Sun, Moon, FileText, Paperclip, X as XIcon,
  Loader2, Download, Table as TableIcon, Calendar
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
  const [agentPanelHeight, setAgentPanelHeight] = React.useState(200); // pixels
  
  // File upload states
  const [isDraggingFile, setIsDraggingFile] = React.useState(false);
  const [uploadingFiles, setUploadingFiles] = React.useState<string[]>([]);
  
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const toolLogsScrollRef = React.useRef<HTMLDivElement>(null);
  const browserPanelRef = React.useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = React.useState(false);
  const [isAtBottom, setIsAtBottom] = React.useState(true);

  // Handle tool logs auto-scroll
  const handleToolLogsScroll = () => {
    if (toolLogsScrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = toolLogsScrollRef.current;
      const atBottom = scrollHeight - scrollTop <= clientHeight + 50; // 50px buffer
      setIsAtBottom(atBottom);
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
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsResizing(true);
    e.preventDefault();
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !browserPanelRef.current) return;
      
      const containerRect = browserPanelRef.current.parentElement?.getBoundingClientRect();
      if (!containerRect) return;
      
      const newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
      if (newWidth > 20 && newWidth < 80) {
        setBrowserPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

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

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/sciparser/v1/browser/stream?chat_id=${activeThreadId || 'none'}&token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
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

          // --- NEW: Route frames by chat_id ---
          if (frameData.chat_id && frameData.chat_id !== activeThreadId) {
            return; // Ignore frames for other chats
          }

          // Extract the actual frame data (handle nested objects or raw strings)
          let actualFrame = frameData.frame;
          if (typeof actualFrame === 'object' && actualFrame !== null) {
            actualFrame = actualFrame.data || actualFrame.text || JSON.stringify(actualFrame);
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
            const toolMsg = JSON.parse(msg.data);
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
    };

    ws.onopen = () => console.log("Browser stream connected for", activeThreadId);
    ws.onclose = () => console.log("Browser stream disconnected");

    return () => ws.close();
  }, [browserActive, activeThreadId]);

  // WebSocket for Live Agent Plan (Analysis -> Strategy -> Execution)
  React.useEffect(() => {
    if (!isAiTyping || !activeThreadId) {
      setCurrentPlan(null);
      return;
    }

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/sciparser/v1/ws/plan/${activeThreadId}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "plan_update") {
          setCurrentPlan(msg.data);
        } else if (msg.type === "thought_update") {
          setAiThinking(msg.data);
        }
      } catch (err) {
        console.error("Plan stream error:", err);
      }
    };

    return () => ws.close();
  }, [isAiTyping, activeThreadId]);

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

        // Tool logs are now live-only, no need to fetch history here
        setToolLogs([]);
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
      
      // Tool logs are now live-only, no need to fetch history here
      setToolLogs([]);
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
      if (response.plan && aiMsg) {
        aiMsg.plan = response.plan;
      }

      if (aiMsg) {
        setMessages(prev => [...prev, aiMsg]);
        setThreads(prev => prev.map(t => 
          t.id === currentThreadId ? { ...t, messages: [...t.messages, userMsg, aiMsg] } : t
        ));

        // --- NEW: Auto-hide execution plan if task completed successfully ---
        if (!userInterruptedHide && (aiMsg.content.toLowerCase().includes("successfully") || aiMsg.content.toLowerCase().includes("completed"))) {
          setTimeout(() => {
            if (!userInterruptedHide) {
              setShowExecutionPlan(false);
            }
          }, 3000);
        }

        // --- NEW: Auto-hide browser if task completed successfully ---
        if (!userInterruptedBrowser && (aiMsg.content.toLowerCase().includes("successfully") || aiMsg.content.toLowerCase().includes("completed"))) {
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
      const errorMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: `⚠️ Error: ${e.message}`,
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
    
    return (
      <div 
        key={msg.id} 
        onClick={() => {
          if (isSelectionMode && msg.id) {
            setSelectedMessages(prev => 
              prev.includes(msg.id!) ? prev.filter(id => id !== msg.id) : [...prev, msg.id!]
            );
          }
        }}
        className={cn(
          "flex flex-col gap-2 transition-all duration-200", 
          msg.role === 'user' ? "items-end" : "items-start",
          isSelectionMode && "cursor-pointer hover:opacity-80",
          isSelectionMode && isSelected && "ring-2 ring-emerald-500 ring-offset-2 rounded-2xl"
        )}
      >
        <div className={cn(
          "rounded-2xl px-4 py-3 shadow-sm max-w-[85%] break-words overflow-hidden relative group",
          msg.role === 'user' ? "bg-emerald-600 text-white" : "bg-card border border-border text-foreground",
          isSelectionMode && isSelected && "bg-emerald-50 dark:bg-emerald-900/20"
        )}>
          {isSelectionMode && (
            <div className={cn(
              "absolute top-2 right-2 w-4 h-4 rounded-full border-2 flex items-center justify-center",
              isSelected ? "bg-emerald-500 border-indigo-500" : "border-slate-300 dark:border-slate-600"
            )}>
              {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
            </div>
          )}
          
          {msg.role === 'ai' && msg.plan && msg.plan.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-[10px] font-bold text-emerald-500 uppercase tracking-widest">
                  <Database className="w-3 h-3" />
                  <span>Agent Workflow</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePlanVisibility(msg.id || "");
                  }}
                  className="h-6 px-2 text-[9px] font-bold text-muted-foreground hover:text-emerald-500 gap-1"
                >
                  {/* {isPlanVisible ? <XIcon className="w-3 h-3" /> : <Plus className="w-3 h-3" />} */}
                  {isPlanVisible ? "HIDE WORKFLOW" : "SHOW WORKFLOW"}
                </Button>
              </div>
              
              <AnimatePresence>
                {isPlanVisible && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, filter: "blur(10px)" }}
                    animate={{ 
                      opacity: 1, 
                      height: "auto", 
                      filter: "blur(0px)",
                      transition: { 
                        height: { type: "spring", stiffness: 300, damping: 30 },
                        opacity: { duration: 0.2 },
                        filter: { duration: 0.3 }
                      }
                    }}
                    exit={{ 
                      opacity: 0, 
                      height: 0, 
                      filter: "blur(10px)",
                      transition: { 
                        height: { duration: 0.3 },
                        opacity: { duration: 0.2 },
                        filter: { duration: 0.2 }
                      }
                    }}
                    className="overflow-hidden"
                  >
                    <Plan 
                      tasks={msg.plan} 
                      onHide={() => togglePlanVisibility(msg.id || "")}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="mt-4 border-b border-border" />
            </div>
          )}

          {/* NEW: Tool Execution Timeline */}
          {msg.role === 'ai' && msg.plan && msg.plan.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-[10px] font-bold text-blue-500 uppercase tracking-widest">
                  <Terminal className="w-3 h-3" />
                  <span>Tool Activity</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleToolVisibility(msg.id || "");
                  }}
                  className="h-6 px-2 text-[9px] font-bold text-muted-foreground hover:text-blue-500 gap-1"
                >
                  
                </Button>
              </div>
            
              <div className="mt-4 border-b border-border" />
            </div>
          )}

          {renderFormattedContent(msg.content, msg.role === 'user')}

          {/* Show "Edit Details" button if form exists in history */}
          {msg.role === 'ai' && msg.form && !isSelectionMode && (
            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-white/5">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveForm(msg.form);
                  setActiveThreadId(activeThreadId); 
                }}
                className="h-7 px-3 text-[10px] font-bold gap-1.5 border-indigo-500/20 text-indigo-500 hover:bg-indigo-500/5"
              >
                <Pencil className="w-3 h-3" />
                EDIT & PROCESS AGAIN
              </Button>
            </div>
          )}
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
          <strong key={bIdx} className={cn("font-extrabold", isUser ? "text-white" : "text-slate-900 dark:text-white")}>
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
              isUser ? "bg-white/20 text-white" : "bg-slate-100 dark:bg-[#2a2a2d] text-indigo-700 dark:text-indigo-400"
            )}>
              {iPart.slice(1, -1)}
            </code>
          );
        }
        return iPart;
      });
    });
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
          <div key={index} className="my-3.5 rounded-xl border border-border bg-muted/50 overflow-hidden font-mono text-[13px] shadow-md">
            <div className="flex justify-between items-center px-4 py-1.5 bg-muted text-xs text-muted-foreground font-sans border-b border-border select-none font-bold">
              <span className="uppercase text-[10px] tracking-widest">{language || "text"}</span>
              <span className="text-[10px] lowercase font-medium">ready</span>
            </div>
            <pre className="p-4 overflow-x-auto text-foreground/90 leading-relaxed whitespace-pre font-medium">
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
          const headers = rows[0];
          const body = rows.slice(2); // Skip header and separator line

          return (
            <div key={index} className="my-4 overflow-hidden rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#1a1a1e] shadow-sm">
              <div className="flex items-center justify-between px-4 py-2 bg-slate-50 dark:bg-white/5 border-b border-slate-200 dark:border-white/10">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  <TableIcon className="w-3 h-3" />
                  <span>Data Table</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => downloadTableData(rows.filter((_, i) => i !== 1), "sciparser_data")}
                  className="h-6 px-2 text-[9px] font-bold text-indigo-500 hover:bg-indigo-500/10 gap-1"
                >
                  <Download className="w-3 h-3" />
                  DOWNLOAD CSV
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[13px] border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-white/5">
                      {headers.map((h, i) => (
                        <th key={i} className="px-4 py-2.5 font-bold text-slate-700 dark:text-slate-200 border-b border-slate-200 dark:border-white/10">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {body.map((row, ri) => (
                      <tr key={ri} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                        {row.map((cell, ci) => (
                          <td key={ci} className="px-4 py-2.5 text-slate-600 dark:text-slate-300 border-b border-slate-100 dark:border-white/5">{cell}</td>
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
            
            return (
              <p key={lineIdx} className={cn(
                "relative leading-relaxed text-[15px] font-medium font-sans",
                isUser ? "text-white" : (line.includes("--- Execution Summary ---") ? "text-primary mt-4 pt-4 border-t border-border font-bold" : "text-foreground/90")
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
          setSuccess("Browser is not initialized. Start a web task to launch it.");
          setTimeout(() => setSuccess(""), 3000);
          return; // Don't open the panel
        }
      } catch (err) {
        console.error("Failed to check browser session:", err);
        return;
      }
    }
    
    setBrowserActive(isActive);
    setLastManualToggle(Date.now()); // Track manual interaction
  };

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

      {/* Scheduler Configuration Popup */}
      {isSchedulerOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 backdrop-blur-md p-4">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="w-full max-w-4xl max-h-[90vh] bg-white dark:bg-[#0f0f12] rounded-[32px] shadow-2xl border border-slate-200 dark:border-white/5 overflow-hidden flex flex-col"
          >
            {/* Header with Gradient Accent */}
            <div className="relative px-8 py-6 overflow-hidden shrink-0">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500" />
              <div className="flex items-center justify-between relative z-10">
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                      <RefreshCw className="w-4 h-4 text-indigo-500 animate-spin-slow" />
                    </div>
                    <h3 className="font-black text-slate-900 dark:text-white text-lg tracking-tight">
                      Configure Automation
                    </h3>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-medium ml-10">
                    Set up a recurring schedule for your selected tasks.
                  </p>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={() => setIsSchedulerOpen(false)} 
                  className="h-10 w-10 rounded-2xl hover:bg-slate-100 dark:hover:bg-white/5"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </Button>
              </div>
            </div>

            <div className="px-8 pb-8 space-y-6 overflow-y-auto hide-scrollbar">
              {/* Frequency Selection */}
              <div className="space-y-3">
                <label className="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] ml-1">Frequency</label>
                <div className="grid grid-cols-3 gap-3 p-1.5 bg-slate-50 dark:bg-white/5 rounded-2xl border border-slate-100 dark:border-white/5">
                  {['daily', 'weekly', 'monthly'].map((type) => (
                    <button
                      key={type}
                      onClick={() => setScheduleType(type)}
                      className={cn(
                        "py-3 text-[11px] font-black rounded-xl transition-all uppercase tracking-wider",
                        scheduleType === type 
                          ? "bg-white dark:bg-[#1a1a1e] text-indigo-600 dark:text-indigo-400 shadow-sm ring-1 ring-slate-200 dark:ring-white/10" 
                          : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                      )}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Email Input */}
              <div className="space-y-3">
                <label className="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] ml-1">Delivery Email</label>
                <div className="relative group">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-lg bg-slate-100 dark:bg-white/5 flex items-center justify-center group-focus-within:bg-indigo-500/10 transition-colors">
                    <Globe className="w-3 h-3 text-slate-400 group-focus-within:text-indigo-500" />
                  </div>
                  <input
                    type="email"
                    placeholder="example@company.com"
                    value={emailRecipient}
                    onChange={(e) => setEmailRecipient(e.target.value)}
                    className="w-full pl-12 pr-4 py-4 text-sm font-medium rounded-2xl bg-slate-50 dark:bg-white/5 border border-slate-100 dark:border-white/5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400"
                  />
                </div>
              </div>

              {/* Selection Summary Card - Clickable to open Review Popup */}
              <div 
                onClick={() => setIsReviewOpen(true)}
                className="relative group cursor-pointer"
              >
                <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-[24px] blur opacity-0 group-hover:opacity-100 transition duration-500" />
                <div className="relative p-5 rounded-[24px] bg-indigo-50/50 dark:bg-indigo-500/5 border border-indigo-100 dark:border-indigo-500/10 flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">Selection Summary</div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                      Click to review <span className="font-bold text-indigo-500">{selectedMessages.length + selectedTools.length} items</span> in detail.
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-white dark:bg-white/5 flex items-center justify-center shadow-sm border border-indigo-100 dark:border-white/5 group-hover:bg-indigo-500 group-hover:text-white transition-all">
                    <ChevronDown className="w-5 h-5 -rotate-90" />
                  </div>
                </div>
              </div>
            </div>

            {/* Footer with Glass Effect */}
            <div className="px-8 py-6 border-t border-slate-100 dark:border-white/5 bg-slate-50/30 dark:bg-white/2 flex items-center justify-between gap-4 shrink-0">
              <button 
                onClick={() => setIsSchedulerOpen(false)} 
                className="text-xs font-black text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors uppercase tracking-widest"
              >
                Cancel
              </button>
              <Button 
                onClick={handleCreateSchedule}
                disabled={loading}
                className="h-14 px-8 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-black uppercase tracking-[0.15em] shadow-xl shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-70 min-w-[200px]"
              >
                {loading ? (
                  <div className="flex items-center gap-3">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing...</span>
                  </div>
                ) : (
                  "Confirm Schedule"
                )}
              </Button>
            </div>
          </motion.div>
        </div>
      )}

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
                      <div className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-[9px] font-black text-emerald-600 uppercase">{log.status}</div>
                    </div>
                    <div className="space-y-3">
                      <div className="space-y-1.5">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest ml-1">Input</span>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-white dark:bg-black/20 p-3 rounded-xl border border-slate-100 dark:border-white/5 font-mono break-all">
                          {typeof log.tool_input === 'string' ? log.tool_input : JSON.stringify(log.tool_input, null, 2)}
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <span className="text-[9px] font-bold text-emerald-500/70 uppercase tracking-widest ml-1">Output</span>
                        <div className="text-[11px] text-slate-600 dark:text-slate-300 bg-emerald-50/30 dark:bg-emerald-500/5 p-3 rounded-xl border border-emerald-100/30 dark:border-emerald-500/10 font-mono whitespace-pre-wrap">
                          {log.tool_output}
                        </div>
                      </div>
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

      {/* Sidebar */}
      <div 
        className={cn(
          "h-full bg-card border-r border-border flex flex-col transition-all duration-300 z-20 shrink-0",
          isSidebarCollapsed ? "w-0 -translate-x-full overflow-hidden border-r-0" : "w-64"
        )}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-lg tracking-tight text-foreground">
            <Sparkles className="w-5 h-5 text-emerald-500" />
            <span>SciParser AI</span>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => handleNewChat(true)}
            className="hover:bg-muted"
          >
            <Plus className="w-5 h-5" />
          </Button>
        </div>

        {/* Sidebar Search */}
        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-muted border-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-foreground"
            />
          </div>
        </div>

        {/* Sidebar Thread List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
          {/* Navigation Section */}
          <div className="space-y-1 mb-4">
            <div
              onClick={() => handleSwitchView("chat")}
              className={cn(
                "group flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-all text-sm font-bold",
                currentView === "chat"
                  ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e1e24]"
              )}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span>AI Chat Core</span>
            </div>

            <div
              onClick={() => handleSwitchView("schedules")}
              className={cn(
                "group flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-all text-sm font-bold",
                currentView === "schedules"
                  ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e1e24]"
              )}
            >
              <Calendar className="w-4 h-4 shrink-0" />
              <span>Automation Schedules</span>
            </div>
          </div>

          <div className="flex items-center gap-2 px-3 mb-2">
            <div className="h-px flex-1 bg-slate-100 dark:bg-white/5" />
            <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Recent Chats</span>
            <div className="h-px flex-1 bg-slate-100 dark:bg-white/5" />
          </div>

          {filteredThreads.map((t) => {
            const isActive = t.id === activeThreadId;
            return (
              <div
                key={t.id}
                onClick={() => handleSelectThread(t.id)}
                className={cn(
                  "group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm font-medium",
                  isActive 
                    ? "bg-primary/20 text-primary" 
                    : "hover:bg-muted text-muted-foreground hover:text-foreground"
                )}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <MessageSquare className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t.title}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingThreadId(String(t.id));
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-200 dark:hover:bg-[#2f2f3d] rounded transition-opacity"
                >
                  <Trash className="w-3.5 h-3.5 text-slate-400 hover:text-red-500" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Delete Chat Confirmation Modal */}
        {deletingThreadId && (
          <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="w-full max-w-sm bg-white dark:bg-[#1a1a1e] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#2f2f3d] p-6 text-center space-y-4"
            >
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mx-auto">
                <Trash className="w-6 h-6 text-red-500" />
              </div>
              <div className="space-y-2">
                <h3 className="font-bold text-lg text-slate-900 dark:text-white">Delete Chat?</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  This will permanently remove this conversation and all its history.
                </p>
              </div>
              <div className="flex gap-3 pt-2">
                <Button 
                  variant="ghost" 
                  onClick={() => setDeletingThreadId(null)} 
                  className="flex-1 text-xs font-bold"
                >
                  CANCEL
                </Button>
                <Button 
                  onClick={() => handleDeleteThread(deletingThreadId)} 
                  className="flex-1 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-xl"
                >
                  DELETE
                </Button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-border bg-card space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-600 flex items-center justify-center text-white font-bold shadow-lg shadow-emerald-500/20">
              {userProfile?.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold truncate text-foreground tracking-tight">{userProfile?.username}</p>
              <p className="text-[11px] text-muted-foreground truncate font-medium">{userProfile?.email}</p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-1 pt-1">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={toggleTheme}
              className="w-10 h-10 rounded-2xl hover:bg-muted text-muted-foreground transition-all active:scale-90"
            >
              {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={handleLogout} 
              className="w-10 h-10 rounded-2xl text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 transition-all active:scale-90"
            >
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-row overflow-hidden h-full relative">
        {currentView === "schedules" ? (
          <SchedulesPage onBack={() => handleSwitchView("chat")} />
        ) : (
          <>
            {/* Chat Column */}
            <div className="flex-1 flex flex-col h-full min-w-[320px] bg-background">
              
              {/* Chat Header */}
              <div className="h-14 border-b border-border bg-card px-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                    className="hover:bg-muted"
                  >
                    {isSidebarCollapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
                  </Button>
                  <div className="font-semibold text-sm text-foreground">{activeModel}</div>
                </div>

                <div className="flex items-center gap-2">
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
                      handleToggleLiveBrowser(!browserActive);
                      setUserInterruptedBrowser(true); // Stop auto-logic if user interacts
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
              <div 
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-6 space-y-6"
              >
                {messages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-[#1e1e2f] flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                      <Sparkles className="w-6 h-6" />
                    </div>
                    <h2 className="text-xl font-bold">How can I assist you today?</h2>
                    <p className="text-sm text-slate-400">
                      SciParser can browse the web, analyze documents, and run complex multi-agent workflows.
                    </p>
                    <div className="grid grid-cols-2 gap-2 w-full pt-4">
                      <button 
                        onClick={() => sendQuickPrompt("Go to Hacker News and extract top stories")}
                        className="p-3 text-xs font-medium text-left rounded-xl border border-slate-200 dark:border-[#232329] hover:bg-slate-100 dark:hover:bg-[#16161a] transition-colors"
                      >
                        📰 Extract Hacker News
                      </button>
                      <button 
                        onClick={() => sendQuickPrompt("Search for latest AI research papers")}
                        className="p-3 text-xs font-medium text-left rounded-xl border border-slate-200 dark:border-[#232329] hover:bg-slate-100 dark:hover:bg-[#16161a] transition-colors"
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
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Live Execution</div>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => {
                            setShowExecutionPlan(!showExecutionPlan);
                            setUserInterruptedHide(true); // Stop auto-hiding if user interacts
                          }}
                          className="h-6 px-2 text-[9px] font-bold text-indigo-500 hover:bg-indigo-500/10 gap-1"
                        >
                          {showExecutionPlan ? <XIcon className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                          {showExecutionPlan ? "HIDE PLAN" : "SHOW PLAN"}
                        </Button>
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
                      {showExecutionPlan && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="overflow-hidden"
                        >
                          {currentPlan ? (
                            <div className="space-y-3">
                              <Plan 
                                tasks={currentPlan} 
                                thoughts={aiThinking ? [aiThinking] : []} 
                                onHide={() => setShowExecutionPlan(false)}
                              />
                            </div>
                          ) : (
                            <div className="bg-white dark:bg-[#1e1e1e] border border-slate-200 dark:border-[#2f2f2f] rounded-2xl p-5 shadow-sm">
                              <MessageLoading />
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Chat Input Area */}
              <div className="p-4 bg-card border-t border-border">
                <div className="max-w-3xl mx-auto relative flex items-end gap-2 bg-muted border border-border rounded-xl p-2">
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
                    className="hover:bg-muted shrink-0"
                  >
                    <Paperclip className="w-5 h-5 text-muted-foreground" />
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
                    className="flex-1 max-h-48 resize-none bg-transparent border-none focus:outline-none text-sm py-2 px-1 text-foreground"
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
                  onMouseDown={handleMouseDown}
                  className="w-1 bg-slate-200 dark:bg-[#232329] hover:bg-indigo-500 cursor-col-resize transition-colors z-10"
                />
                {/* Browser Panel */}
                <div 
                  ref={browserPanelRef}
                  style={{ width: `${browserPanelWidth}%` }}
                  className="h-full overflow-hidden bg-slate-900 flex flex-col shrink-0"
                >
                  <div className="flex-1 overflow-hidden">
                    <BrowserPreview 
                      frame={browserFrame} 
                      isActive={browserActive} 
                      onClose={() => setBrowserActive(false)} 
                    />
                  </div>
                  
                  {/* Tool Activity Panel below Browser */}
                  <div className="h-1/3 border-t border-slate-800 bg-[#0a0a0c] flex flex-col overflow-hidden">
                    <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between bg-[#111114]">
                      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                        <Code className="w-3 h-3 text-indigo-400" />
                        <span>Tool Execution Log</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {isAiTyping && (
                          <>
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-[9px] text-emerald-500 font-bold uppercase">Live</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div 
                      ref={toolLogsScrollRef}
                      onScroll={handleToolLogsScroll}
                      className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-3"
                    >
                      {toolLogs.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-slate-600 italic">
                          Waiting for tool activity...
                        </div>
                      ) : (
                        toolLogs.map((log, idx) => {
                          const isSelected = selectedTools.includes(log.id || String(idx));
                          return (
                            <div 
                              key={log.id || idx} 
                              onClick={() => {
                                if (isSelectionMode) {
                                  const id = log.id || String(idx);
                                  setSelectedToolIds(prev => 
                                    prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
                                  );
                                }
                              }}
                              className={cn(
                                "flex flex-col gap-1 border-l-2 pl-3 py-1 transition-all cursor-pointer relative",
                                log.status === 'IN_PROGRESS' ? "border-blue-500 bg-blue-500/5" : 
                                log.status === 'SUCCESS' ? "border-emerald-500 bg-emerald-500/5" : "border-red-500 bg-red-500/5",
                                isSelectionMode && isSelected && "bg-indigo-500/10 border-indigo-500"
                              )}
                            >
                              {isSelectionMode && (
                                <div className={cn(
                                  "absolute top-1 right-1 w-3 h-3 rounded-full border flex items-center justify-center",
                                  isSelected ? "bg-indigo-500 border-indigo-500" : "border-slate-600"
                                )}>
                                  {isSelected && <Check className="w-2 h-2 text-white" />}
                                </div>
                              )}
                              <div className="flex items-center justify-between">
                                <span className={cn(
                                  "font-bold",
                                  log.status === 'IN_PROGRESS' ? "text-blue-400" : 
                                  log.status === 'SUCCESS' ? "text-emerald-400" : "text-red-400"
                                )}>
                                  {">"} {log.tool_name}
                                </span>
                                <span className="text-[9px] text-slate-500">
                                  {log.status}
                                </span>
                              </div>
                              <div className="text-slate-400 break-all opacity-70 text-[10px]">
                                IN: {JSON.stringify(log.tool_input)}
                              </div>
                              {log.tool_output && (
                                <div className="text-slate-200 break-words mt-1 bg-white/5 p-1.5 rounded border border-white/5">
                                  OUT: {log.tool_output}
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
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