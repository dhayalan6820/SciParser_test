import * as React from "react";
import { Button } from "./button";
import { sciparserApi, ChatMessage } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { 
  Calendar, Clock, Code, Play, Pencil, Trash, 
  ChevronLeft, Mail, CheckCircle2, AlertCircle,
  ExternalLink, Copy, Download, X, Globe, RefreshCw,
  Settings, Bell, Shield, Zap, Info, ChevronRight, ChevronDown,
  Layout, Cpu, Terminal, Layers, Activity, Database,
  Search, MessageSquare, Target, Check, List, Workflow,
  ArrowRight, Loader2, Sparkles, User as UserIcon, Brain
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Task, Subtask } from "./agent-plan";

const TIMEZONE_OPTIONS = [
  { label: "(GMT-05:00) EST — New York", value: "America/New_York", abbr: "EST" },
  { label: "(GMT-06:00) CST — Chicago", value: "America/Chicago", abbr: "CST" },
  { label: "(GMT-07:00) MST — Denver", value: "America/Denver", abbr: "MST" },
  { label: "(GMT-08:00) PST — Los Angeles", value: "America/Los_Angeles", abbr: "PST" },
  { label: "(GMT+05:30) IST — India", value: "Asia/Kolkata", abbr: "IST" },
  { label: "(GMT+00:00) UTC", value: "UTC", abbr: "UTC" },
];

const DAY_OF_WEEK_OPTIONS = [
  { label: "Mon", value: "mon" },
  { label: "Tue", value: "tue" },
  { label: "Wed", value: "wed" },
  { label: "Thu", value: "thu" },
  { label: "Fri", value: "fri" },
  { label: "Sat", value: "sat" },
  { label: "Sun", value: "sun" },
];

const TIME_OPTIONS = Array.from({ length: 24 }, (_, h) => {
  const ampm = h < 12 ? "AM" : "PM";
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return {
    label: `${String(h12).padStart(2, "0")}:00 ${ampm}`,
    value: `${String(h).padStart(2, "0")}:00`,
  };
});

const DOW_TO_INDEX: Record<string, number> = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };

function computeNextRun(scheduleType: string, scheduleTime: string, tz: string, dayOfWeek: string = "mon"): string {
  const [h, m] = scheduleTime.split(":").map(Number);
  // Represent "now" in the selected IANA timezone using the toLocaleString trick
  const nowInTz = new Date(new Date().toLocaleString("en-US", { timeZone: tz }));
  let next = new Date(nowInTz);
  next.setHours(h, m || 0, 0, 0);

  if (scheduleType === "daily") {
    if (next <= nowInTz) next.setDate(next.getDate() + 1);
  } else if (scheduleType === "weekly") {
    const targetDow = DOW_TO_INDEX[dayOfWeek] ?? 1;
    const dow = next.getDay(); // 0=Sun
    let daysAhead = targetDow - dow;
    if (daysAhead < 0 || (daysAhead === 0 && next <= nowInTz)) daysAhead += 7;
    next.setDate(next.getDate() + daysAhead);
  } else if (scheduleType === "monthly") {
    next = new Date(nowInTz.getFullYear(), nowInTz.getMonth() + 1, 1, h, m || 0, 0, 0);
  }

  return next.toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: tz,
  }) + " at " + next.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZone: tz });
}

interface Schedule {
  schedule_id: string;
  title: string;
  schedule_type: string;
  email_recipient: string;
  status: string;
  generated_script: string;
  extracted_content: string;
  created_at: string;
  updated_at?: string;
}

interface PremiumSchedulerProps {
  isOpen: boolean;
  onClose: () => void;
  onScheduled?: () => void;
  selectedMessages: string[];
  selectedTools: string[];
  chatId?: string;
  messages: ChatMessage[];
  currentPlan: Task[] | null;
  toolLogs: any[];
}

export const PremiumScheduler: React.FC<PremiumSchedulerProps> = ({ 
  isOpen, 
  onClose, 
  onScheduled,
  selectedMessages, 
  selectedTools,
  chatId,
  messages,
  currentPlan,
  toolLogs
}) => {
  const { theme } = useTheme();
  const [loading, setLoading] = React.useState(false);
  const [scheduleType, setScheduleType] = React.useState("daily");
  const [emailRecipient, setEmailRecipient] = React.useState("");
  const [taskName, setTaskName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [activeTab, setActiveTab] = React.useState("context");
  const [scheduleError, setScheduleError] = React.useState("");
  const [scheduleSuccess, setScheduleSuccess] = React.useState(false);
  
  // Schedule time & timezone
  const [scheduleTime, setScheduleTime] = React.useState("09:00");
  const [scheduleDayOfWeek, setScheduleDayOfWeek] = React.useState("mon");
  const [timezone, setTimezone] = React.useState("America/New_York");

  // Advanced Options
  const [retryCount, setRetryCount] = React.useState(3);
  const [timeout, setTimeoutVal] = React.useState(120);
  const [headless, setHeadless] = React.useState(true);

  const [draftLoading, setDraftLoading] = React.useState(false);
  const [draftSuccess, setDraftSuccess] = React.useState(false);

  // Empty tool log warning state
  const [showEmptyToolsWarning, setShowEmptyToolsWarning] = React.useState(false);
  const [taskNameMissing, setTaskNameMissing] = React.useState(false);
  const taskNameInputRef = React.useRef<HTMLInputElement>(null);

  // Truncate tool output to keep token cost low
  const summarizeOutput = (raw: unknown, maxChars = 500): string => {
    const str = typeof raw === 'string' ? raw : JSON.stringify(raw ?? '');
    if (str.length <= maxChars) return str;
    return str.slice(0, maxChars) + `… [+${str.length - maxChars} chars truncated]`;
  };

  const handleCreateSchedule = async (skipWarning = false) => {
    setScheduleError("");

    // Task name is required — tell the user instead of silently blocking the button
    if (!taskName.trim()) {
      setTaskNameMissing(true);
      setScheduleError("Please enter a task name before confirming the schedule.");
      taskNameInputRef.current?.focus();
      taskNameInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setTaskNameMissing(false);

    // If no tools have been selected, warn the user first
    if (!skipWarning && selectedTools.length === 0) {
      setShowEmptyToolsWarning(true);
      return;
    }

    setShowEmptyToolsWarning(false);
    try {
      setLoading(true);

      // Build compact tool context — only the user-selected SUCCESS tools, output summarised ≤300 chars
      const tool_context = (toolLogs || [])
        .filter(log =>
          selectedTools.includes(log.id) &&
          (log.status === 'SUCCESS' || log.status === 'COMPLETED')
        )
        .map(log => ({
          tool_name: log.tool_name,
          output: summarizeOutput(log.tool_output, 300)
        }));

      const data = {
        chat_id: chatId,
        title: taskName || "New Automation Task",
        schedule_type: scheduleType,
        schedule_time: scheduleTime,
        schedule_day_of_week: scheduleDayOfWeek,
        timezone: timezone,
        email_recipient: emailRecipient,
        selected_message_ids: selectedMessages,
        selected_tool_ids: selectedTools,
        tool_context,
        advanced_options: {
          retry_count: retryCount,
          timeout: timeout,
          headless: headless
        }
      };
      await sciparserApi.createSchedule(data);
      setScheduleSuccess(true);
      onScheduled?.();
      setTimeout(() => onClose(), 1500);
    } catch (err: any) {
      console.error("Failed to create schedule:", err);
      let msg = err?.message || "Failed to create schedule.";
      try {
        const parsed = JSON.parse(msg);
        msg = parsed?.detail || parsed?.message || msg;
      } catch {}
      setScheduleError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    setScheduleError("");
    try {
      setDraftLoading(true);
      const data = {
        chat_id: chatId,
        title: taskName || "New Automation Task",
        schedule_type: scheduleType,
        schedule_time: scheduleTime,
        schedule_day_of_week: scheduleDayOfWeek,
        timezone: timezone,
        email_recipient: emailRecipient || null,
        selected_message_ids: selectedMessages,
        selected_tool_ids: selectedTools,
        status: "draft",
        advanced_options: {
          retry_count: retryCount,
          timeout: timeout,
          headless: headless
        }
      };
      await sciparserApi.createSchedule(data);
      setDraftSuccess(true);
      onScheduled?.();
      setTimeout(() => onClose(), 1500);
    } catch (err: any) {
      console.error("Failed to save draft:", err);
      let msg = err?.message || "Failed to save draft.";
      try {
        const parsed = JSON.parse(msg);
        msg = parsed?.detail || parsed?.message || msg;
      } catch {}
      setScheduleError(msg);
    } finally {
      setDraftLoading(false);
    }
  };

  if (!isOpen) return null;

  // --- FIX: Extract data from selected context ---
  // Filter messages that are in the selectedMessages list
  const selectedMsgs = messages.filter(m => selectedMessages.includes(m.id));
  
  // Find the last AI message in the selection for plan and response
  const selectedAiMsg = [...selectedMsgs].reverse().find(m => m.role === 'ai' || m.role === 'assistant');
  // Find the first user message in the selection for the prompt
  const selectedUserMsg = selectedMsgs.find(m => m.role === 'user' || m.role === 'human');

  const userPrompt = selectedUserMsg?.content || "No prompt selected";
  const aiResponse = selectedAiMsg?.content || "No response selected";
  
  // Use the plan from the selected AI message
  const displayPlan = selectedAiMsg?.plan || [];

  // Tools auto-derived from the chat message(s) the user selected (see
  // chat_page.tsx) — not a manual checkbox list.
  const selectedToolLogs = (toolLogs || []).filter(l => selectedTools.includes(l.id));
  const successSelectedTools = selectedToolLogs.filter(
    log => log.status === 'SUCCESS' || log.status === 'COMPLETED'
  );
  // Keep full session list only for the tab badge (shows 0 if nothing selected)
  const allTools = toolLogs || [];
  const successTools = successSelectedTools;

  // --- FIX: Ensure activeTab switches correctly ---
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-xl p-4 md:p-8">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full max-w-[1400px] h-full max-h-[95vh] bg-background rounded-[24px] shadow-2xl border border-border overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="min-h-14 sm:h-20 px-4 sm:px-8 border-b border-border flex items-center justify-between bg-card/50 shrink-0 py-3 sm:py-0">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="w-9 h-9 sm:w-12 sm:h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shrink-0">
              <Calendar className="w-5 h-5 sm:w-6 sm:h-6 text-indigo-500" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base sm:text-xl font-black tracking-tight text-foreground uppercase truncate">Schedule Automation Task</h1>
              <p className="hidden sm:block text-xs text-muted-foreground font-bold uppercase tracking-widest">Configure and schedule your automation to run on a recurring basis.</p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={onClose} 
            className="h-10 w-10 sm:h-12 sm:w-12 rounded-2xl hover:bg-foreground/5 text-muted-foreground hover:text-foreground transition-all shrink-0"
          >
            <X className="w-5 h-5 sm:w-6 sm:h-6" />
          </Button>
        </div>

        <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
          {/* Left Panel - Configuration */}
          <div className="w-full md:w-[38%] lg:w-[35%] border-b md:border-b-0 md:border-r border-border bg-background flex flex-col overflow-y-auto hide-scrollbar p-4 sm:p-6 md:p-8 space-y-6 sm:space-y-8 shrink-0 max-h-[45vh] md:max-h-none">
            
            {/* 1. Schedule Configuration */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500 text-[10px] font-black border border-emerald-500/20">1</div>
                <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Schedule Configuration</h3>
              </div>
              
              <div className="space-y-4">
                <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Frequency</label>
                <div className="grid grid-cols-3 gap-3">
                  {['daily', 'weekly', 'monthly'].map((type) => (
                    <button
                      key={type}
                      onClick={() => setScheduleType(type)}
                      className={cn(
                        "flex flex-col items-center justify-center gap-3 p-5 rounded-2xl border transition-all duration-300 group",
                        scheduleType === type 
                          ? "bg-indigo-500/10 border-indigo-500 text-foreground shadow-[0_0_20px_rgba(99,102,241,0.15)]" 
                          : "bg-card border-border text-muted-foreground hover:border-border hover:text-muted-foreground"
                      )}
                    >
                      <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
                        scheduleType === type ? "bg-indigo-500 text-foreground" : "bg-border text-muted-foreground group-hover:bg-muted"
                      )}>
                        <Calendar className="w-5 h-5" />
                      </div>
                      <span className="text-[11px] font-black uppercase tracking-widest">{type}</span>
                      {scheduleType === type && (
                        <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
                          <Check className="w-2.5 h-2.5 text-foreground" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {scheduleType === 'weekly' && (
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Day of Week</label>
                  <div className="grid grid-cols-7 gap-1.5">
                    {DAY_OF_WEEK_OPTIONS.map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => setScheduleDayOfWeek(day.value)}
                        className={cn(
                          "py-2.5 rounded-lg border text-[10px] font-black uppercase tracking-widest transition-all",
                          scheduleDayOfWeek === day.value
                            ? "bg-indigo-500 border-indigo-500 text-foreground shadow-[0_0_12px_rgba(99,102,241,0.25)]"
                            : "bg-card border-border text-muted-foreground hover:border-border hover:text-muted-foreground"
                        )}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Time of Day</label>
                  <div className="relative">
                    <Clock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <select
                      value={scheduleTime}
                      onChange={e => setScheduleTime(e.target.value)}
                      className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-card border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none"
                    >
                      {TIME_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Timezone</label>
                  <div className="relative">
                    <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <select
                      value={timezone}
                      onChange={e => setTimezone(e.target.value)}
                      className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-card border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none"
                    >
                      {TIMEZONE_OPTIONS.map(tz => (
                        <option key={tz.value} value={tz.value}>{tz.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                  </div>
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 space-y-3">
                <div className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Next Run Preview</div>
                <div className="flex items-center gap-4">
                  <Calendar className="w-5 h-5 text-indigo-500" />
                  <div>
                    <div className="text-sm font-bold text-foreground">{computeNextRun(scheduleType, scheduleTime, timezone, scheduleDayOfWeek).split(" at ")[0]}</div>
                    <div className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">
                      at {computeNextRun(scheduleType, scheduleTime, timezone, scheduleDayOfWeek).split(" at ")[1]} ({TIMEZONE_OPTIONS.find(t => t.value === timezone)?.abbr || timezone})
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* 2. Notifications */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-500 text-[10px] font-black border border-indigo-500/20">2</div>
                <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Notifications</h3>
              </div>
              <div className="space-y-4">
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-indigo-500 transition-colors" />
                  <input
                    type="email"
                    placeholder="example@company.com"
                    value={emailRecipient}
                    onChange={(e) => setEmailRecipient(e.target.value)}
                    className="w-full pl-11 pr-4 py-4 rounded-xl bg-card border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all placeholder:text-muted-foreground"
                  />
                  <button className="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 rounded-lg bg-border text-[10px] font-black text-muted-foreground hover:bg-muted transition-colors uppercase tracking-widest">
                    + Add more
                  </button>
                </div>
                <div className="flex items-center gap-2 px-1">
                  <Bell className="w-3.5 h-3.5 text-indigo-500" />
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Receive results and alerts via email.</span>
                </div>
              </div>
            </section>

            {/* 3. Task Details */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-purple-500/10 flex items-center justify-center text-purple-500 text-[10px] font-black border border-purple-500/20">3</div>
                <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Task Details</h3>
              </div>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Task Name <span className="text-red-500">*</span></label>
                  <input
                    ref={taskNameInputRef}
                    type="text"
                    placeholder="e.g. Check website availability"
                    value={taskName}
                    onChange={(e) => {
                      setTaskName(e.target.value);
                      if (e.target.value.trim()) {
                        setTaskNameMissing(false);
                        setScheduleError("");
                      }
                    }}
                    className={cn(
                      "w-full px-4 py-4 rounded-xl bg-card border text-sm font-bold text-foreground focus:outline-none focus:ring-2 transition-all placeholder:text-muted-foreground",
                      taskNameMissing
                        ? "border-red-500 focus:ring-red-500/20"
                        : "border-border focus:ring-indigo-500/20"
                    )}
                  />
                  {taskNameMissing && (
                    <p className="text-[10px] font-bold text-red-500 ml-1">Task name is required to confirm the schedule.</p>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Description (Optional)</label>
                  <textarea
                    placeholder="Provide a brief description of this task..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-4 py-4 rounded-xl bg-card border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all placeholder:text-muted-foreground min-h-[100px] resize-none"
                  />
                  <div className="text-right text-[10px] font-bold text-muted-foreground uppercase tracking-widest">0 / 500</div>
                </div>
              </div>
            </section>

            {/* 4. Advanced Options */}
            <section className="space-y-6 pb-8">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-500 text-[10px] font-black border border-indigo-500/20">4</div>
                  <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Advanced Options</h3>
                </div>
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="p-5 rounded-2xl bg-card border border-border space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-indigo-500" />
                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Retry Attempts</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={() => setRetryCount(Math.max(0, retryCount - 1))} className="w-8 h-8 rounded-lg bg-border border border-border flex items-center justify-center text-foreground hover:bg-muted">-</button>
                    <span className="text-sm font-black text-foreground w-4 text-center">{retryCount}</span>
                    <button onClick={() => setRetryCount(Math.min(5, retryCount + 1))} className="w-8 h-8 rounded-lg bg-border border border-border flex items-center justify-center text-foreground hover:bg-muted">+</button>
                  </div>
                </div>
                <div className="h-px bg-border" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Execution Timeout</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input 
                      type="number" 
                      value={timeout} 
                      onChange={(e) => setTimeoutVal(parseInt(e.target.value))}
                      className="w-16 px-2 py-1.5 rounded-lg bg-border border border-border text-xs font-black text-foreground text-center focus:outline-none"
                    />
                    <span className="text-[10px] font-bold text-muted-foreground uppercase">sec</span>
                  </div>
                </div>
                <div className="h-px bg-border" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-sky-500" />
                    <div>
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Browser Mode</span>
                      <p className="text-[9px] text-muted-foreground font-bold uppercase tracking-wider mt-0.5">
                        {headless ? "Headless — no visible window" : "Headed — browser window visible"}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setHeadless(h => !h)}
                    className={cn(
                      "relative w-11 h-6 rounded-full transition-colors duration-200 border",
                      headless
                        ? "bg-indigo-600 border-indigo-500"
                        : "bg-emerald-600 border-emerald-500"
                    )}
                  >
                    <span className={cn(
                      "absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200",
                      headless ? "left-0.5" : "left-[22px]"
                    )} />
                  </button>
                </div>
              </div>
            </section>
          </div>

          {/* Right Panel - AI Context & Preview */}
          <div className="flex-1 bg-background flex flex-col overflow-hidden">
            {/* Tabs */}
            <div className="px-4 sm:px-8 pt-4 sm:pt-6 flex items-center gap-4 sm:gap-8 border-b border-border shrink-0 overflow-x-auto scroll-x-smooth">
              {[
                { id: 'context', label: 'AI Context', icon: Brain },
                { id: 'plan', label: 'AI Plan', icon: Workflow },
                { id: 'response', label: 'Response', icon: MessageSquare },
                { id: 'tools', label: 'Tools', icon: Cpu, count: successTools.length }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={cn(
                    "flex shrink-0 items-center gap-2 pb-4 text-[11px] font-black uppercase tracking-[0.15em] transition-all relative",
                    activeTab === tab.id ? "text-indigo-500" : "text-muted-foreground hover:text-muted-foreground"
                  )}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 rounded-md bg-card border border-border text-[9px] text-indigo-400">
                      {tab.count}
                    </span>
                  )}
                  {activeTab === tab.id && (
                    <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
                  )}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-8 hide-scrollbar space-y-6 sm:space-y-8">
              <AnimatePresence mode="wait">
                {activeTab === 'context' && (
                  <motion.div
                    key="context"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6"
                  >
                    {/* User Inputs */}
                    <div className="p-6 rounded-2xl bg-card border border-border space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <UserIcon className="w-4 h-4 text-emerald-500" />
                          <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">User Inputs</h4>
                        </div>
                        <Info className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">View the inputs provided for this task.</p>
                      <div className="p-4 rounded-xl bg-background border border-border min-h-[120px] overflow-y-auto max-h-[200px] hide-scrollbar">
                        <p className="text-sm text-muted-foreground leading-relaxed italic">"{userPrompt}"</p>
                      </div>
                      <button className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-border hover:bg-muted transition-colors group">
                        <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">View Details</span>
                        <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-all" />
                      </button>
                    </div>

                    {/* AI Understanding */}
                    <div className="p-6 rounded-2xl bg-card border border-border space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <Sparkles className="w-4 h-4 text-indigo-500" />
                          <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">AI Plan (Agent Plan)</h4>
                        </div>
                        <Info className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">Steps the agent will follow to complete the task.</p>
                      <div className="space-y-3 overflow-y-auto max-h-[200px] hide-scrollbar">
                        {displayPlan && displayPlan.length > 0 ? (
                          displayPlan.map((task, i) => (
                            <div key={task.id || i} className="flex items-center gap-3">
                              <div className="w-5 h-5 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[9px] font-black text-indigo-500 shrink-0">{i + 1}</div>
                              <span className="text-xs text-muted-foreground font-medium truncate">{task.title}</span>
                            </div>
                          ))
                        ) : (
                          <div className="py-6 flex flex-col items-center justify-center gap-2">
                            <Workflow className="w-6 h-6 text-muted-foreground/60" />
                            <p className="text-[10px] font-black text-muted-foreground/60 uppercase tracking-widest">No plan in selected context</p>
                          </div>
                        )}
                      </div>
                      <button 
                        onClick={() => handleTabChange('plan')}
                        className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-border hover:bg-muted transition-colors group"
                      >
                        <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">View Full Plan</span>
                        <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-all" />
                      </button>
                    </div>

                    {/* AI Response Summary */}
                    <div className="col-span-2 p-6 rounded-2xl bg-card border border-border space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <Target className="w-4 h-4 text-purple-500" />
                          <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">AI Response (Summary)</h4>
                        </div>
                        <Info className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">AI understanding and response.</p>
                      <div className="p-5 rounded-xl bg-background border border-border overflow-y-auto max-h-[200px] hide-scrollbar">
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {aiResponse || "I will check the website availability by navigating to the provided URL, validating the HTTP status code and page content. If the site is down or returns an error, I will notify you via email with the details."}
                        </p>
                      </div>
                      <button 
                        onClick={() => handleTabChange('response')}
                        className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-border hover:bg-muted transition-colors group"
                      >
                        <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">View Full Response</span>
                        <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-all" />
                      </button>
                    </div>
                  </motion.div>
                )}

                {activeTab === 'plan' && (
                  <motion.div
                    key="plan"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-6"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                        <Workflow className="w-5 h-5 text-indigo-500" />
                      </div>
                      <div>
                        <h4 className="text-sm font-black text-foreground uppercase tracking-widest">AI Plan</h4>
                        <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">Full step-by-step execution plan.</p>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {!selectedAiMsg ? (
                        <div className="py-20 flex flex-col items-center justify-center bg-card border border-border rounded-[32px] border-dashed">
                          <Workflow className="w-10 h-10 text-muted-foreground/60 mb-4" />
                          <p className="text-xs font-black text-muted-foreground uppercase tracking-widest">Select a chat message to see AI plan</p>
                        </div>
                      ) : displayPlan && displayPlan.length > 0 ? (
                        displayPlan.map((task, i) => (
                          <div key={task.id || i} className="p-5 rounded-2xl bg-card border border-border space-y-3">
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="w-6 h-6 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[10px] font-black text-indigo-500 shrink-0">{i + 1}</div>
                                <span className="text-xs font-black text-foreground uppercase tracking-wider truncate">{task.title}</span>
                              </div>
                              <div className="px-2 py-0.5 rounded-md bg-background border border-border text-[9px] text-muted-foreground font-bold uppercase shrink-0">
                                {task.status || "pending"}
                              </div>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed pl-9">{task.description}</p>
                            {task.subtasks && task.subtasks.length > 0 && (
                              <div className="pl-9 pt-2 space-y-2">
                                {task.subtasks.map((sub: Subtask, si: number) => (
                                  <div key={sub.id || si} className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                    <div className="w-1.5 h-1.5 rounded-full bg-muted" />
                                    <span>{sub.title}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="py-20 flex flex-col items-center justify-center bg-card border border-border rounded-[32px] border-dashed">
                          <Workflow className="w-10 h-10 text-muted-foreground/60 mb-4" />
                          <p className="text-xs font-black text-muted-foreground uppercase tracking-widest">No plan data available</p>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}

                {activeTab === 'response' && (
                  <motion.div
                    key="response"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-6"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
                        <MessageSquare className="w-5 h-5 text-purple-500" />
                      </div>
                      <div>
                        <h4 className="text-sm font-black text-foreground uppercase tracking-widest">AI Response</h4>
                        <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">The full response for the selected context.</p>
                      </div>
                    </div>

                    {!selectedAiMsg ? (
                      <div className="py-20 flex flex-col items-center justify-center bg-card border border-border rounded-[32px] border-dashed min-h-[400px]">
                        <MessageSquare className="w-10 h-10 text-muted-foreground/60 mb-4" />
                        <p className="text-xs font-black text-muted-foreground uppercase tracking-widest">Select a chat message to see AI response</p>
                      </div>
                    ) : (
                      <div className="p-8 rounded-[32px] bg-card border border-border min-h-[400px] overflow-y-auto hide-scrollbar">
                        <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap text-sm">
                          {aiResponse || "No AI response available"}
                        </p>
                      </div>
                    )}
                  </motion.div>
                )}

                {activeTab === 'tools' && (
                  <motion.div
                    key="tools"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-6"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                          <Cpu className="w-5 h-5 text-indigo-500" />
                        </div>
                        <div>
                          <h4 className="text-sm font-black text-foreground uppercase tracking-widest">
                            MCP Tools ({successSelectedTools.length} / {selectedToolLogs.length})
                          </h4>
                          <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">
                            {successSelectedTools.length === 0
                              ? "No successful tools selected for script"
                              : "Success tools included in script generation"}
                          </p>
                        </div>
                      </div>
                      {/* Info pill: how many will be sent */}
                      {successSelectedTools.length === 0 ? (
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                          <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          <span className="text-[10px] font-black text-amber-500 uppercase tracking-widest">
                            0 will be sent
                          </span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">
                            {successSelectedTools.length} will be sent
                          </span>
                        </div>
                      )}
                    </div>

                    {selectedTools.length === 0 ? (
                      <div className="py-14 flex flex-col items-center justify-center bg-indigo-500/5 border border-indigo-500/20 rounded-[32px] border-dashed gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                          <List className="w-6 h-6 text-indigo-400" />
                        </div>
                        <div className="text-center px-6">
                          <p className="text-xs font-black text-indigo-400 uppercase tracking-widest mb-1">No Tools Selected</p>
                          <p className="text-[10px] text-indigo-400/60 font-bold uppercase tracking-wider leading-relaxed">
                            Select the chat message(s) that used tools and they'll be included here automatically.<br />Only success tools are used for script generation.
                          </p>
                        </div>
                      </div>
                    ) : selectedToolLogs.length === 0 ? (
                      <div className="py-14 flex flex-col items-center justify-center bg-amber-500/5 border border-amber-500/20 rounded-[32px] border-dashed gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                          <AlertCircle className="w-6 h-6 text-amber-400" />
                        </div>
                        <div className="text-center px-6">
                          <p className="text-xs font-black text-amber-400 uppercase tracking-widest mb-1">No Matching Tool Logs</p>
                          <p className="text-[10px] text-amber-400/60 font-bold uppercase tracking-wider leading-relaxed">
                            Selected tool IDs were not found in the current session log.
                          </p>
                        </div>
                      </div>
                    ) : successSelectedTools.length === 0 ? (
                      <div className="py-14 flex flex-col items-center justify-center bg-amber-500/5 border border-amber-500/20 rounded-[32px] border-dashed gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                          <AlertCircle className="w-6 h-6 text-amber-400" />
                        </div>
                        <div className="text-center px-6">
                          <p className="text-xs font-black text-amber-400 uppercase tracking-widest mb-1">No Successful Tools</p>
                          <p className="text-[10px] text-amber-400/60 font-bold uppercase tracking-wider leading-relaxed">
                            None of the selected tools completed successfully in the chat logs.<br />Only successful tool executions can be included in the automated schedule script.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                        {successSelectedTools.map((log, i) => {
                          const isSuccess = log.status === 'SUCCESS' || log.status === 'COMPLETED';
                          const isFailed  = log.status === 'FAILED'  || log.status === 'ERROR';
                          return (
                            <div
                              key={log.id || i}
                              className={cn(
                                "p-5 rounded-2xl border transition-all",
                                isSuccess
                                  ? "bg-card border-emerald-500/30"
                                  : isFailed
                                  ? "bg-card/50 border-border opacity-50"
                                  : "bg-card border-border"
                              )}
                            >
                              <div className="flex items-center gap-3">
                                <div className={cn(
                                  "w-9 h-9 rounded-xl border flex items-center justify-center shrink-0",
                                  isSuccess
                                    ? "bg-emerald-500/10 border-emerald-500/20"
                                    : "bg-background border-border"
                                )}>
                                  <Terminal className={cn(
                                    "w-4 h-4",
                                    isSuccess ? "text-emerald-500" : "text-muted-foreground"
                                  )} />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="text-xs font-black text-foreground uppercase tracking-wider truncate" title={log.tool_name}>
                                    {log.tool_name}
                                  </div>
                                  <div className={cn(
                                    "text-[10px] font-bold uppercase tracking-widest",
                                    isSuccess ? "text-emerald-500" :
                                    isFailed  ? "text-red-400" :
                                    "text-muted-foreground"
                                  )}>
                                    {log.status}
                                    {isSuccess && (
                                      <span className="ml-2 text-[9px] text-emerald-600">✓ included</span>
                                    )}
                                    {isFailed && (
                                      <span className="ml-2 text-[9px] text-red-700">✗ excluded</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <div className="mt-3 p-2 rounded-lg bg-black/20 border border-white/5 text-[9px] text-muted-foreground font-mono line-clamp-3 overflow-hidden">
                                {summarizeOutput(log.tool_output, 300)}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Execution Flow Preview */}
              <div className="space-y-6">
                <div className="flex items-center gap-3">
                  <Workflow className="w-5 h-5 text-indigo-500" />
                  <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">Execution Flow Preview</h4>
                </div>
                <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">How this task will be executed.</p>
                
                <div className="relative p-8 rounded-[32px] bg-card border border-border overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5" />
                  
                  <div className="relative flex items-center justify-between gap-4">
                    {[
                      { label: 'Generate AI Plan', sub: 'Understand task & create plan', icon: UserIcon, color: 'text-emerald-500' },
                      { label: 'Generate Script (Playwright)', sub: 'Create automation script', icon: Database, color: 'text-indigo-500' },
                      { label: 'Execute Playwright', sub: 'Run script in browser', icon: Cpu, color: 'text-purple-500' }
                    ].map((node, i) => (
                      <React.Fragment key={i}>
                        <div className="flex flex-col items-center gap-4 text-center max-w-[140px]">
                          <div className="w-12 h-12 rounded-2xl bg-background border border-border flex items-center justify-center shadow-xl">
                            <node.icon className={cn("w-6 h-6", node.color)} />
                          </div>
                          <div className="space-y-1">
                            <div className="text-[10px] font-black text-foreground uppercase tracking-widest">{node.label}</div>
                            <div className="text-[9px] text-muted-foreground font-bold uppercase tracking-tight leading-tight">{node.sub}</div>
                          </div>
                        </div>
                        {i < 2 && <ArrowRight className="w-4 h-4 text-border" />}
                      </React.Fragment>
                    ))}

                    <ArrowRight className="w-4 h-4 text-border" />

                    {/* Fallback Node */}
                    <div className="relative group">
                      <div className="absolute -inset-4 bg-indigo-500/5 rounded-3xl border border-indigo-500/20 border-dashed" />
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-[9px] font-black text-indigo-400 uppercase tracking-widest">If Failed</div>
                      <div className="flex flex-col items-center gap-4 text-center max-w-[140px] relative z-10">
                        <div className="w-12 h-12 rounded-2xl bg-background border border-indigo-500/30 flex items-center justify-center shadow-xl">
                          <RefreshCw className="w-6 h-6 text-indigo-400" />
                        </div>
                        <div className="space-y-1">
                          <div className="text-[10px] font-black text-foreground uppercase tracking-widest">Browser Use</div>
                          <div className="text-[9px] text-muted-foreground font-bold uppercase tracking-tight leading-tight">(Attempt 1-3)</div>
                          <div className="text-[8px] text-indigo-400 font-black uppercase tracking-widest">Fallback & retry up to 3 attempts</div>
                        </div>
                      </div>
                    </div>

                    <ArrowRight className="w-4 h-4 text-border" />

                    <div className="flex flex-col items-center gap-4 text-center max-w-[140px]">
                      <div className="w-12 h-12 rounded-2xl bg-background border border-emerald-500/30 flex items-center justify-center shadow-xl">
                        <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="text-[10px] font-black text-foreground uppercase tracking-widest">Complete Task</div>
                        <div className="text-[9px] text-muted-foreground font-bold uppercase tracking-tight leading-tight">Store results & notify</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Execution Config Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                  {[
                    { label: 'Retry Attempts', val: `Max ${retryCount} attempts`, icon: RefreshCw },
                    { label: 'Timeout', val: `${timeout} seconds`, icon: Clock },
                    { label: 'Browser', val: headless ? 'Chromium (Headless)' : 'Chromium (Headed)', icon: Globe },
                    { label: 'Notification', val: 'On Failure & Success', icon: Bell },
                    { label: 'Log Retention', val: '30 Days', icon: Database }
                  ].map((item, i) => (
                    <div key={i} className={cn("p-4 rounded-xl bg-card border border-border space-y-2", i === 4 && "col-span-1")}>
                      <div className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">{item.label}</div>
                      <div className="text-[11px] font-bold text-foreground uppercase tracking-wider">{item.val}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Selection Summary */}
              <div className="p-8 rounded-[32px] bg-gradient-to-br from-card to-background border border-border relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-10">
                  <Layout className="w-32 h-32 text-indigo-500" />
                </div>
                <div className="relative z-10 space-y-6">
                  <div className="flex items-center gap-3">
                    <Layers className="w-5 h-5 text-indigo-500" />
                    <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">Selection Summary</h4>
                  </div>
                  <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-wider">Review your schedule configuration.</p>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 sm:gap-x-12 gap-y-4 sm:gap-y-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Calendar className="w-3.5 h-3.5" /> Frequency
                        </div>
                        <span className="text-xs font-black text-foreground uppercase">{scheduleType}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Clock className="w-3.5 h-3.5" /> Time of Day
                        </div>
                        <span className="text-xs font-black text-foreground uppercase">
                          {TIME_OPTIONS.find(t => t.value === scheduleTime)?.label || scheduleTime}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Globe className="w-3.5 h-3.5" /> Timezone
                        </div>
                        <span className="text-xs font-black text-foreground uppercase">
                          {TIMEZONE_OPTIONS.find(t => t.value === timezone)?.abbr || timezone}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Mail className="w-3.5 h-3.5" /> Delivery Email
                        </div>
                        <span className="text-xs font-black text-foreground truncate max-w-[150px]">{emailRecipient || "example@company.com"}</span>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Terminal className="w-3.5 h-3.5" /> Task Name
                        </div>
                        <span className="text-xs font-black text-foreground uppercase truncate max-w-[150px]">{taskName || "Check website availability"}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Calendar className="w-3.5 h-3.5" /> Next Run
                        </div>
                        <span className="text-xs font-black text-foreground uppercase text-right">{computeNextRun(scheduleType, scheduleTime, timezone, scheduleDayOfWeek)}</span>
                      </div>
                      <div className="pt-4">
                        <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/20 flex items-center gap-3">
                          <Shield className="w-5 h-5 text-emerald-500" />
                          <div>
                            <div className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Secure & Reilable</div>
                            <div className="text-[9px] text-muted-foreground font-bold uppercase tracking-tight leading-tight">Your schedule is encrypted and runs on our secure infrastructure.</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-4 sm:px-8 py-3 sm:py-4 border-t border-border bg-card/50 flex flex-col gap-3 shrink-0">
              {showEmptyToolsWarning && (
                <div className="flex flex-col sm:flex-row items-start gap-3 px-4 sm:px-5 py-3 sm:py-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-black text-amber-400 uppercase tracking-widest mb-1">No Tool Activity Recorded</p>
                    <p className="text-[11px] text-amber-400/80 font-bold leading-relaxed">
                      No MCP tool runs were found. The generated script may be generic without tool context.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleCreateSchedule(true)}
                      className="text-[10px] font-black text-amber-400 border border-amber-500/40 hover:bg-amber-500/20 transition-colors px-3 py-1.5 rounded-lg uppercase tracking-widest whitespace-nowrap"
                    >
                      Continue Anyway
                    </button>
                    <button
                      onClick={() => setShowEmptyToolsWarning(false)}
                      className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
              {scheduleError && (
                <div className="flex items-start gap-3 px-4 sm:px-5 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] font-bold text-red-400 leading-relaxed">{scheduleError}</p>
                </div>
              )}
              {scheduleSuccess && (
                <div className="flex items-center gap-3 px-4 sm:px-5 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <p className="text-[11px] font-bold text-emerald-400 uppercase tracking-widest">Schedule created successfully!</p>
                </div>
              )}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4">
                <button 
                  onClick={onClose} 
                  className="text-[11px] font-black text-muted-foreground hover:text-foreground transition-colors uppercase tracking-[0.2em] self-start sm:self-auto"
                >
                  Cancel
                </button>
                <div className="flex items-center gap-2 sm:gap-4 w-full sm:w-auto">
                  <Button 
                    variant="outline"
                    onClick={handleSaveDraft}
                    disabled={draftLoading || draftSuccess || loading || scheduleSuccess}
                    className="h-11 sm:h-14 flex-1 sm:flex-none sm:px-8 rounded-2xl border-border bg-transparent text-muted-foreground text-[11px] font-black uppercase tracking-[0.15em] hover:bg-foreground/5 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {draftLoading ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Saving…</span>
                      </>
                    ) : draftSuccess ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-amber-400">Draft Saved!</span>
                      </>
                    ) : (
                      <span>Save Draft</span>
                    )}
                  </Button>
                  <Button 
                    onClick={() => handleCreateSchedule()}
                    disabled={loading || scheduleSuccess}
                    className="h-11 sm:h-14 flex-1 sm:flex-none sm:px-12 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-foreground text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 sm:min-w-[200px] flex items-center justify-center gap-2 sm:gap-3"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : scheduleSuccess ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Scheduled!</span>
                      </>
                    ) : (
                      <>
                        <Calendar className="w-4 h-4" />
                        <span>Confirm Schedule</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
