// ChatPage.tsx
import * as React from "react";
import logoLight from "@/assets/logo-light.png";
import logoDark from "@/assets/logo-dark.png";
import atomIcon from "@/assets/atom-icon.png";
import { Signup1 } from "./signup-1";
import { Button } from "./button";
import { sciparserApi, ChatMessage, UploadedFile, User } from "../../api";
import { DEFAULT_CDP_URL, wsUrl } from "../../config";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { Component as AiLoader } from "./ai-loader";
import { MessageLoading } from "./message-loading";
import { BrowserPreview } from "./browser-preview";
import { SchedulesPage } from "./schedules-page";
import { SettingsPage } from "./settings-page";
import { ProcessingPanel } from "./processing-panel";
import { PremiumScheduler } from "./premium-scheduler";
import {
  Sparkles,
  User2,
  Database,
  RefreshCw,
  CheckCircle2,
  BookOpen,
  MessageSquare,
  Plus,
  LogOut,
  Trash,
  Pencil,
  Check,
  Menu,
  X,
  ChevronDown,
  Globe,
  Send,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Code,
  Terminal,
  Sun,
  Moon,
  FileText,
  Paperclip,
  X as XIcon,
  Loader2,
  Download,
  Table as TableIcon,
  Calendar,
  Clock,
  Camera,
  Link,
  Copy,
  Shield,
  Eye,
  EyeOff,
  Settings,
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
  const [userProfile, setUserProfile] = React.useState<UserProfile | null>(
    null,
  );
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
  const [activeThreadId, setActiveThreadId] = React.useState<
    string | undefined
  >(undefined);
  const [browserActive, setBrowserActive] = React.useState(false);
  const [browserFrame, setBrowserFrame] = React.useState<string | null>(null);
  const [activeBrowserEngine, setActiveBrowserEngine] = React.useState<"camoufox" | "chrome" | null>(null);
  const [mousePos, setMousePos] = React.useState<{ x: number; y: number; event: string; vpW: number; vpH: number } | null>(null);
  const [lastManualToggle, setLastManualToggle] = React.useState<number>(0);
  const [browserBlink, setBrowserBlink] = React.useState<
    "green" | "red" | null
  >(null);
  const [userInterruptedBrowser, setUserInterruptedBrowser] =
    React.useState(false);
  const isFirstFrame = React.useRef<boolean>(true);

  const [showBrowserPreview, setShowBrowserPreview] = React.useState(false);
  const [preferLiveBrowser, setPreferLiveBrowser] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [voiceEnabled, setVoiceEnabled] = React.useState(false);
  const [isAiTyping, setIsAiTyping] = React.useState(false);
  const [currentPlan, setCurrentPlan] = React.useState<Task[] | null>(null);
  const [toolLogs, setToolLogs] = React.useState<any[]>([]);
  const [aiThinking, setAiThinking] = React.useState<string | null>(null);
  const [taskThoughts, setTaskThoughts] = React.useState<
    Record<string, string>
  >({});
  const [showExecutionPlan, setShowExecutionPlan] = React.useState(true);
  const [userInterruptedHide, setUserInterruptedHide] = React.useState(false);
  const [visiblePlans, setVisiblePlans] = React.useState<
    Record<string, boolean>
  >({});
  const [visibleTools, setVisibleTools] = React.useState<
    Record<string, boolean>
  >({});

  // Sidebar auto-collapse refs
  const sidebarAutoCollapsedRef = React.useRef(false);
  const sidebarUserInteractedRef = React.useRef(false);
  const prevBrowserActiveRef = React.useRef(false);

  const [agentHistory, setAgentHistory] = React.useState<any[]>([]);

  // Proxy state
  const [proxyActive, setProxyActive] = React.useState(false);
  const [proxyUrlMasked, setProxyUrlMasked] = React.useState<string | null>(null);
  const [showProxyModal, setShowProxyModal] = React.useState(false);
  const [proxyInput, setProxyInput] = React.useState("");
  const [proxySaving, setProxySaving] = React.useState(false);
  const [proxyDeleting, setProxyDeleting] = React.useState(false);
  const [proxyError, setProxyError] = React.useState<string | null>(null);
  const [proxyTesting, setProxyTesting] = React.useState(false);
  const [proxyTestResult, setProxyTestResult] = React.useState<string | null>(null);
  const [proxyInputVisible, setProxyInputVisible] = React.useState(false);

  // Camoufox fallback warning banner
  const [camoufoxFallbackWarning, setCamoufoxFallbackWarning] = React.useState(false);

  // CDP (Connect Your Browser) state
  const [cdpConnected, setCdpConnected] = React.useState(false);
  const [cdpConnectedUrl, setCdpConnectedUrl] = React.useState<string | null>(null);
  const [showCdpModal, setShowCdpModal] = React.useState(false);
  const [cdpUrlInput, setCdpUrlInput] = React.useState(DEFAULT_CDP_URL);
  const [cdpConnecting, setCdpConnecting] = React.useState(false);
  const [cdpError, setCdpError] = React.useState<string | null>(null);
  const [cdpCopied, setCdpCopied] = React.useState(false);

  const togglePlanVisibility = (msgId: string) => {
    setVisiblePlans((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const toggleToolVisibility = (msgId: string) => {
    setVisibleTools((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const [activeModel, setActiveModel] = React.useState("SciParser AI Core");
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false);
  const [editingThreadId, setEditingThreadId] = React.useState<string | null>(
    null,
  );
  const [editingTitleText, setEditingTitleText] = React.useState("");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [deletingThreadId, setDeletingThreadId] = React.useState<string | null>(
    null,
  );

  // Navigation State
  const [currentView, setCurrentView] = React.useState<"chat" | "schedules" | "settings">(
    "chat",
  );

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
  const [sidebarWidth, setSidebarWidth] = React.useState(300); // pixels

  // Refs
  const sidebarResizeRef = React.useRef<{
    startX: number;
    startWidth: number;
  } | null>(null);
  const lastBrowserFrameRef = React.useRef<string | null>(null);

  // File upload states
  const [isDraggingFile, setIsDraggingFile] = React.useState(false);
  const [uploadingFiles, setUploadingFiles] = React.useState<string[]>([]);

  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const toolLogsScrollRef = React.useRef<HTMLDivElement>(null);
  // Tracks whether the user has scrolled away from the bottom of the chat
  const userScrolledUpRef = React.useRef(false);
  const browserPanelRef = React.useRef<HTMLDivElement>(null);
  const [resizingPanel, setResizingPanel] = React.useState<"browser" | null>(null);
  const [isAtBottom, setIsAtBottom] = React.useState(true);

  // Handle tool logs auto-scroll
  const handleToolLogsScroll = () => {
    if (toolLogsScrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } =
        toolLogsScrollRef.current;
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
      const latestPlanLog = [...(agentLogsRes || [])]
        .reverse()
        .find((log: any) => {
          const output = normalizeJsonValue(log.output_data);
          return (
            Array.isArray(output) || (output && typeof output === "object")
          );
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
        behavior: "smooth",
      });
    }
  }, [toolLogs, aiThinking, isAtBottom]);

  // File handling functions
  const handleFileDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingFile(false);

    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      setUploadingFiles((prev) => [...prev, file.name]);
      await handleFileUploaded(file.name, file.size, file.type);
      setUploadingFiles((prev) => prev.filter((name) => name !== file.name));
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      for (const file of files) {
        setUploadingFiles((prev) => [...prev, file.name]);
        await handleFileUploaded(file.name, file.size, file.type);
        setUploadingFiles((prev) => prev.filter((name) => name !== file.name));
      }
    }
  };

  // Resizable panel handlers
  const handleBrowserResizeStart = (e: React.MouseEvent) => {
    setResizingPanel("browser");
    e.preventDefault();
  };


  const handleSidebarMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    sidebarResizeRef.current = { startX: e.clientX, startWidth: sidebarWidth };
    const onMouseMove = (ev: MouseEvent) => {
      if (!sidebarResizeRef.current) return;
      const delta = ev.clientX - sidebarResizeRef.current.startX;
      const next = Math.max(
        200,
        Math.min(520, sidebarResizeRef.current.startWidth + delta),
      );
      setSidebarWidth(next);
    };
    const onMouseUp = () => {
      sidebarResizeRef.current = null;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingPanel) return;

      if (resizingPanel === "browser" && browserPanelRef.current) {
        const containerRect =
          browserPanelRef.current.parentElement?.getBoundingClientRect();
        if (!containerRect) return;
        const newWidth =
          100 - ((e.clientX - containerRect.left) / containerRect.width) * 100;
        if (newWidth > 10 && newWidth < 90) {
          setBrowserPanelWidth(Math.round(newWidth));
        }
      }
    };

    const handleMouseUp = () => {
      setResizingPanel(null);
    };

    if (resizingPanel) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "default";
    };
  }, [resizingPanel]);

  React.useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Auto-collapse sidebar when browser opens; restore when it closes
  React.useEffect(() => {
    if (isMobile) return;
    const wasActive = prevBrowserActiveRef.current;
    prevBrowserActiveRef.current = browserActive;

    if (browserActive && !wasActive) {
      // Browser just opened
      if (!isSidebarCollapsed && !sidebarUserInteractedRef.current) {
        setIsSidebarCollapsed(true);
        sidebarAutoCollapsedRef.current = true;
      }
    } else if (!browserActive && wasActive) {
      // Browser just closed
      if (
        sidebarAutoCollapsedRef.current &&
        !sidebarUserInteractedRef.current
      ) {
        setIsSidebarCollapsed(false);
        sidebarAutoCollapsedRef.current = false;
      }
    }
  }, [browserActive, isMobile]);

  React.useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      fetchUserProfile(token).catch((err) => {
        console.error("Failed to load user profile:", err);
        localStorage.removeItem("access_token");
      });
    }
  }, []);

  // Load proxy + CDP status once user profile is available
  React.useEffect(() => {
    if (!userProfile) return;
    sciparserApi.getProxyStatus().then((s) => {
      setProxyActive(s.active);
      setProxyUrlMasked(s.proxy_url_masked);
    }).catch(() => {});
    sciparserApi.getCdpStatus().then((s) => {
      setCdpConnected(s.connected);
      setCdpConnectedUrl(s.cdp_url);
      if (s.cdp_url) setCdpUrlInput(s.cdp_url);
    }).catch(() => {});
    sciparserApi.getBrowserEngine().then((r) => {
      setActiveBrowserEngine((r.engine as "camoufox" | "chrome") || "camoufox");
    }).catch(() => {});
  }, [userProfile]);

  const handleSaveProxy = async () => {
    if (!proxyInput.trim()) return;
    setProxySaving(true);
    setProxyError(null);
    setProxyTestResult(null);
    try {
      await sciparserApi.setProxy(proxyInput.trim());
      const s = await sciparserApi.getProxyStatus();
      setProxyActive(s.active);
      setProxyUrlMasked(s.proxy_url_masked);
      setProxyInput("");
      setShowProxyModal(false);
    } catch (err: any) {
      setProxyError(err.message || "Failed to save proxy");
    } finally {
      setProxySaving(false);
    }
  };

  const handleDeleteProxy = async () => {
    setProxyDeleting(true);
    setProxyError(null);
    try {
      await sciparserApi.deleteProxy();
      setProxyActive(false);
      setProxyUrlMasked(null);
      setProxyInput("");
      setProxyTestResult(null);
    } catch (err: any) {
      setProxyError(err.message || "Failed to remove proxy");
    } finally {
      setProxyDeleting(false);
    }
  };

  const handleTestProxy = async () => {
    setProxyTesting(true);
    setProxyError(null);
    setProxyTestResult(null);
    try {
      const res = await sciparserApi.testProxy(proxyInput.trim() || undefined);
      setProxyTestResult(`✓ Exit IP: ${res.exit_ip}`);
    } catch (err: any) {
      setProxyError(err.message || "Proxy test failed");
    } finally {
      setProxyTesting(false);
    }
  };

  const handleConnectCdp = async () => {
    setCdpConnecting(true);
    setCdpError(null);
    try {
      await sciparserApi.connectCdp(cdpUrlInput);
      setCdpConnected(true);
      setCdpConnectedUrl(cdpUrlInput);
      setShowCdpModal(false);
    } catch (err: any) {
      setCdpError(err.message || "Failed to connect");
    } finally {
      setCdpConnecting(false);
    }
  };

  const handleDisconnectCdp = async () => {
    try {
      await sciparserApi.disconnectCdp();
    } catch (_) {}
    setCdpConnected(false);
    setCdpConnectedUrl(null);
    setCdpUrlInput(DEFAULT_CDP_URL);
  };

  const handleCdpCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCdpCopied(true);
      setTimeout(() => setCdpCopied(false), 1500);
    });
  };

  // Re-enable auto-scroll whenever the active thread changes (thread switch or new chat)
  React.useEffect(() => {
    userScrolledUpRef.current = false;
  }, [activeThreadId]);

  // Detect when user manually scrolls — pause auto-scroll while they read up
  const handleChatScroll = React.useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    // Re-enable auto-scroll once user scrolls back within 80 px of the bottom
    userScrolledUpRef.current = distFromBottom > 80;
  }, []);

  React.useEffect(() => {
    // Don't hijack the scroll position while the user is reading up
    if (userScrolledUpRef.current) return;
    if (scrollRef.current) {
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(() => {
        if (scrollRef.current && !userScrolledUpRef.current) {
          scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth",
          });
        }
      });
    }
  }, [messages, isAiTyping, currentPlan, toolLogs]);

  // Real-Time WebSocket stream connection for CDP frame screencasts
  React.useEffect(() => {
    if (!userProfile?.user_id) return;
    if (!activeThreadId) return;
    isFirstFrame.current = true;

    const token = localStorage.getItem("access_token");
    const buildUrl = () =>
      wsUrl(`/sciparser/v1/browser/stream?chat_id=${activeThreadId}&token=${token}`);

    let ws: WebSocket;
    let heartbeatTimer: ReturnType<typeof setInterval>;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let destroyed = false;

    const handleMessage = (event: MessageEvent) => {
      requestAnimationFrame(() => {
        try {
          const msg = JSON.parse(event.data);
          const eventType = msg.event || (msg.frame ? "frame" : null);
          const rawData = msg.data || msg.frame;

          if (eventType === "frame") {
            let frameData;
            try {
              frameData =
                typeof rawData === "string" ? JSON.parse(rawData) : rawData;
            } catch {
              frameData = { frame: rawData };
            }

            const frameChatId = frameData.chat_id
              ? String(frameData.chat_id)
              : null;
            const activeId = activeThreadId ? String(activeThreadId) : null;
            if (frameChatId && activeId && frameChatId !== activeId) {
              console.log(
                "[BrowserStream] frame dropped — chat_id mismatch:",
                frameChatId,
                "vs active:",
                activeId,
              );
              return;
            }

            let actualFrame = frameData.frame;
            if (typeof actualFrame === "object" && actualFrame !== null) {
              actualFrame =
                actualFrame.data ||
                actualFrame.text ||
                JSON.stringify(actualFrame);
            }
            if (!actualFrame && typeof rawData === "string") {
              try {
                const parsedRaw = JSON.parse(rawData);
                actualFrame =
                  parsedRaw.frame ||
                  parsedRaw.screenshot ||
                  parsedRaw.data ||
                  parsedRaw.image;
              } catch {
                /* ignore */
              }
            }

            console.log(
              "[BrowserStream] frame event — length:",
              actualFrame?.length ?? 0,
              "chat_id:",
              frameChatId,
            );

            if (actualFrame) {
              setBrowserFrame(actualFrame);
              lastBrowserFrameRef.current = actualFrame;
              if (isFirstFrame.current && !userInterruptedBrowser) {
                isFirstFrame.current = false;
                setBrowserBlink("green");
                setBrowserActive(true);
                setTimeout(() => setBrowserBlink(null), 1500);
              }
            }
          } else if (eventType === "mouse") {
            try {
              const md = typeof rawData === "string" ? JSON.parse(rawData) : rawData;
              const frameChatId = md.chat_id ? String(md.chat_id) : null;
              const activeId = activeThreadId ? String(activeThreadId) : null;
              if (!frameChatId || !activeId || frameChatId === activeId) {
                setMousePos({
                  x: Number(md.x ?? 0),
                  y: Number(md.y ?? 0),
                  event: md.event || "move",
                  vpW: Number(md.vpW ?? 1280),
                  vpH: Number(md.vpH ?? 800),
                });
              }
            } catch {
              /* ignore */
            }
          } else if (eventType === "tool_log") {
            try {
              const toolMsg =
                typeof rawData === "string" ? JSON.parse(rawData) : rawData;
              if (toolMsg.type === "tool_start") {
                setToolLogs((prev) => {
                  if (prev.some((log) => log.id === toolMsg.tool_call_id))
                    return prev;
                  return [
                    ...prev,
                    {
                      id: toolMsg.tool_call_id || uuidv4(),
                      tool_name: toolMsg.tool,
                      tool_input: toolMsg.args,
                      status: "IN_PROGRESS",
                      created_at: new Date().toISOString(),
                    },
                  ];
                });
              } else if (toolMsg.type === "tool_output") {
                setToolLogs((prev) =>
                  prev.map((log) =>
                    log.id === toolMsg.tool_call_id
                      ? {
                          ...log,
                          status: toolMsg.status,
                          tool_output: toolMsg.output,
                          error_message: toolMsg.error,
                        }
                      : log,
                  ),
                );
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

    const connect = () => {
      if (destroyed) return;
      ws = new WebSocket(buildUrl());

      ws.onopen = () => {
        console.log("Browser stream connected for", activeThreadId);
        clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 20000);
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        clearInterval(heartbeatTimer);
        setMousePos(null);
        console.log("Browser stream disconnected — reconnecting in 3s");
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      destroyed = true;
      clearInterval(heartbeatTimer);
      clearTimeout(reconnectTimer);
      ws?.close();
      setMousePos(null);
    };
  }, [activeThreadId, userProfile?.user_id]);

  // WebSocket for Live Agent Plan (Analysis -> Strategy -> Execution)
  React.useEffect(() => {
    if (!activeThreadId) {
      setCurrentPlan(null);
      return;
    }

    const token = localStorage.getItem("access_token");
    const buildUrl = () =>
      wsUrl(`/sciparser/v1/ws/plan/${activeThreadId}?token=${token}`);

    let ws: WebSocket;
    let heartbeatTimer: ReturnType<typeof setInterval>;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;
      ws = new WebSocket(buildUrl());

      ws.onopen = () => {
        console.log("Plan stream connected for", activeThreadId);
        clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "plan_update") {
            setCurrentPlan(msg.data);
            // Only mark as typing if the plan has a task that is actually still running.
            // Rehydrated plans from stopped/completed runs must not restart the polling loop.
            const stillRunning = Array.isArray(msg.data) && msg.data.some(
              (t: any) => t.status === "in-progress" || t.status === "running" || t.status === "pending"
            );
            if (stillRunning) setIsAiTyping(true);
          } else if (msg.type === "notification" && msg.notification_type === "camoufox_fallback") {
            setCamoufoxFallbackWarning(true);
          } else if (msg.type === "thought_update") {
            setAiThinking(msg.data);
            // Associate thought with the currently running task
            setCurrentPlan((prev) => {
              if (!prev) return prev;
              const active = prev.find(
                (t) => t.status === "in-progress" || t.status === "running",
              );
              if (active) {
                setTaskThoughts((th) => ({ ...th, [active.id]: msg.data }));
              }
              return prev;
            });
          }
        } catch {
          /* ignore non-JSON keep-alive responses */
        }
      };

      ws.onclose = () => {
        clearInterval(heartbeatTimer);
        console.log("Plan stream disconnected — reconnecting in 3s");
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      destroyed = true;
      clearInterval(heartbeatTimer);
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [activeThreadId]);

  // Tool logs are delivered in real-time via the browser WebSocket stream (tool_log events).
  // HTTP polling was removed — it was redundant and caused 5-10 extra requests/second.

  const MIN_TEXTAREA_H = 44; // ~1 row
  const MAX_TEXTAREA_H = 160; // ~4 rows

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const clamped = Math.min(
      Math.max(el.scrollHeight, MIN_TEXTAREA_H),
      MAX_TEXTAREA_H,
    );
    el.style.height = `${clamped}px`;
    el.style.overflowY = el.scrollHeight > MAX_TEXTAREA_H ? "auto" : "hidden";
  };

  // Keep height in sync whenever value changes (covers programmatic clears too)
  React.useEffect(() => {
    adjustHeight();
  }, [textareaValue]);

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
        createdAt: s.createdAt || new Date().toISOString(),
      }));

      setThreads(loadedThreads);

      const latestThreadId = loadedThreads[0].id;
      setActiveThreadId(latestThreadId);

      try {
        const historyData = await sciparserApi.getChatHistory(latestThreadId);
        if (historyData && historyData.messages) {
          setMessages(historyData.messages);
          setThreads((prev) =>
            prev.map((t) =>
              t.id === latestThreadId
                ? { ...t, messages: historyData.messages }
                : t,
            ),
          );
        }
        await loadExecutionLogs(latestThreadId);
      } catch (historyErr: any) {
        console.warn(
          `Could not load history for thread ${latestThreadId}:`,
          historyErr,
        );
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
        const res = await sciparserApi.signin(
          formData.username,
          formData.password,
        );
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
        await sciparserApi.signup(
          formData.username,
          formData.email,
          formData.password,
        );
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
        setThreads((prev) => prev.filter((t) => t.id !== idStr));
        handleNewChat();
      }
    } finally {
      setTimeout(() => setIsNavigating(false), 500);
    }
  };

  const handleDeleteThread = async (
    threadId: string | number,
    e?: React.MouseEvent,
  ) => {
    if (e) e.stopPropagation();
    const idStr = String(threadId);

    try {
      setIsNavigating(true);
      setLoaderText("Deleting Chat");

      // 1. Call API to delete from database
      await sciparserApi.deleteChatSession(idStr);

      // 2. Update local state
      const updatedThreads = threads.filter((t) => String(t.id) !== idStr);
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
    if (
      !force &&
      messages.length === 0 &&
      activeThreadId &&
      String(activeThreadId).startsWith("thread-")
    ) {
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
    setThreads((prev) => [newThread, ...prev]);
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
        createdAt: new Date().toISOString(),
      };
      setThreads((prev) => [newThread, ...prev]);
    }

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
      form: undefined,
    };

    setMessages((prev) => [...prev, userMsg]);
    userScrolledUpRef.current = false; // always jump to bottom for own messages
    setTextareaValue("");
    setIsAiTyping(true);
    setShowExecutionPlan(true); // Always show when new process starts
    setUserInterruptedHide(false); // Reset interruption flag
    setUserInterruptedBrowser(false); // Reset browser interruption flag
    isFirstFrame.current = true; // Reset for new message
    setToolLogs([]); // Clear tool logs for the new live process
    setAiThinking(null); // Clear thinking for new process
    setCurrentPlan(null); // Clear old plan steps immediately
    setTaskThoughts({}); // Clear old per-task reasoning immediately
    // Refresh the active engine badge so it reflects what the backend will actually use
    sciparserApi.getBrowserEngine().then((r) => {
      setActiveBrowserEngine((r.engine as "camoufox" | "chrome") || "camoufox");
    }).catch(() => {});

    try {
      const response = await sciparserApi.sendChatMessage(
        text,
        [],
        preferLiveBrowser,
        currentThreadId,
      );

      const aiMsg = response.message;
      const responsePlan = response.plan || aiMsg?.plan;
      if (responsePlan && aiMsg) {
        aiMsg.plan = responsePlan;
        setCurrentPlan(responsePlan);
      }

      if (aiMsg) {
        const hasScreenshotTool = toolLogs.some((l: any) =>
          l.tool_name?.toLowerCase().includes("screenshot"),
        );
        const contentMentionsScreenshot = /screenshot/i.test(
          aiMsg.content || "",
        );
        const msgToAdd: ChatMessage = { ...aiMsg };
        if (
          (hasScreenshotTool || contentMentionsScreenshot) &&
          lastBrowserFrameRef.current
        ) {
          msgToAdd.screenshots = [lastBrowserFrameRef.current];
        }
        setMessages((prev) => [...prev, msgToAdd]);
        setThreads((prev) =>
          prev.map((t) =>
            t.id === currentThreadId
              ? { ...t, messages: [...t.messages, userMsg, msgToAdd] }
              : t,
          ),
        );

        // --- NEW: Auto-hide execution plan if task completed successfully ---
        const contentLower = (aiMsg.content || "").toLowerCase();
        if (
          !userInterruptedHide &&
          (contentLower.includes("successfully") ||
            contentLower.includes("completed"))
        ) {
          setTimeout(() => {
            if (!userInterruptedHide) {
              setShowExecutionPlan(false);
            }
          }, 3000);
        }

        // --- NEW: Auto-hide browser if task completed successfully ---
        // Use word-boundary check: "unsuccessful" must NOT trigger this
        const isActualSuccess =
          /\bsuccessfully\b/.test(contentLower) &&
          !contentLower.includes("unsuccessful");
        if (
          !userInterruptedBrowser &&
          (isActualSuccess || /\btask completed\b/.test(contentLower))
        ) {
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
        form: undefined,
      };
      setMessages((prev) => [...prev, errorMsg]);
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

  const handleResetSession = async () => {
    if (!activeThreadId) return;
    try {
      await sciparserApi.resetSessionState(activeThreadId);
    } catch (e) {
      console.error("Failed to reset session:", e);
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
    const isPlanVisible =
      visiblePlans[msg.id || ""] ??
      (msg.role === "ai" && msg.plan && msg.plan.length > 0);
    const isUser = msg.role === "user" || msg.role === "human";

    return (
      <div
        key={msg.id || `msg-${msg.timestamp}-${Math.random()}`}
        className={cn(
          "flex flex-col gap-4 transition-all duration-300",
          isUser ? "items-end" : "items-start",
          isSelectionMode && "cursor-pointer hover:opacity-80",
        )}
        onClick={() => {
          if (isSelectionMode && msg.id) {
            setSelectedMessages((prev) =>
              prev.includes(msg.id)
                ? prev.filter((id) => id !== msg.id)
                : [...prev, msg.id],
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
                <span className="text-[10px] font-black text-foreground uppercase tracking-[0.2em]">
                  Execution Trace
                </span>
              </div>
              <div className="h-px flex-1 bg-border" />
            </div>
            <Plan tasks={msg.plan} />
          </div>
        )}

        <div
          className={cn(
            "group relative flex gap-4 max-w-[85%] transition-all duration-300",
            isUser ? "flex-row-reverse" : "flex-row",
          )}
        >
          {/* Selection Checkbox Overlay */}
          {isSelectionMode && msg.id && (
            <div
              className={cn(
                "absolute -top-2 -right-2 z-10 h-6 w-6 rounded-full border-2 flex items-center justify-center transition-all shadow-lg",
                isSelected
                  ? "bg-indigo-600 border-indigo-500 text-white"
                  : "bg-background border-border text-transparent",
              )}
            >
              <Check className="h-3.5 w-3.5" />
            </div>
          )}

          {/* Avatar */}
          <div
            className={cn(
              "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-lg transition-transform duration-300 group-hover:scale-110",
              isUser
                ? "bg-emerald-600 text-white"
                : "bg-muted border border-border text-foreground",
            )}
          >
            {isUser ? (
              <User2 className="w-4 h-4" />
            ) : (
              <img src={atomIcon} alt="SciParser" className="w-4 h-4 object-contain" />
            )}
          </div>

          {/* Message Bubble */}
          <div className="flex flex-col gap-2 min-w-0">
            <div
              className={cn(
                "px-5 py-3.5 rounded-2xl shadow-sm border transition-all duration-200",
                isUser
                  ? "bg-emerald-600 border-emerald-500 text-white rounded-tr-none shadow-emerald-500/10"
                  : "bg-card border-border text-card-foreground rounded-tl-none hover:border-accent",
                isSelectionMode &&
                  isSelected &&
                  "ring-2 ring-indigo-500 border-indigo-500",
              )}
            >
              <div
                className={cn(
                  "text-sm leading-relaxed font-medium whitespace-pre-wrap break-words",
                  isUser ? "text-white" : "text-foreground",
                )}
              >
                {renderFormattedContent(msg.content, isUser)}
              </div>
            </div>

            {/* Inline screenshots */}
            {!isUser && msg.screenshots && msg.screenshots.length > 0 && (
              <div className="flex flex-col gap-2 mt-1">
                {msg.screenshots.map((src, i) => (
                  <div
                    key={i}
                    className="rounded-xl overflow-hidden border border-border shadow-lg max-w-xl"
                  >
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-muted border-b border-border select-none">
                      <Camera className="w-3.5 h-3.5 text-cyan-400" />
                      <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                        Screenshot
                      </span>
                    </div>
                    <img
                      src={
                        src.startsWith("data:")
                          ? src
                          : `data:image/jpeg;base64,${src}`
                      }
                      alt="Browser screenshot"
                      className="w-full h-auto object-contain max-h-96 bg-black"
                    />
                  </div>
                ))}
              </div>
            )}

            {/* AI Response Stats (tokens · cost · time) */}
            {!isUser && msg.plan && msg.plan.length > 0 && (() => {
              const totalInput  = msg.plan.reduce((s: number, t: Task) => s + (t.token_usage?.input  ?? 0), 0);
              const totalOutput = msg.plan.reduce((s: number, t: Task) => s + (t.token_usage?.output ?? 0), 0);
              const totalCost   = msg.plan.reduce((s: number, t: Task) => s + ((t.token_usage as any)?.cost ?? 0), 0);
              if (totalInput === 0 && totalOutput === 0) return null;

              const fmtTokens = (n: number) =>
                n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

              const msgIdx = messages.findIndex((m: ChatMessage) => m.id === msg.id);
              let processingMs: number | null = null;
              if (msgIdx > 0) {
                const prevUser = [...messages].slice(0, msgIdx).reverse()
                  .find((m: ChatMessage) => m.role === "user" || m.role === "human");
                if (prevUser?.timestamp && msg.timestamp) {
                  processingMs = new Date(msg.timestamp).getTime() - new Date(prevUser.timestamp).getTime();
                }
              }
              const fmtTime = (ms: number) => {
                if (ms < 60000) return `${Math.round(ms / 1000)}s`;
                const m = Math.floor(ms / 60000);
                const s = Math.round((ms % 60000) / 1000);
                return s > 0 ? `${m}m ${s}s` : `${m}m`;
              };

              return (
                <div className="flex items-center gap-3 flex-wrap mt-0.5 px-1">
                  {processingMs !== null && processingMs > 0 && (
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Clock className="w-3 h-3 text-muted-foreground/80" />
                      <span>{fmtTime(processingMs)}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <span className="text-muted-foreground/60">↑</span>
                    <span>{fmtTokens(totalInput)}</span>
                    <span className="text-muted-foreground/60 mx-0.5">/</span>
                    <span className="text-muted-foreground/60">↓</span>
                    <span>{fmtTokens(totalOutput)}</span>
                    <span className="text-muted-foreground/70 ml-0.5">tok</span>
                  </div>
                  {totalCost > 0 && (
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <span className="text-muted-foreground/60">$</span>
                      <span>{totalCost < 0.001 ? totalCost.toExponential(1) : totalCost.toFixed(4)}</span>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Timestamp & Actions */}
            <div
              className={cn(
                "flex items-center gap-3 px-1 opacity-0 group-hover:opacity-100 transition-opacity",
                isUser ? "flex-row-reverse" : "flex-row",
              )}
            >
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                {new Date(msg.timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleFileUploaded = async (
    fileName: string,
    fileSize: number,
    fileType: string,
  ) => {
    try {
      await sciparserApi.uploadFileMetadata(fileName, fileSize, fileType);

      const uploadRes = await sciparserApi.getUploadedFiles();
      const freshUpload = uploadRes.uploads.find(
        (u: UploadedFile) => u.name === fileName,
      ) || {
        id: "upl-" + Date.now(),
        name: fileName,
        size: fileSize,
        type: fileType,
        uploadedAt: new Date().toISOString(),
      };

      setThreads((prev) =>
        prev.map((t) => {
          if (t.id === activeThreadId) {
            const uploadsList = t.uploads.some(
              (u: UploadedFile) => u.name === fileName,
            )
              ? t.uploads
              : [...t.uploads, freshUpload];
            return { ...t, uploads: uploadsList };
          }
          return t;
        }),
      );
      setUploads((prev) =>
        prev.some((u: UploadedFile) => u.name === fileName)
          ? prev
          : [...prev, freshUpload],
      );

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
    sendQuickPrompt(
      "Analyze the vocal context frequencies and synthesize SciParser audio.",
    );
  };

  const parseInlineFormatting = (text: string, isUser: boolean = false) => {
    const boldParts = text.split(/(\*\*.*?\*\*)/g);
    return boldParts.map((bPart, bIdx) => {
      if (bPart.startsWith("**") && bPart.endsWith("**")) {
        return (
          <strong
            key={bIdx}
            className={cn(
              "font-extrabold",
              isUser ? "text-white" : "text-white dark:text-white",
            )}
          >
            {bPart.slice(2, -2)}
          </strong>
        );
      }
      const inlineParts = bPart.split(/(\`.*?\`)/g);
      return inlineParts.map((iPart, iIdx) => {
        if (iPart.startsWith("`") && iPart.endsWith("`")) {
          return (
            <code
              key={iIdx}
              className={cn(
                "px-1.5 py-0.5 mx-0.5 rounded font-mono text-[13px] font-bold",
                isUser
                  ? "bg-white/20 text-white"
                  : "bg-white/90 text-sky-500 dark:bg-white/90 dark:text-sky-600",
              )}
            >
              {iPart.slice(1, -1)}
            </code>
          );
        }
        const urlRegex = /(https?:\/\/[^\s)]+)|www\.[^\s)]+/g;
        return iPart.split(urlRegex).map((segment, segIdx) => {
          if (!segment) return null;
          if (urlRegex.test(segment)) {
            urlRegex.lastIndex = 0;
            const href = segment.startsWith("http")
              ? segment
              : `https://${segment}`;
            return (
              <a
                key={`${iIdx}-${segIdx}`}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-sky-400 underline underline-offset-2 decoration-sky-400/50 hover:text-sky-300"
              >
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
    const csvContent = data.map((row) => row.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${filename}.csv`);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderFormattedContent = (content: string, isUser: boolean = false) => {
    if (!content) return null;

    // Detect raw HTML pages (e.g. Replit proxy/hosting page served instead of data)
    if (
      !isUser &&
      (/^\s*<!DOCTYPE\s/i.test(content) ||
        /^\s*<html[\s>]/i.test(content) ||
        (content.includes("<body") && content.includes("</html>")))
    ) {
      const tmp = document.createElement("div");
      tmp.innerHTML = content;
      const text = (tmp.textContent || tmp.innerText || "")
        .trim()
        .replace(/\s+/g, " ");
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs">
            <span className="text-amber-400 font-semibold shrink-0">
              ⚠ HTML Response
            </span>
            <span className="text-muted-foreground">
              The server returned a web page instead of data — this may be a
              Replit hosting or proxy page.
            </span>
          </div>
          {text && (
            <p className="text-[13px] text-muted-foreground leading-relaxed line-clamp-3 px-1">
              {text.slice(0, 400)}
            </p>
          )}
        </div>
      );
    }

    // Split out fenced code blocks first so they don't get further parsed
    const parts = content.split(/(```[\s\S]*?```)/g);

    return parts.map((part, partIdx) => {
      // ── Fenced code block ──────────────────────────────────────────────
      if (part.startsWith("```") && part.endsWith("```")) {
        const inner = part.slice(3, -3).trim().split("\n");
        const lang = inner[0] && !/\s/.test(inner[0]) ? inner[0] : "";
        const code = (lang ? inner.slice(1) : inner).join("\n");
        return (
          <div
            key={partIdx}
            className="my-3.5 rounded-xl border border-border bg-card overflow-hidden font-mono text-[13px] shadow-md"
          >
            <div className="flex justify-between items-center px-4 py-1.5 bg-muted border-b border-border select-none">
              <span className="uppercase text-[10px] font-black tracking-widest text-muted-foreground">
                {lang || "text"}
              </span>
              <span className="text-[10px] text-muted-foreground/60 font-medium">
                ready
              </span>
            </div>
            <pre className="p-4 overflow-x-auto text-foreground leading-relaxed whitespace-pre">
              {code}
            </pre>
          </div>
        );
      }

      // ── Detect markdown table blocks ───────────────────────────────────
      const hasTable =
        part.includes("|") &&
        part.split("\n").some((l) => l.trim().startsWith("|"));

      if (!isUser && hasTable) {
        const tableLines = part
          .split("\n")
          .filter((l) => l.trim().startsWith("|"));
        if (tableLines.length > 1) {
          const isSep = (row: string[]) =>
            row.every((c) => /^:?-{2,}:?$/.test(c.replace(/\s/g, "")));
          const rows = tableLines.map((l) =>
            l
              .split("|")
              .map((c) => c.trim())
              .filter(Boolean),
          );
          const sepIdx = rows.findIndex(isSep);
          const header = sepIdx > 0 ? rows[0] : rows[0];
          const body = (
            sepIdx >= 0 ? rows.slice(sepIdx + 1) : rows.slice(1)
          ).filter((r) => !isSep(r));
          const nonTableText = part
            .split("\n")
            .filter((l) => !l.trim().startsWith("|") && l.trim())
            .join("\n");

          return (
            <div key={partIdx} className="space-y-3">
              {nonTableText && (
                <div>{renderFormattedContent(nonTableText, isUser)}</div>
              )}
              <div className="my-3 overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
                <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-muted border-b border-border">
                  <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                    <TableIcon className="w-3.5 h-3.5 text-indigo-500" />
                    Data Table
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      downloadTableData([header, ...body], "sciparser_data")
                    }
                    className="h-7 px-3 text-[10px] font-black text-sky-400 hover:bg-sky-500/10 gap-1 rounded-xl"
                  >
                    <Download className="w-3 h-3" />
                    EXPORT CSV
                  </Button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[13px] border-collapse">
                    <thead>
                      <tr className="bg-muted">
                        {header.map((h, i) => (
                          <th
                            key={i}
                            className="px-4 py-3 font-black text-foreground border-b border-border whitespace-nowrap"
                          >
                            {parseTableCellContent(h, isUser)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {body.map((row, ri) => (
                        <tr
                          key={ri}
                          className={cn(
                            "border-b border-border transition-colors hover:bg-muted/50",
                            ri % 2 === 0 ? "bg-card" : "bg-muted/20",
                          )}
                        >
                          {row.map((cell, ci) => (
                            <td
                              key={ci}
                              className="px-4 py-3 text-card-foreground align-top"
                            >
                              {parseTableCellContent(cell, isUser)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        }
      }

      // ── Line-by-line rendering ─────────────────────────────────────────
      const lines = part.split("\n");
      const rendered: React.ReactNode[] = [];
      let i = 0;

      while (i < lines.length) {
        const line = lines[i];
        const trimmed = line.trim();

        // Skip blank lines / table separator lines
        if (!trimmed || trimmed.startsWith("|")) {
          i++;
          continue;
        }

        // Horizontal rule
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
          rendered.push(
            <hr key={i} className="my-3 border-t border-border" />,
          );
          i++;
          continue;
        }

        // ATX Headings  # / ## / ###
        const h3 = trimmed.match(/^###\s+(.*)/);
        const h2 = trimmed.match(/^##\s+(.*)/);
        const h1 = trimmed.match(/^#\s+(.*)/);
        if (!isUser && h1) {
          rendered.push(
            <h2
              key={i}
              className="mt-4 mb-1 text-[18px] font-black text-foreground tracking-tight leading-snug"
            >
              {parseInlineFormatting(h1[1], isUser)}
            </h2>,
          );
          i++;
          continue;
        }
        if (!isUser && h2) {
          rendered.push(
            <h3
              key={i}
              className="mt-3 mb-1 text-[15px] font-black text-foreground tracking-tight"
            >
              {parseInlineFormatting(h2[1], isUser)}
            </h3>,
          );
          i++;
          continue;
        }
        if (!isUser && h3) {
          rendered.push(
            <h4
              key={i}
              className="mt-2 mb-0.5 text-[13px] font-black text-muted-foreground uppercase tracking-wider"
            >
              {parseInlineFormatting(h3[1], isUser)}
            </h4>,
          );
          i++;
          continue;
        }

        // Setext-style bold heading: "Text:" alone on a line (section label pattern)
        if (!isUser && /^[A-Z][^.!?]*:$/.test(trimmed) && trimmed.length < 60) {
          rendered.push(
            <p
              key={i}
              className="mt-3 mb-0.5 text-[13px] font-black text-sky-500 uppercase tracking-wider"
            >
              {trimmed}
            </p>,
          );
          i++;
          continue;
        }

        // Bullet list — collect consecutive items
        if (
          trimmed.startsWith("- ") ||
          trimmed.startsWith("* ") ||
          trimmed.startsWith("• ")
        ) {
          const items: string[] = [];
          while (i < lines.length) {
            const t = lines[i].trim();
            if (
              t.startsWith("- ") ||
              t.startsWith("* ") ||
              t.startsWith("• ")
            ) {
              items.push(t.replace(/^[-*•]\s+/, ""));
              i++;
            } else {
              break;
            }
          }
          rendered.push(
            <ul key={`ul-${i}`} className="my-1.5 space-y-1 pl-4">
              {items.map((item, idx) => (
                <li
                  key={idx}
                  className="flex gap-2 leading-relaxed text-[14px] text-muted-foreground"
                >
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500/70" />
                  <span>{parseInlineFormatting(item, isUser)}</span>
                </li>
              ))}
            </ul>,
          );
          continue;
        }

        // Numbered list — collect consecutive items
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          const items: { n: string; text: string }[] = [];
          while (i < lines.length) {
            const m = lines[i].trim().match(/^(\d+)\.\s+(.*)/);
            if (m) {
              items.push({ n: m[1], text: m[2] });
              i++;
            } else {
              break;
            }
          }
          rendered.push(
            <ol key={`ol-${i}`} className="my-1.5 space-y-1 pl-4">
              {items.map((item, idx) => (
                <li
                  key={idx}
                  className="flex gap-2.5 leading-relaxed text-[14px] text-muted-foreground"
                >
                  <span className="shrink-0 text-[12px] font-black text-sky-500 mt-0.5 w-4 text-right">
                    {item.n}.
                  </span>
                  <span>{parseInlineFormatting(item.text, isUser)}</span>
                </li>
              ))}
            </ol>,
          );
          continue;
        }

        // Plain paragraph
        rendered.push(
          <p
            key={i}
            className={cn(
              "leading-relaxed text-[14px]",
              isUser ? "text-white" : "text-muted-foreground",
            )}
          >
            {parseInlineFormatting(line, isUser)}
          </p>,
        );
        i++;
      }

      return (
        <div key={partIdx} className="space-y-1.5">
          {rendered}
        </div>
      );
    });
  };

  const filteredThreads = threads.filter((t) =>
    t.title.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const handleToggleLiveBrowser = async (isActive: boolean) => {
    if (isActive) {
      try {
        const res = await sciparserApi.checkBrowserSession();
        if (!res.is_active) {
          setSuccess(
            "Browser is not initialized yet. Opening the preview panel anyway.",
          );
          setTimeout(() => setSuccess(""), 3000);
        }
      } catch (err) {
        console.error("Failed to check browser session:", err);
        setSuccess(
          "Browser session check failed. Opening the preview panel anyway.",
        );
        setTimeout(() => setSuccess(""), 3000);
      }
    }

    setBrowserActive(isActive);
    setLastManualToggle(Date.now()); // Track manual interaction
  };

  const sidebarItemBase =
    "group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm font-medium";
  const sidebarItemInactive =
    "text-muted-foreground hover:text-foreground hover:bg-accent";
  const sidebarItemActive =
    "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20";

  const handleCreateSchedule = async () => {
    if (!activeThreadId) return;

    try {
      setIsNavigating(true);
      setLoaderText("Creating Schedule");

      await sciparserApi.createSchedule({
        chat_id: activeThreadId,
        title:
          threads.find((t) => t.id === activeThreadId)?.title || "New Schedule",
        selected_message_ids: selectedMessages,
        selected_tool_ids: selectedTools,
        schedule_type: scheduleType,
        email_recipient: emailRecipient || userProfile?.email,
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

  const handleSwitchView = (view: "chat" | "schedules" | "settings") => {
    if (currentView === view) return;

    setIsNavigating(true);
    setLoaderText(
      view === "chat" ? "Switching to Chat" :
      view === "schedules" ? "Opening Schedules" :
      "Opening Settings"
    );

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
      {/* Connect Your Browser (CDP) modal */}
      {showProxyModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowProxyModal(false)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-card rounded-2xl shadow-2xl border border-border overflow-hidden flex flex-col"
          >
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className={cn("w-4 h-4", proxyActive ? "text-violet-400" : "text-muted-foreground")} />
                <h3 className="font-semibold text-foreground text-sm">
                  {proxyActive ? "Residential Proxy Active" : "Configure Residential Proxy"}
                </h3>
              </div>
              <button onClick={() => setShowProxyModal(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <XIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-4">
              {proxyActive ? (
                <div className="space-y-3">
                  <div className="bg-violet-900/20 border border-violet-500/30 rounded-lg px-3 py-2.5">
                    <p className="text-xs text-violet-300 font-medium mb-0.5">Active proxy</p>
                    <p className="text-xs text-muted-foreground font-mono break-all">{proxyUrlMasked}</p>
                  </div>
                  <p className="text-xs text-muted-foreground/80">All browser sessions for your account are routed through this proxy. Remove it to go back to the datacenter IP.</p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 text-xs border-border text-muted-foreground hover:text-foreground"
                      onClick={handleTestProxy}
                      disabled={proxyTesting}
                    >
                      {proxyTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                      {proxyTesting ? "Testing…" : "Test Proxy"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 text-xs border-red-900/40 text-red-400 hover:bg-red-900/10"
                      onClick={handleDeleteProxy}
                      disabled={proxyDeleting}
                    >
                      {proxyDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                      {proxyDeleting ? "Removing…" : "Remove Proxy"}
                    </Button>
                  </div>
                  {proxyTestResult && (
                    <p className="text-xs text-emerald-400 bg-emerald-900/20 border border-emerald-500/20 rounded px-2 py-1.5">{proxyTestResult}</p>
                  )}
                  {proxyError && (
                    <p className="text-xs text-red-400 bg-red-900/20 border border-red-500/20 rounded px-2 py-1.5">{proxyError}</p>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Route browser traffic through a residential proxy to bypass WAF blocks on telecom and financial sites (Verizon, Frontier, AT&T, etc.). Works with Brightdata, Oxylabs, Smartproxy, or any HTTP proxy.
                  </p>
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground font-medium">Proxy URL</label>
                    <div className="relative">
                      <input
                        type={proxyInputVisible ? "text" : "password"}
                        value={proxyInput}
                        onChange={(e) => setProxyInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSaveProxy()}
                        placeholder="http://user:pass@proxy.example.com:22225"
                        className="w-full bg-muted border border-border rounded-lg px-3 py-2 text-xs text-foreground placeholder-muted-foreground/60 focus:outline-none focus:border-violet-500/50 pr-9 font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => setProxyInputVisible((v) => !v)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/80 hover:text-muted-foreground"
                      >
                        {proxyInputVisible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground/60">Credentials are stored in server memory only, not in the database.</p>
                  </div>
                  {proxyError && (
                    <p className="text-xs text-red-400 bg-red-900/20 border border-red-500/20 rounded px-2 py-1.5">{proxyError}</p>
                  )}
                  {proxyTestResult && (
                    <p className="text-xs text-emerald-400 bg-emerald-900/20 border border-emerald-500/20 rounded px-2 py-1.5">{proxyTestResult}</p>
                  )}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 text-xs border-border text-muted-foreground hover:text-foreground"
                      onClick={handleTestProxy}
                      disabled={proxyTesting || !proxyInput.trim()}
                    >
                      {proxyTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                      {proxyTesting ? "Testing…" : "Test"}
                    </Button>
                    <Button
                      size="sm"
                      className="flex-1 text-xs bg-violet-600 hover:bg-violet-500 text-white"
                      onClick={handleSaveProxy}
                      disabled={proxySaving || !proxyInput.trim()}
                    >
                      {proxySaving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                      {proxySaving ? "Saving…" : "Save Proxy"}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}

      {showCdpModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowCdpModal(false)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-card rounded-2xl shadow-2xl border border-border overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={cn("w-2.5 h-2.5 rounded-full", cdpConnected ? "bg-emerald-400" : "bg-muted-foreground/40")} />
                <h3 className="font-semibold text-foreground text-sm">
                  {cdpConnected ? "Your Browser Connected" : "Connect Your Browser"}
                </h3>
              </div>
              <button onClick={() => setShowCdpModal(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <XIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-4">
              {cdpConnected ? (
                /* Connected state */
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    The agent is using your local Chrome browser. Your residential IP bypasses
                    WAF blocks on Verizon, Frontier, AT&T, and Cloudflare.
                  </p>
                  <div className="bg-muted rounded-lg px-3 py-2 text-xs text-emerald-400 font-mono break-all">
                    {cdpConnectedUrl}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDisconnectCdp}
                    className="w-full text-red-400 border-red-900/40 hover:bg-red-900/20 text-xs"
                  >
                    Disconnect — switch back to cloud browser
                  </Button>
                </div>
              ) : (
                /* Not connected state */
                <div className="space-y-4">
                  <p className="text-xs text-muted-foreground">
                    Run Chrome with remote debugging enabled, then expose it publicly with a tunnel
                    so this server can reach it.
                  </p>

                  {/* Step 1: launch Chrome */}
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-semibold text-muted-foreground/80 uppercase tracking-wider">Step 1 — Launch Chrome</p>
                    <div className="bg-muted rounded-lg px-3 py-2 flex items-center justify-between gap-2">
                      <code className="text-xs text-foreground font-mono flex-1 break-all">
                        google-chrome --remote-debugging-port=9222 --no-first-run
                      </code>
                      <button
                        onClick={() => handleCdpCopy("google-chrome --remote-debugging-port=9222 --no-first-run")}
                        className="shrink-0 text-muted-foreground/80 hover:text-foreground transition-colors"
                        title="Copy"
                      >
                        {cdpCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <div className="space-y-1 mt-1">
                      <p className="text-[10px] text-muted-foreground/60">
                        <span className="text-muted-foreground/80">macOS:</span>{" "}
                        <span className="font-mono break-all">/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222</span>
                      </p>
                      <p className="text-[10px] text-muted-foreground/60">
                        <span className="text-muted-foreground/80">Windows:</span>{" "}
                        <span className="font-mono break-all">"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222</span>
                      </p>
                    </div>
                  </div>

                  {/* Step 2: tunnel */}
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-semibold text-muted-foreground/80 uppercase tracking-wider">Step 2 — Expose via tunnel</p>
                    <div className="bg-muted rounded-lg px-3 py-2">
                      <code className="text-xs text-foreground font-mono break-all">npx cloudflared tunnel --url http://localhost:9222</code>
                    </div>
                    <p className="text-[10px] text-muted-foreground/60">Copy the <span className="text-muted-foreground/80">trycloudflare.com</span> URL it prints — paste it below.</p>
                  </div>

                  {/* Step 3: enter URL */}
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-semibold text-muted-foreground/80 uppercase tracking-wider">Step 3 — Enter the CDP URL</p>
                    <input
                      type="text"
                      value={cdpUrlInput}
                      onChange={(e) => setCdpUrlInput(e.target.value)}
                      placeholder="https://xyz.trycloudflare.com"
                      className="w-full bg-muted border border-border rounded-lg px-3 py-2 text-xs text-foreground font-mono placeholder-muted-foreground/40 focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  {cdpError && (
                    <p className="text-xs text-red-400 bg-red-900/20 border border-red-900/30 rounded-lg px-3 py-2">{cdpError}</p>
                  )}

                  <Button
                    size="sm"
                    onClick={handleConnectCdp}
                    disabled={cdpConnecting || !cdpUrlInput.trim()}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold"
                  >
                    {cdpConnecting ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Testing connection…</> : "Connect"}
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}

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
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setActiveForm(null)}
                className="h-8 w-8 rounded-full"
              >
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
                          <span>
                            {field.label}{" "}
                            {field.required && (
                              <span className="text-red-500">*</span>
                            )}
                          </span>
                          {field.type === "password" && (
                            <span className="text-[9px] text-muted-foreground font-normal italic">
                              Encrypted
                            </span>
                          )}
                        </label>
                        <input
                          type={field.type || "text"}
                          placeholder={field.placeholder}
                          value={formData[field.id] || ""}
                          onChange={(e) =>
                            setFormData((prev) => ({
                              ...prev,
                              [field.id]: e.target.value,
                            }))
                          }
                          className="w-full px-4 py-2.5 text-sm rounded-xl bg-muted/50 border border-border focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all placeholder:text-muted-foreground"
                        />
                        {field.note && (
                          <p className="text-[10px] text-muted-foreground italic pl-1">
                            {field.note}
                          </p>
                        )}
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
              <Button
                variant="ghost"
                onClick={() => setActiveForm(null)}
                className="text-xs font-bold"
              >
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
            className="w-full max-w-3xl max-h-[80vh] bg-card rounded-[32px] shadow-2xl border border-border overflow-hidden flex flex-col"
          >
            <div className="px-8 py-6 border-b border-slate-100 dark:border-white/5 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                  <BookOpen className="w-4 h-4 text-indigo-500" />
                </div>
                <h3 className="font-black text-slate-900 dark:text-white text-lg tracking-tight uppercase">
                  Review Selection
                </h3>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsReviewOpen(false)}
                className="h-10 w-10 rounded-2xl"
              >
                <X className="w-5 h-5 text-slate-400" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-4 hide-scrollbar">
              {selectedMessages.map((id) => {
                const msg = messages.find((m) => m.id === id);
                return (
                  <div
                    key={id}
                    className="flex flex-col gap-3 bg-slate-50 dark:bg-white/2 p-5 rounded-2xl border border-slate-100 dark:border-white/5"
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-3.5 h-3.5 text-indigo-500" />
                      <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                        User Message
                      </span>
                    </div>
                    <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium">
                      {msg?.content}
                    </div>
                  </div>
                );
              })}
              {selectedTools.map((id) => {
                const log = toolLogs.find((l) => l.id === id);
                if (!log) return null;
                return (
                  <div
                    key={id}
                    className="flex flex-col gap-4 bg-slate-50 dark:bg-white/2 p-6 rounded-[24px] border border-slate-100 dark:border-white/5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Code className="w-4 h-4 text-emerald-500" />
                        <span className="text-[11px] font-black text-slate-700 dark:text-slate-200 uppercase tracking-wider">
                          {log.tool_name}
                        </span>
                      </div>
                      <div
                        className={cn(
                          "px-2 py-0.5 rounded-md text-[9px] font-black uppercase",
                          log.status === "SUCCESS"
                            ? "bg-emerald-500/10 text-emerald-600"
                            : log.status === "FAILED"
                              ? "bg-red-500/10 text-red-600"
                              : "bg-blue-500/10 text-blue-600",
                        )}
                      >
                        {log.status}
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="space-y-1.5">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest ml-1">
                          Input
                        </span>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-white dark:bg-black/20 p-3 rounded-xl border border-slate-100 dark:border-white/5 font-mono break-all">
                          {typeof log.tool_input === "string"
                            ? log.tool_input
                            : JSON.stringify(log.tool_input, null, 2)}
                        </div>
                      </div>
                      {log.tool_output && (
                        <div className="space-y-1.5">
                          <span className="text-[9px] font-bold text-emerald-500/70 uppercase tracking-widest ml-1">
                            Output
                          </span>
                          <div className="text-[11px] text-slate-600 dark:text-slate-300 bg-emerald-50/30 dark:bg-emerald-500/5 p-3 rounded-xl border border-emerald-100/30 dark:border-emerald-500/10 font-mono whitespace-pre-wrap">
                            {log.tool_output}
                          </div>
                        </div>
                      )}
                      {log.error_message && (
                        <div className="space-y-1.5">
                          <span className="text-[9px] font-bold text-red-500/70 uppercase tracking-widest ml-1">
                            Error
                          </span>
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
          "flex flex-col shrink-0 overflow-hidden border-border backdrop-blur-xl bg-background/95",
          isMobile
            ? cn(
                "fixed inset-y-0 left-0 z-50 h-full w-[320px] max-w-[85vw] border-r transition-transform duration-300",
                isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full",
              )
            : "relative h-full z-20 border-r transition-[width] duration-300",
        )}
        style={
          !isMobile
            ? {
                width: isSidebarCollapsed
                  ? "56px"
                  : currentView === "schedules" || currentView === "settings"
                    ? "64px"
                    : `${sidebarWidth}px`,
              }
            : undefined
        }
      >
        {/* Collapsed icon-only rail (desktop only, when sidebar is toggled off) */}
        {!isMobile && isSidebarCollapsed && (
          <div className="flex h-full flex-col items-center py-4 gap-3 overflow-hidden">
            <div className="pointer-events-none absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_top,color-mix(in_oklab,var(--primary)_8%,transparent),transparent_28%)]" />
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full border border-primary/20 bg-muted shadow-[0_0_18px_rgba(16,185,129,0.16)]">
              <img src={atomIcon} alt="SciParser" className="h-6 w-6 object-contain" />
            </div>
            <div className="relative z-10 w-8 h-px bg-border" />
            <button
              onClick={() => handleNewChat(true)}
              title="New Chat"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-border bg-card/50 text-muted-foreground hover:border-primary/25 hover:bg-muted hover:text-foreground transition-all"
            >
              <Plus className="h-5 w-5" />
            </button>
            <button
              onClick={() =>
                handleSwitchView(
                  currentView === "schedules" ? "chat" : "schedules",
                )
              }
              title="Automation"
              className={cn(
                "relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border transition-all",
                currentView === "schedules"
                  ? "border-primary/35 bg-gradient-to-b from-primary/20 to-primary/15 text-foreground shadow-[0_0_16px_rgba(34,211,238,0.15)]"
                  : "border-border bg-card/50 text-muted-foreground hover:border-primary/25 hover:bg-muted hover:text-foreground",
              )}
            >
              <Calendar className="h-5 w-5" />
            </button>
            <button
              onClick={() => handleSwitchView(currentView === "settings" ? "chat" : "settings")}
              title="Settings"
              className={cn(
                "relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border transition-all",
                currentView === "settings"
                  ? "border-violet-500/35 bg-gradient-to-b from-violet-500/20 to-violet-600/15 text-foreground shadow-[0_0_16px_rgba(167,139,250,0.15)]"
                  : "border-border bg-card/50 text-muted-foreground hover:border-violet-500/25 hover:bg-muted hover:text-foreground",
              )}
            >
              <Settings className="h-5 w-5" />
            </button>
            <div className="flex-1" />
            <button
              onClick={toggleTheme}
              title="Toggle theme"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-border bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-all"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={handleLogout}
              title="Log out"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-border bg-muted text-red-400 hover:bg-muted/80 hover:text-red-300 transition-all"
            >
              <LogOut className="w-4 h-4" />
            </button>
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-white text-xs font-black shadow-[0_0_18px_rgba(16,185,129,0.3)]">
              {userProfile?.username.slice(0, 2).toUpperCase()}
            </div>
          </div>
        )}

        {/* Icon-only rail shown when on Automation or Settings page (desktop only) */}
        {!isMobile && !isSidebarCollapsed && (currentView === "schedules" || currentView === "settings") && (
          <div className="flex h-full flex-col items-center py-4 gap-3">
            <div className="pointer-events-none absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_top,color-mix(in_oklab,var(--primary)_8%,transparent),transparent_28%)]" />
            {/* Logo */}
            <div className="relative z-10">
              <img src={theme === "dark" ? logoDark : logoLight} alt="SciParser" className="h-8 w-auto object-contain" />
            </div>
            <div className="relative z-10 w-8 h-px bg-border" />
            {/* Chat nav icon */}
            <button
              onClick={() => handleSwitchView("chat")}
              title="AI Chat"
              className={cn(
                "relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border transition-all",
                currentView === "chat"
                  ? "border-primary/35 bg-gradient-to-b from-primary/20 to-primary/15 text-foreground shadow-[0_0_16px_rgba(34,211,238,0.15)]"
                  : "border-border bg-card/50 text-muted-foreground hover:border-primary/25 hover:bg-muted hover:text-foreground",
              )}
            >
              <MessageSquare className="h-5 w-5" />
            </button>
            {/* Automation nav icon */}
            <button
              onClick={() => handleSwitchView("schedules")}
              title="Automation"
              className={cn(
                "relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border transition-all",
                currentView === "schedules"
                  ? "border-primary/35 bg-gradient-to-b from-primary/20 to-primary/15 text-foreground shadow-[0_0_16px_rgba(34,211,238,0.15)]"
                  : "border-border bg-card/50 text-muted-foreground hover:border-primary/25 hover:bg-muted hover:text-foreground",
              )}
            >
              <Calendar className="h-5 w-5" />
            </button>
            {/* Settings nav icon */}
            <button
              onClick={() => handleSwitchView("settings")}
              title="Settings"
              className={cn(
                "relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border transition-all",
                currentView === "settings"
                  ? "border-violet-500/35 bg-gradient-to-b from-violet-500/20 to-violet-600/15 text-foreground shadow-[0_0_16px_rgba(167,139,250,0.15)]"
                  : "border-border bg-card/50 text-muted-foreground hover:border-violet-500/25 hover:bg-muted hover:text-foreground",
              )}
            >
              <Settings className="h-5 w-5" />
            </button>
            {/* Spacer */}
            <div className="flex-1" />
            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              title="Toggle theme"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-border bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-all"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
            </button>
            {/* Logout */}
            <button
              onClick={handleLogout}
              title="Log out"
              className="relative z-10 flex h-10 w-10 items-center justify-center rounded-[14px] border border-border bg-muted text-red-400 hover:bg-muted/80 hover:text-red-300 transition-all"
            >
              <LogOut className="w-4 h-4" />
            </button>
            {/* User avatar */}
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-white text-xs font-black shadow-[0_0_18px_rgba(16,185,129,0.3)]">
              {userProfile?.username.slice(0, 2).toUpperCase()}
            </div>
          </div>
        )}
        <div
          className={cn(
            "relative flex h-full flex-col bg-background/95",
            !isMobile &&
              (isSidebarCollapsed || currentView === "schedules") &&
              "hidden",
          )}
        >
          <div className="pointer-events-none absolute inset-0 opacity-30 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_28%),radial-gradient(circle_at_bottom,rgba(16,185,129,0.06),transparent_22%)]" />

          {/* Drag-resize handle — right edge of sidebar */}
          {!isMobile && (
            <div
              onMouseDown={handleSidebarMouseDown}
              title="Drag to resize"
              className="absolute right-0 top-0 h-full w-1 z-30 cursor-col-resize group"
              style={{ userSelect: "none" }}
            >
              <div className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[3px] h-10 rounded-full bg-transparent group-hover:bg-[#22D3EE]/40 transition-colors duration-150" />
            </div>
          )}

          {/* Sidebar Header */}
          <div className="relative z-10 px-4 pt-4 pb-3">
            <div className="rounded-[18px] border border-border bg-muted/30 px-4 py-4 shadow-[0_14px_40px_rgba(0,0,0,0.24)] backdrop-blur-xl">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <img src={theme === "dark" ? logoDark : logoLight} alt="SciParser" className="h-8 w-auto object-contain" />
                </div>
                <div className="flex items-center gap-1.5">
                  {isMobile && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setIsMobileSidebarOpen(false)}
                      className="h-10 w-10 rounded-[14px] border border-border bg-card/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleNewChat(true)}
                    className="h-10 w-10 rounded-[14px] border border-border bg-card/60 text-foreground hover:bg-muted hover:text-[#22D3EE]"
                  >
                    <Plus className="h-5 w-5" />
                  </Button>
                </div>
              </div>

              {/* Sidebar Search */}
              <div className="mt-4 relative">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-[14px] border border-border bg-card/80 py-3 pl-10 pr-12 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-[#22D3EE]/50 focus:ring-2 focus:ring-[#22D3EE]/15"
                />
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-border bg-muted/30 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                  ⌘K
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleSwitchView("chat")}
                  className={cn(
                    "flex items-center justify-between rounded-[14px] border px-3 py-3 text-left transition-all duration-200",
                    currentView === "chat"
                      ? "border-[#22D3EE]/35 bg-gradient-to-r from-[#10B981]/20 to-[#22D3EE]/15 text-foreground shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                      : "border-border bg-muted/20 text-muted-foreground hover:border-[#22D3EE]/25 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare className="h-4 w-4 shrink-0" />
                    <span className="truncate text-sm font-semibold">
                      AI Chat Core
                    </span>
                  </div>
                  <img src={atomIcon} alt="SciParser" className="h-4 w-4 object-contain shrink-0" />
                </button>

                <button
                  onClick={() => handleSwitchView("schedules")}
                  className={cn(
                    "flex items-center justify-between rounded-[14px] border px-3 py-3 text-left transition-all duration-200",
                    currentView === "schedules"
                      ? "border-[#22D3EE]/35 bg-gradient-to-r from-[#10B981]/20 to-[#22D3EE]/15 text-foreground shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                      : "border-border bg-muted/20 text-muted-foreground hover:border-[#22D3EE]/25 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Calendar className="h-4 w-4 shrink-0" />
                    <span className="truncate text-sm font-semibold">
                      Automation
                    </span>
                  </div>
                  <div className="h-2 w-2 rounded-full bg-[#22D3EE]" />
                </button>

                <button
                  onClick={() => handleSwitchView("settings")}
                  className={cn(
                    "col-span-2 flex items-center justify-between rounded-[14px] border px-3 py-3 text-left transition-all duration-200",
                    currentView === "settings"
                      ? "border-violet-500/35 bg-gradient-to-r from-violet-500/20 to-violet-600/15 text-foreground shadow-[0_0_24px_rgba(167,139,250,0.12)]"
                      : "border-border bg-muted/20 text-muted-foreground hover:border-violet-500/25 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Settings className="h-4 w-4 shrink-0" />
                    <span className="truncate text-sm font-semibold">
                      Settings
                    </span>
                  </div>
                  <Shield className="h-3.5 w-3.5 shrink-0 text-violet-400/60" />
                </button>
              </div>
            </div>
          </div>

          {/* Sidebar Thread List */}
          <div className="relative z-10 flex-1 overflow-y-auto px-4 pb-3 pt-1 hide-scrollbar">
            <div className="flex items-center gap-3 px-1.5 pb-3 pt-1">
              <div className="h-px flex-1 bg-border" />
              <span className="text-[10px] font-black uppercase tracking-[0.24em] text-[#10B981]">
                Recent Chats
              </span>
              <div className="h-px flex-1 bg-border" />
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
                        : "border-border bg-muted/20 hover:border-[#22D3EE]/25 hover:bg-muted",
                    )}
                  >
                    {isActive && (
                      <div className="absolute left-0 top-0 h-full w-1 bg-[#10B981] shadow-[0_0_14px_rgba(16,185,129,0.65)]" />
                    )}
                    <div className="flex items-start gap-3 pl-1">
                      <div
                        className={cn(
                          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] border",
                          isActive
                            ? "border-[#10B981]/20 bg-[#10B981]/10 text-[#10B981]"
                            : "border-border bg-card text-muted-foreground",
                        )}
                      >
                        <MessageSquare className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={cn(
                              "truncate text-[14px] font-semibold tracking-tight",
                              isActive
                                ? "text-foreground"
                                : "text-muted-foreground group-hover:text-foreground",
                            )}
                          >
                            {t.title}
                          </span>
                          <div className="flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeletingThreadId(String(t.id));
                              }}
                              className="rounded-md border border-border bg-muted/30 p-1.5 text-muted-foreground hover:border-red-500/30 hover:text-red-400"
                            >
                              <Trash className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <span className="text-[11px] text-muted-foreground">
                            {isActive
                              ? "Pinned chat"
                              : `${t.messages?.length || 0} messages`}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {t.createdAt
                              ? new Date(t.createdAt).toLocaleDateString([], {
                                  month: "short",
                                  day: "numeric",
                                })
                              : ""}
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
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-[14px] border border-border bg-card/80 px-3 py-3 text-sm font-semibold text-[#10B981] transition-all hover:border-[#10B981]/30 hover:bg-muted hover:text-[#34D399]"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-[#10B981]/30 bg-[#10B981]/10 text-[#10B981]">
                +
              </span>
              New Chat
            </button>
          </div>

          {/* Sidebar Footer */}
          <div className="relative z-10 px-4 pb-4 pt-2">
            <div className="rounded-[16px] border border-border bg-muted/30 px-4 py-3 backdrop-blur-xl shadow-[0_14px_40px_rgba(0,0,0,0.24)]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#10B981] text-white font-black shadow-[0_0_24px_rgba(16,185,129,0.38)]">
                    {userProfile?.username.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {userProfile?.username}
                    </p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {userProfile?.email}
                    </p>
                  </div>
                </div>
                <button className="rounded-lg border border-border bg-card p-2 text-muted-foreground transition-colors hover:border-[#22D3EE]/25 hover:text-foreground">
                  <ChevronDown className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 flex items-center justify-between gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleTheme}
                  className="h-10 w-10 rounded-[12px] border border-border bg-card text-muted-foreground transition-all hover:bg-muted hover:text-foreground active:scale-90"
                >
                  {theme === "dark" ? (
                    <Sun className="w-5 h-5" />
                  ) : (
                    <Moon className="w-5 h-5" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  className="h-10 w-10 rounded-[12px] border border-border bg-card text-red-400 transition-all hover:bg-muted hover:text-red-300 active:scale-90"
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
                className="w-full max-w-sm rounded-[20px] border border-border bg-card p-6 text-center shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-red-500/20 bg-red-500/10">
                  <Trash className="h-6 w-6 text-red-400" />
                </div>
                <div className="mt-4 space-y-2">
                  <h3 className="text-lg font-bold text-foreground">
                    Delete chat?
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    This will permanently remove this conversation and all its
                    history.
                  </p>
                </div>
                <div className="mt-5 flex gap-3">
                  <Button
                    variant="ghost"
                    onClick={() => setDeletingThreadId(null)}
                    className="flex-1 rounded-xl border border-border bg-muted/30 text-xs font-bold text-foreground hover:bg-muted"
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
        {currentView === "settings" ? (
          <SettingsPage onBack={() => handleSwitchView("chat")} userProfile={userProfile} />
        ) : currentView === "schedules" ? (
          <SchedulesPage onBack={() => handleSwitchView("chat")} />
        ) : (
          <>
            {/* Chat Column */}
            <div
              className="flex flex-col h-full min-w-0 bg-background transition-all duration-300"
              style={{
                flex: `1 1 ${100 - (browserActive ? browserPanelWidth : 0)}%`,
              }}
            >
              {/* Chat Header */}
              <div className="h-14 border-b border-border bg-card px-4 flex items-center gap-2 shrink-0 overflow-hidden">
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      sidebarUserInteractedRef.current = true;
                      sidebarAutoCollapsedRef.current = false;
                      if (isMobile) {
                        setIsMobileSidebarOpen(!isMobileSidebarOpen);
                      } else {
                        setIsSidebarCollapsed(!isSidebarCollapsed);
                      }
                    }}
                    className="hover:bg-muted shrink-0"
                  >
                    {(isMobile ? isMobileSidebarOpen : !isSidebarCollapsed) ? (
                      <PanelLeftClose className="w-5 h-5" />
                    ) : (
                      <PanelLeftOpen className="w-5 h-5" />
                    )}
                  </Button>
                  <div className="font-semibold text-sm text-foreground truncate max-w-[120px] sm:max-w-none">
                    {activeModel}
                  </div>
                </div>

                <div className="flex-1" />

                <div className="flex items-center gap-1 sm:gap-1.5 flex-nowrap shrink-0">

                  <Button
                    variant={isSelectionMode ? "default" : "outline"}
                    size="sm"
                    onClick={toggleSelectionMode}
                    className={cn(
                      "gap-1.5 text-xs font-semibold shrink-0",
                      isSelectionMode &&
                        "bg-indigo-600 hover:bg-indigo-700 text-white border-none",
                    )}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="hidden md:inline">
                      {isSelectionMode ? "Cancel Selection" : "Schedule Task"}
                    </span>
                  </Button>

                  {isSelectionMode && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleClearSelection}
                      className="gap-1.5 text-xs font-semibold shrink-0 text-slate-500 border-slate-200 hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
                    >
                      <Trash className="w-4 h-4" />
                      <span className="hidden md:inline">Clear All</span>
                    </Button>
                  )}

                  {isSelectionMode &&
                    (selectedMessages.length > 0 ||
                      selectedTools.length > 0) && (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => setIsSchedulerOpen(true)}
                        className="gap-1.5 text-xs font-semibold shrink-0 bg-emerald-600 hover:bg-emerald-700 text-white border-none"
                      >
                        <RefreshCw className="w-4 h-4" />
                        <span className="hidden md:inline">
                          Configure Schedule{" "}
                        </span>
                        <span>
                          ({selectedMessages.length + selectedTools.length})
                        </span>
                      </Button>
                    )}

                  <Button
                    variant={browserActive ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      const nextState = !browserActive;
                      handleToggleLiveBrowser(nextState);
                      setUserInterruptedBrowser(!nextState);
                    }}
                    className={cn(
                      "gap-1.5 text-xs font-semibold shrink-0 transition-all duration-500",
                      browserActive &&
                        "bg-emerald-600 hover:bg-emerald-700 text-white border-none",
                      browserBlink === "green" &&
                        "ring-4 ring-emerald-500 animate-pulse border-emerald-500",
                      browserBlink === "red" &&
                        "ring-4 ring-red-500 animate-pulse border-red-500",
                    )}
                  >
                    <Globe className="w-4 h-4" />
                    <span className="hidden md:inline">Live Browser</span>
                  </Button>

                  {/* Connect Your Browser (CDP) button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setCdpError(null); setShowCdpModal(true); }}
                    title={cdpConnected ? `Your browser connected: ${cdpConnectedUrl}` : "Connect your local Chrome browser to avoid WAF blocks"}
                    className={cn(
                      "gap-1.5 text-xs font-semibold shrink-0 transition-all duration-300",
                      cdpConnected
                        ? "border-emerald-500 text-emerald-400 hover:bg-emerald-900/20"
                        : "border-border text-muted-foreground hover:text-foreground hover:border-border",
                    )}
                  >
                    <span className={cn("w-2 h-2 rounded-full shrink-0", cdpConnected ? "bg-emerald-400" : "bg-muted-foreground")} />
                    <Link className="w-4 h-4" />
                    <span className="hidden md:inline">{cdpConnected ? "Your Browser" : "Connect Browser"}</span>
                  </Button>

                  {/* Residential Proxy button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSwitchView("settings")}
                    title={proxyActive ? `Proxy active: ${proxyUrlMasked}` : "Configure a residential proxy to bypass WAF blocks"}
                    className={cn(
                      "gap-1.5 text-xs font-semibold shrink-0 transition-all duration-300",
                      proxyActive
                        ? "border-violet-500 text-violet-400 hover:bg-violet-900/20"
                        : "border-border text-muted-foreground hover:text-foreground hover:border-border",
                    )}
                  >
                    <Shield className={cn("w-4 h-4", proxyActive && "fill-violet-500/20")} />
                    <span className="hidden md:inline">{proxyActive ? "Proxy On" : "Proxy"}</span>
                  </Button>

                  {browserActive && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCloseBrowser}
                      className="gap-1.5 text-xs font-semibold shrink-0 text-red-500 border-red-200 hover:bg-red-50 dark:border-red-900/30 dark:hover:bg-red-900/10"
                    >
                      <XIcon className="w-4 h-4" />
                      <span className="hidden md:inline">Close Browser</span>
                    </Button>
                  )}

                  {activeThreadId && !isAiTyping && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleResetSession}
                      title="Clear the saved browser session so the next message starts from scratch"
                      className="gap-1.5 text-xs font-semibold shrink-0 text-amber-500 border-amber-200 hover:bg-amber-50 dark:border-amber-900/30 dark:hover:bg-amber-900/10"
                    >
                      <RefreshCw className="w-4 h-4" />
                      <span className="hidden md:inline">Reset Session</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* Camoufox fallback warning banner */}
              {camoufoxFallbackWarning && (
                <div className="mx-3 mt-2 flex items-center gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300 shrink-0">
                  <span className="shrink-0">⚠</span>
                  <span className="flex-1">
                    Camoufox failed to start — running on Chrome instead. Bot detection may be less effective.{" "}
                    <button
                      onClick={() => handleSwitchView("settings")}
                      className="underline underline-offset-2 hover:text-amber-200 transition-colors"
                    >
                      Open Settings
                    </button>
                  </span>
                  <button
                    onClick={() => setCamoufoxFallbackWarning(false)}
                    className="shrink-0 text-amber-400 hover:text-amber-200 transition-colors"
                    aria-label="Dismiss"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Messages Container */}
              <div className="flex-1 flex flex-row overflow-hidden">
                <div
                  ref={scrollRef}
                  onScroll={handleChatScroll}
                  className="flex-1 overflow-y-auto flex flex-col"
                >
                  {messages.length === 0 && !isAiTyping ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-4 sm:p-6 chat-content-cap space-y-4">
                      <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center border border-border">
                        <img src={atomIcon} alt="SciParser" className="w-8 h-8 object-contain" />
                      </div>
                      <h2 className="text-xl font-bold text-foreground">
                        How can I assist you today?
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        SciParser can browse the web, analyze documents, and run
                        complex multi-agent workflows.
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-4">
                        <button
                          onClick={() =>
                            sendQuickPrompt(
                              "Go to Hacker News and extract top stories",
                            )
                          }
                          className="p-3 text-xs font-medium text-left rounded-xl border border-border text-foreground hover:bg-muted transition-colors min-h-[44px]"
                        >
                          📰 Extract Hacker News
                        </button>
                        <button
                          onClick={() =>
                            sendQuickPrompt(
                              "Search for latest AI research papers",
                            )
                          }
                          className="p-3 text-xs font-medium text-left rounded-xl border border-border text-foreground hover:bg-muted transition-colors min-h-[44px]"
                        >
                          🔬 Search AI Papers
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex-1" />
                      <div className="p-3 sm:p-6 space-y-4 sm:space-y-6 chat-content-cap">
                        {messages.map(renderMessage)}

                        {/* Live Plan / Loading State */}
                        {isAiTyping && (
                          <div className="mt-4 max-w-2xl space-y-4">
                            <div className="flex items-center justify-between px-1">
                              <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2">
                                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                                  <div className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em]">
                                    Live Execution
                                  </div>
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
                                    taskThoughts={taskThoughts}
                                    isAiTyping={isAiTyping}
                                  />
                                ) : (
                                  <div className="bg-card border border-border rounded-2xl p-5 shadow-sm">
                                    <MessageLoading />
                                  </div>
                                )}
                              </motion.div>
                            </AnimatePresence>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>

              </div>

              {/* Chat Input Area */}
              <div className="px-3 py-3 sm:px-4 sm:py-4 bg-card border-t border-border">
                <div className="chat-content-cap relative flex items-end gap-2 bg-card border border-border rounded-xl p-2">
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
                    onChange={(e) => setTextareaValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(textareaValue);
                      }
                    }}
                    placeholder="Ask SciParser anything..."
                    style={{
                      minHeight: `${MIN_TEXTAREA_H}px`,
                      maxHeight: `${MAX_TEXTAREA_H}px`,
                      height: `${MIN_TEXTAREA_H}px`,
                      overflowY: "hidden",
                    }}
                    className="w-full resize-none bg-transparent border-none focus:outline-none text-sm py-2 px-1 text-foreground placeholder:text-muted-foreground"
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
                  className="w-1.5 bg-border hover:bg-indigo-500 cursor-col-resize transition-colors z-30 relative group"
                >
                  <div className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize" />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-12 rounded-full bg-border group-hover:bg-white transition-colors" />
                </div>

                <div
                  ref={browserPanelRef}
                  style={{ width: `${browserPanelWidth}%` }}
                  className="h-full overflow-hidden bg-background flex flex-col shrink-0 transition-[width] duration-75 ease-out"
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
                    mousePos={mousePos}
                    onToggleToolSelection={(id) => {
                      setSelectedToolIds((prev) =>
                        prev.includes(id)
                          ? prev.filter((i) => i !== id)
                          : [...prev, id],
                      );
                    }}
                    onClearLogs={() => setToolLogs([])}
                    browserEngine={activeBrowserEngine}
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
