// ChatPage.tsx
import * as React from "react";
import { Signup1 } from "./signup-1";
import { Button } from "./button";
import { sciparserApi, ChatMessage, UploadedFile, User } from "../../api";
import { useTheme } from "../../App";
import { cn } from "../../../lib/utils";
import { Component as AiLoader } from "./ai-loader";
import { MessageLoading } from "./message-loading";
import { BrowserPreview } from "./browser-preview";
import { 
  Sparkles, User2, Database, RefreshCw, CheckCircle2, 
  BookOpen, MessageSquare, Plus, LogOut, Trash, Pencil, Check, Menu, X, 
  ChevronDown, Globe, Send, PanelLeftClose, PanelLeftOpen, Search, Code, 
  Sun, Moon, FileText, Paperclip, X as XIcon
} from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import Plan, { Task } from "./agent-plan";

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
  
  const [showBrowserPreview, setShowBrowserPreview] = React.useState(false);
  const [preferLiveBrowser, setPreferLiveBrowser] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [voiceEnabled, setVoiceEnabled] = React.useState(false);
  const [isAiTyping, setIsAiTyping] = React.useState(false);
  const [currentPlan, setCurrentPlan] = React.useState<Task[] | null>(null);
  const [toolLogs, setToolLogs] = React.useState<any[]>([]);

  const [activeModel, setActiveModel] = React.useState("SciParser AI Core");
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false);
  const [editingThreadId, setEditingThreadId] = React.useState<string | null>(null);
  const [editingTitleText, setEditingTitleText] = React.useState("");
  const [searchQuery, setSearchQuery] = React.useState("");
  
  // Resizable panel states
  const [browserPanelWidth, setBrowserPanelWidth] = React.useState(50); // percentage
  const [agentPanelHeight, setAgentPanelHeight] = React.useState(200); // pixels
  
  // File upload states
  const [isDraggingFile, setIsDraggingFile] = React.useState(false);
  const [uploadingFiles, setUploadingFiles] = React.useState<string[]>([]);
  
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const browserPanelRef = React.useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = React.useState(false);

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
    if (!browserActive || !activeThreadId) return;

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/sciparser/v1/browser/stream?chat_id=${activeThreadId}&token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'frame') {
          setBrowserFrame(msg.data);
          // Auto-show browser when we get the first frame
          if (!browserActive) setBrowserActive(true);
        } else if (msg.event === 'status') {
          console.log("Browser status:", msg.data);
        } else if (msg.event === 'tool_log') {
          try {
            // The data itself is a JSON string from brain.py
            const toolMsg = JSON.parse(msg.data);
            if (toolMsg.type === 'tool_start') {
              setToolLogs(prev => [...prev, {
                id: uuidv4(),
                tool_name: toolMsg.tool,
                tool_input: toolMsg.args,
                status: 'IN_PROGRESS',
                created_at: new Date().toISOString()
              }]);
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
    if (idStr.startsWith("thread-")) {
      setActiveThreadId(idStr);
      setMessages([]);
      setToolLogs([]); // Clear logs for new thread
      return;
    }

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
    }
  };

  const handleDeleteThread = async (threadId: string | number, e: React.MouseEvent) => {
    e.stopPropagation();
    const idStr = String(threadId);
    
    setThreads(prev => prev.filter(t => String(t.id) !== idStr));
    if (String(activeThreadId) === idStr) {
      handleNewChat();
    }

    if (!idStr.startsWith("thread-")) {
      try {
        await sciparserApi.deleteChatSession(idStr);
      } catch (err) {
        console.warn("Delete failed:", err);
      }
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    const currentThreadId = activeThreadId ? String(activeThreadId) : uuidv4();
    
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
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setTextareaValue("");
    setIsAiTyping(true);
    setToolLogs([]); // Clear tool logs for the new live process

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
      }
    } catch (e: any) {
      console.error("Message sending failed:", e);
      const errorMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: `⚠️ Error: ${e.message}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsAiTyping(false);
    }
  };

  const renderMessage = (msg: ChatMessage) => (
    <div key={msg.id} className={cn("flex flex-col gap-2", msg.role === 'user' ? "items-end" : "items-start")}>
      <div className={cn(
        "rounded-2xl px-4 py-3 shadow-sm max-w-[85%]",
        msg.role === 'user' ? "bg-indigo-600 text-white" : "bg-white dark:bg-[#1e1e1e] border border-slate-200 dark:border-[#2f2f2f]"
      )}>
        {msg.role === 'ai' && msg.plan && msg.plan.length > 0 && (
          <div className="mb-4 pb-4 border-b border-slate-100 dark:border-white/5">
            <Plan tasks={msg.plan} />
          </div>
        )}

        {renderFormattedContent(msg.content)}
      </div>
    </div>
  );

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

  const parseInlineFormatting = (text: string) => {
    const boldParts = text.split(/(\*\*.*?\*\*)/g);
    return boldParts.map((bPart, bIdx) => {
      if (bPart.startsWith("**") && bPart.endsWith("**")) {
        return (
          <strong key={bIdx} className="font-extrabold text-slate-900 dark:text-white">
            {bPart.slice(2, -2)}
          </strong>
        );
      }
      const inlineParts = bPart.split(/(\`.*?\`)/g);
      return inlineParts.map((iPart, iIdx) => {
        if (iPart.startsWith("`") && iPart.endsWith("`")) {
          return (
            <code key={iIdx} className="px-1.5 py-0.5 mx-0.5 rounded bg-slate-100 dark:bg-[#2a2a2d] text-indigo-700 dark:text-indigo-400 font-mono text-[13px] font-bold">
              {iPart.slice(1, -1)}
            </code>
          );
        }
        return iPart;
      });
    });
  };

  const renderFormattedContent = (content: string) => {
    if (!content) return null;
    const parts = content.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        const lines = part.slice(3, -3).trim().split("\n");
        const language = lines[0] && !lines[0].includes(" ") ? lines[0] : "";
        const code = language ? lines.slice(1).join("\n") : lines.join("\n");
        
        return (
          <div key={index} className="my-3.5 rounded-xl border border-slate-200 dark:border-[#2f2f2f] bg-slate-50 dark:bg-[#1e1e1e] overflow-hidden font-mono text-[13px] shadow-md">
            <div className="flex justify-between items-center px-4 py-1.5 bg-slate-100 dark:bg-[#171717] text-xs text-slate-500 dark:text-slate-400 font-sans border-b border-slate-200 dark:border-white/5 select-none font-bold">
              <span className="uppercase text-[10px] tracking-widest">{language || "text"}</span>
              <span className="text-[10px] lowercase font-medium">ready</span>
            </div>
            <pre className="p-4 overflow-x-auto text-slate-850 dark:text-slate-200 leading-relaxed whitespace-pre font-medium">
              {code}
            </pre>
          </div>
        );
      }
      
      const lines = part.split("\n");
      return (
        <div key={index} className="space-y-2.5">
          {lines.map((line, lineIdx) => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return <div key={lineIdx} className="h-1" />;
            
            if (trimmedLine.startsWith("- ") || trimmedLine.startsWith("* ") || trimmedLine.startsWith("• ")) {
              const listContent = trimmedLine.replace(/^[-*•]\s+/, "");
              return (
                <li key={lineIdx} className="ml-5 list-disc leading-relaxed text-slate-800 dark:text-[#ececec] pr-2">
                  {parseInlineFormatting(listContent)}
                </li>
              );
            }
            
            const numMatch = trimmedLine.match(/^(\d+)\.\s+(.*)/);
            if (numMatch) {
              const listContent = numMatch[2];
              return (
                <li key={lineIdx} className="ml-5 list-decimal leading-relaxed text-slate-800 dark:text-[#ececec] pr-2" style={{ listStyleType: "decimal" }}>
                  {parseInlineFormatting(listContent)}
                </li>
              );
            }
            
            return (
              <p key={lineIdx} className="relative leading-relaxed text-slate-800 dark:text-[#ececec] text-[15px] font-medium font-sans">
                {parseInlineFormatting(line)}
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

  const handleToggleLiveBrowser = (isActive: boolean) => {
    setBrowserActive(isActive);
  };

  const handleNewChat = () => {
    const newId = uuidv4(); 
    const newThread: Thread = {
      id: newId,
      title: "New Chat",
      messages: [],
      uploads: [],
      createdAt: new Date().toISOString(),
    };
    setThreads([newThread, ...threads]);
    setActiveThreadId(newId);
    setMessages([]);
    setBrowserActive(false);
  };

  // --- Authentication Screen ---
  if (!userProfile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-[#0a0a0c] p-4">
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
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 dark:bg-[#0f0f11] text-slate-900 dark:text-slate-100 font-sans">
      {isNavigating && <AiLoader text={loaderText} />}

      {/* Sidebar */}
      <div 
        className={cn(
          "h-full bg-white dark:bg-[#16161a] border-r border-slate-200 dark:border-[#232329] flex flex-col transition-all duration-300 z-20 shrink-0",
          isSidebarCollapsed ? "w-0 -translate-x-full overflow-hidden border-r-0" : "w-64"
        )}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-200 dark:border-[#232329] flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-lg tracking-tight">
            <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>SciParser AI</span>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={handleNewChat}
            className="hover:bg-slate-100 dark:hover:bg-[#232329]"
          >
            <Plus className="w-5 h-5" />
          </Button>
        </div>

        {/* Sidebar Search */}
        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-slate-100 dark:bg-[#1e1e24] border-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Sidebar Thread List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
          {filteredThreads.map((t) => {
            const isActive = t.id === activeThreadId;
            return (
              <div
                key={t.id}
                onClick={() => handleSelectThread(t.id)}
                className={cn(
                  "group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm font-medium",
                  isActive 
                    ? "bg-indigo-50 dark:bg-[#232335] text-indigo-600 dark:text-indigo-400" 
                    : "hover:bg-slate-100 dark:hover:bg-[#1e1e24] text-slate-600 dark:text-slate-400"
                )}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <MessageSquare className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t.title}</span>
                </div>
                <button
                  onClick={(e) => handleDeleteThread(t.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-200 dark:hover:bg-[#2f2f3d] rounded transition-opacity"
                >
                  <Trash className="w-3.5 h-3.5 text-slate-400 hover:text-red-500" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-[#232329] space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold">
              {userProfile.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold truncate">{userProfile.username}</p>
              <p className="text-xs text-slate-400 truncate">{userProfile.email}</p>
            </div>
          </div>
          <div className="flex items-center justify-between pt-2">
            <Button variant="ghost" size="icon" onClick={toggleTheme}>
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
            <Button variant="ghost" size="icon" onClick={handleLogout} className="text-red-500 hover:text-red-600">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-row overflow-hidden h-full relative">
        
        {/* Chat Column */}
        <div className="flex-1 flex flex-col h-full min-w-[320px] bg-slate-50 dark:bg-[#0f0f11]">
          
          {/* Chat Header */}
          <div className="h-14 border-b border-slate-200 dark:border-[#232329] bg-white dark:bg-[#16161a] px-4 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-3">
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                className="hover:bg-slate-100 dark:hover:bg-[#232329]"
              >
                {isSidebarCollapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
              </Button>
              <div className="font-semibold text-sm">{activeModel}</div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={browserActive ? "default" : "outline"}
                size="sm"
                onClick={() => handleToggleLiveBrowser(!browserActive)}
                className={cn(
                  "gap-1.5 text-xs font-semibold",
                  browserActive && "bg-emerald-600 hover:bg-emerald-700 text-white border-none"
                )}
              >
                <Globe className="w-4 h-4" />
                <span>Live Browser</span>
              </Button>
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
              <div className="mt-4 max-w-2xl">
                {currentPlan ? (
                  <Plan tasks={currentPlan} />
                ) : (
                  <div className="bg-white dark:bg-[#1e1e1e] border border-slate-200 dark:border-[#2f2f2f] rounded-2xl p-5 shadow-sm">
                    <MessageLoading />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Chat Input Area */}
          <div className="p-4 bg-white dark:bg-[#16161a] border-t border-slate-200 dark:border-[#232329]">
            <div className="max-w-3xl mx-auto relative flex items-end gap-2 bg-slate-50 dark:bg-[#1e1e24] border border-slate-200 dark:border-[#2f2f3d] rounded-xl p-2">
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
                className="hover:bg-slate-200 dark:hover:bg-[#2f2f3d] shrink-0"
              >
                <Paperclip className="w-5 h-5 text-slate-400" />
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
                className="flex-1 max-h-48 resize-none bg-transparent border-none focus:outline-none text-sm py-2 px-1"
              />
              <Button
                onClick={() => handleSendMessage(textareaValue)}
                disabled={!textareaValue.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white shrink-0"
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
                <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-2">
                  {toolLogs.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-slate-600 italic">
                      Waiting for tool activity...
                    </div>
                  ) : (
                    toolLogs.map((log, idx) => (
                      <div key={log.id || idx} className="flex flex-col gap-1 border-l-2 border-indigo-500/30 pl-3 py-1">
                        <div className="flex items-center justify-between">
                          <span className="text-indigo-400 font-bold">
                            {">"} {log.tool_name}
                          </span>
                          <span className="text-[9px] text-slate-500">
                            {new Date(log.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="text-slate-300 break-all opacity-80">
                          {JSON.stringify(log.tool_input)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        )}

      </div>
    </div>
  );
};

export default ChatPage;