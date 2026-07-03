import * as React from "react";
import { Button } from "./button";
import { sciparserApi } from "../../api";
import { wsUrl } from "../../config";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { 
  Calendar, Clock, Code, Play, Pencil, Trash, 
  ChevronLeft, Mail, CheckCircle2, AlertCircle,
  ExternalLink, Copy, Download, RefreshCw, Pause,
  ChevronRight, Activity, Cpu, Globe,
  Layout, Layers, Zap, Shield, Info, Search,
  Terminal, Workflow, Target, MessageSquare,
  ArrowRight, Loader2, Sparkles, User as UserIcon,
  Check, X, MoreVertical, Maximize2, ZoomIn,
  History, Timer, Gauge, Network,
  Brain, HardDrive
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Schedule {
  schedule_id: string;
  title: string;
  schedule_type: string;
  schedule_time?: string;
  email_recipient: string | null;
  status: string;
  generated_script: string;
  extracted_content: string;
  assistant_response?: string;
  plan_data?: string;
  user_prompt?: string;
  next_run?: string | null;
  last_run?: string | null;
  created_at: string;
  updated_at?: string;
}

interface ScheduleRun {
  run_id: string;
  status: string;
  created_at: string;
  duration_seconds?: number;
  engine?: string;
  attempt?: number;
  output?: string;
  error_log?: string;
}

interface SchedulesPageProps {
  onBack: () => void;
}

const ModalShell: React.FC<{
  title: string;
  icon: React.ElementType;
  onClose: () => void;
  children: React.ReactNode;
  maxWidth?: string;
  headerAction?: React.ReactNode;
}> = ({ title, icon: Icon, onClose, children, maxWidth = "max-w-3xl", headerAction }) => (
  <div className="fixed inset-0 z-[130] flex items-center justify-center bg-background/80 backdrop-blur-xl p-4">
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={cn("w-full bg-card rounded-[32px] shadow-2xl border border-border flex flex-col max-h-[85vh]", maxWidth)}
    >
      <div className="px-6 sm:px-8 py-5 sm:py-6 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
            <Icon className="w-5 h-5 text-indigo-500" />
          </div>
          <h3 className="font-black text-base sm:text-xl text-foreground uppercase tracking-tight">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          {headerAction}
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground shrink-0">
            <X className="w-6 h-6" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6 sm:p-8">{children}</div>
    </motion.div>
  </div>
);

export const SchedulesPage: React.FC<SchedulesPageProps> = ({ onBack }) => {
  const { theme } = useTheme();
  const [schedules, setSchedules] = React.useState<Schedule[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedSchedule, setSelectedSchedule] = React.useState<Schedule | null>(null);
  const [copySuccess, setCopySuccess] = React.useState<string | null>(null);
  const [isRunning, setIsRunning] = React.useState(false);
  const [isActivating, setIsActivating] = React.useState(false);
  const [activateError, setActivateError] = React.useState<string | null>(null);
  const [isEditing, setIsEditing] = React.useState(false);
  const [editData, setEditData] = React.useState({ title: "", type: "", email: "" });
  const [deleteConfirmId, setDeleteConfirmId] = React.useState<string | null>(null);
  const [activeModal, setActiveModal] = React.useState<null | "script" | "aiplan" | "history" | "browser" | "result" | "runDetail">(null);
  const [selectedRun, setSelectedRun] = React.useState<ScheduleRun | null>(null);
  const [currentProgress, setCurrentProgress] = React.useState(0);
  const [liveLogs, setLiveLogs] = React.useState<any[]>([]);
  const [liveScreenshot, setLiveScreenshot] = React.useState<string | null>(null);
  const [resourceUsage, setResourceUsage] = React.useState<{ cpu_percent: number; memory_mb: number } | null>(null);
  const [runStartedAt, setRunStartedAt] = React.useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);
  const [pipelineSteps, setPipelineSteps] = React.useState([
    { id: 1, name: "Initialize", status: "pending", duration: "--", time: "--" },
    { id: 2, name: "Generate Plan", status: "pending", duration: "--", time: "--" },
    { id: 3, name: "Generate Script", status: "pending", duration: "--", time: "--" },
    { id: 4, name: "Execute Automation", status: "pending", duration: "--", time: "--" },
    { id: 5, name: "Extract Result", status: "pending", duration: "--", time: "--" },
    { id: 6, name: "Save Result", status: "pending", duration: "--", time: "--" }
  ]);
  
  const [runs, setRuns] = React.useState<ScheduleRun[]>([]);

  // Resizable sidebar
  const [sidebarWidth, setSidebarWidth] = React.useState(280);
  const [isResizingSidebar, setIsResizingSidebar] = React.useState(false);
  const sidebarContainerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isResizingSidebar) return;
      if (!sidebarContainerRef.current) return;
      // Container-relative: measure from the flex container's left edge
      const containerLeft = sidebarContainerRef.current.getBoundingClientRect().left;
      const newWidth = e.clientX - containerLeft;
      setSidebarWidth(Math.min(480, Math.max(200, newWidth)));
    };
    const onMouseUp = () => {
      if (isResizingSidebar) {
        setIsResizingSidebar(false);
        document.body.style.cursor = 'default';
      }
    };
    if (isResizingSidebar) {
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      document.body.style.cursor = 'col-resize';
    }
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, [isResizingSidebar]);

  React.useEffect(() => {
    fetchSchedules();
  }, []);

  React.useEffect(() => {
    if (selectedSchedule) {
      fetchScheduleRuns(selectedSchedule.schedule_id);
    }
  }, [selectedSchedule]);

  const fetchScheduleRuns = async (scheduleId: string) => {
    try {
      const data = await sciparserApi.getScheduleRuns(scheduleId);
      setRuns(data || []);
    } catch (err) {
      console.error("Failed to fetch runs:", err);
    }
  };

  // Live elapsed-time ticker while a run is in progress
  React.useEffect(() => {
    if (!isRunning || !runStartedAt) return;
    const tick = () => setElapsedSeconds(Math.floor((Date.now() - runStartedAt) / 1000));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [isRunning, runStartedAt]);

  // WebSocket for real-time monitoring — reconnects if dropped while running
  React.useEffect(() => {
    if (!selectedSchedule || !isRunning) return;

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const token = localStorage.getItem("access_token");
      const scheduleWsUrl = wsUrl(`/sciparser/v1/ws/schedule/${selectedSchedule.schedule_id}?token=${token}`);
      ws = new WebSocket(scheduleWsUrl);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'log') {
            setLiveLogs(prev => [...prev, msg]);
          } else if (msg.type === 'pipeline_update') {
            setPipelineSteps(prev => prev.map(step =>
              step.id === msg.step_id ? { ...step, status: msg.status, time: msg.time || step.time } : step
            ));
            setCurrentProgress(Math.round((msg.step_id / 6) * 100));
            // Mark done when final step completes or any step fails
            if ((msg.step_id === 6 && msg.status === 'completed') || msg.status === 'failed') {
              setIsRunning(false);
              setResourceUsage(null);
              setTimeout(fetchSchedules, 1500);
            }
          } else if (msg.type === 'screenshot') {
            setLiveScreenshot(msg.frame);
          } else if (msg.type === 'resource_usage') {
            setResourceUsage({ cpu_percent: msg.cpu_percent, memory_mb: msg.memory_mb });
          }
        } catch (err) {
          console.error("Schedule WS error:", err);
        }
      };

      ws.onclose = () => {
        if (!cancelled && isRunning) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [selectedSchedule?.schedule_id, isRunning]);

  const fetchSchedules = async () => {
    try {
      setLoading(true);
      const data = await sciparserApi.getSchedules();
      setSchedules(data);
      if (data.length > 0 && !selectedSchedule) {
        setSelectedSchedule(data[0]);
      } else if (selectedSchedule) {
        const updated = data.find((s: any) => s.schedule_id === selectedSchedule.schedule_id);
        if (updated) setSelectedSchedule(updated);
      }
    } catch (err) {
      console.error("Failed to fetch schedules:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    try {
      await sciparserApi.deleteSchedule(deleteConfirmId);
      const updatedSchedules = schedules.filter(s => s.schedule_id !== deleteConfirmId);
      setSchedules(updatedSchedules);
      
      if (selectedSchedule?.schedule_id === deleteConfirmId) {
        setSelectedSchedule(updatedSchedules.length > 0 ? updatedSchedules[0] : null);
      }
      setDeleteConfirmId(null);
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const handleUpdate = async () => {
    if (!selectedSchedule) return;
    try {
      await sciparserApi.updateSchedule(selectedSchedule.schedule_id, {
        title: editData.title,
        schedule_type: editData.type,
        email_recipient: editData.email
      });
      setIsEditing(false);
      fetchSchedules();
    } catch (err) {
      console.error("Update failed:", err);
    }
  };

  const handleRunNow = async () => {
    if (!selectedSchedule) return;
    try {
      setIsRunning(true);
      setCurrentProgress(0);
      setLiveLogs([]);
      setLiveScreenshot(null);
      setResourceUsage(null);
      setRunStartedAt(Date.now());
      setElapsedSeconds(0);
      setPipelineSteps(prev => prev.map(s => ({ ...s, status: 'pending', time: '--' })));
      
      await sciparserApi.runSchedule(selectedSchedule.schedule_id);
      // isRunning is cleared by WS completion event; fallback after 10 min
      setTimeout(() => setIsRunning(false), 600_000);
    } catch (err) {
      console.error("Failed to run schedule:", err);
      setIsRunning(false);
    }
  };

  const handleActivate = async () => {
    if (!selectedSchedule) return;
    setActivateError(null);
    try {
      setIsActivating(true);
      await sciparserApi.activateSchedule(selectedSchedule.schedule_id);
      // Refresh the schedule list and update the selected schedule
      const updated = await sciparserApi.getSchedules();
      setSchedules(updated);
      const refreshed = updated.find((s: Schedule) => s.schedule_id === selectedSchedule.schedule_id);
      if (refreshed) setSelectedSchedule(refreshed);
    } catch (err: any) {
      console.error("Failed to activate schedule:", err);
      let msg = err?.message || "Failed to activate schedule.";
      try { const p = JSON.parse(msg); msg = p?.detail || p?.message || msg; } catch {}
      setActivateError(msg);
    } finally {
      setIsActivating(false);
    }
  };

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopySuccess("Code copied!");
    setTimeout(() => setCopySuccess(null), 2000);
  };

  const [copiedRunField, setCopiedRunField] = React.useState<string | null>(null);

  const handleCopyRunField = (field: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedRunField(field);
    setTimeout(() => setCopiedRunField(null), 2000);
  };

  const handleDownloadRunLog = (run: ScheduleRun) => {
    const contents = [
      `Run ID: ${run.run_id}`,
      `Status: ${run.status}`,
      `Engine: ${run.engine || '—'}`,
      `Duration: ${run.duration_seconds != null ? `${run.duration_seconds}s` : '—'}`,
      `Date: ${formatDate(run.created_at)}`,
      '',
      '=== Output (stdout) ===',
      run.output && run.output.trim().length > 0 ? run.output : 'No output recorded for this run.',
      '',
      '=== Error (stderr) ===',
      run.error_log && run.error_log.trim().length > 0 ? run.error_log : 'No errors recorded for this run.',
      '',
    ].join('\n');
    const blob = new Blob([contents], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `run-${run.run_id}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="flex flex-col h-full w-full bg-background overflow-hidden text-foreground">
      {/* Header */}
      <div className="min-h-14 border-b border-border bg-card/50 px-4 sm:px-8 flex flex-wrap items-center justify-between gap-2 py-3 sm:py-0 sm:h-20 shrink-0 backdrop-blur-xl z-10">
        <div className="flex items-center gap-3 sm:gap-6">
          <Button variant="ghost" size="icon" onClick={onBack} className="rounded-2xl hover:bg-foreground/5 text-muted-foreground hover:text-foreground transition-all shrink-0">
            <ChevronLeft className="w-5 h-5 sm:w-6 sm:h-6" />
          </Button>
          <div className="hidden sm:block h-10 w-px bg-border" />
          <div>
            <h1 className="text-base sm:text-xl font-black tracking-tight text-foreground uppercase">Automation Monitoring</h1>
            <p className="hidden sm:block text-[10px] text-muted-foreground uppercase tracking-[0.2em] font-bold">Real-time AI orchestration dashboard</p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">System Online</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchSchedules} className="h-9 sm:h-11 px-3 sm:px-6 rounded-xl border-border bg-transparent text-muted-foreground text-[11px] font-black uppercase tracking-[0.15em] hover:bg-foreground/5 gap-2">
            <RefreshCw className="w-4 h-4" />
            <span className="hidden sm:inline">REFRESH</span>
          </Button>
        </div>
      </div>

      <div ref={sidebarContainerRef} className="flex-1 flex overflow-hidden min-h-0">
        {/* Sidebar - Schedule List (hidden on mobile) */}
        <div
          className="hidden md:flex border-r border-border bg-background flex-col shrink-0 relative"
          style={{ width: sidebarWidth }}
        >
          <div className="p-6 border-b border-border flex items-center justify-between">
            <div className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em]">Your Schedules</div>
            <div className="px-2 py-1 rounded-md bg-card border border-border text-[9px] text-muted-foreground font-bold">{schedules.length}</div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 hide-scrollbar">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-40 gap-4">
                <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Syncing...</span>
              </div>
            ) : schedules.length === 0 ? (
              <div className="p-10 text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-card border border-border flex items-center justify-center mx-auto">
                  <Calendar className="w-6 h-6 text-muted-foreground/60" />
                </div>
                <p className="text-[11px] text-muted-foreground font-bold uppercase leading-relaxed">No schedules found.<br/>Create one from the chat!</p>
              </div>
            ) : (
              schedules.map((s) => (
                <div
                  key={s.schedule_id}
                  onClick={() => setSelectedSchedule(s)}
                  className={cn(
                    "group relative overflow-hidden rounded-[20px] border p-4 transition-all duration-300 cursor-pointer",
                    selectedSchedule?.schedule_id === s.schedule_id
                      ? "border-indigo-500/40 bg-indigo-500/10 text-foreground shadow-[0_0_30px_rgba(99,102,241,0.1)]"
                      : "border-border bg-card/40 text-muted-foreground hover:border-border hover:bg-card"
                  )}
                >
                  {selectedSchedule?.schedule_id === s.schedule_id && (
                    <motion.div layoutId="activeIndicator" className="absolute left-0 top-0 h-full w-1 bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.8)]" />
                  )}
                  <div className="font-black text-xs truncate mb-2 uppercase tracking-wider">{s.title}</div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest",
                        selectedSchedule?.schedule_id === s.schedule_id ? "bg-indigo-500 text-foreground" : "bg-border text-muted-foreground"
                      )}>
                        {s.schedule_type}
                      </span>
                      {s.status === 'draft' && (
                        <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest bg-amber-500/20 text-amber-400 border border-amber-500/30">
                          Draft
                        </span>
                      )}
                    </div>
                    <span className="text-[9px] text-muted-foreground/60 font-black uppercase">{formatDate(s.created_at).split(',')[0]}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Drag handle on the right edge of the sidebar */}
          <div
            onMouseDown={(e) => { e.preventDefault(); setIsResizingSidebar(true); }}
            className="absolute top-0 right-0 w-1.5 h-full cursor-col-resize z-20 group flex items-center justify-center hover:bg-indigo-500/20 transition-colors"
          >
            <div className="w-0.5 h-16 rounded-full bg-border group-hover:bg-indigo-500 transition-colors" />
          </div>
        </div>

        {/* Main Content - Premium Dashboard */}
        <div className="flex-1 overflow-y-auto bg-background p-4 sm:p-6 hide-scrollbar min-w-0">

          {/* Mobile schedule switcher — visible only below md breakpoint */}
          {schedules.length > 0 && (
            <div className="flex md:hidden gap-2 pb-4 scroll-x-smooth -mx-4 px-4">
              {schedules.map((s) => (
                <button
                  key={s.schedule_id}
                  onClick={() => setSelectedSchedule(s)}
                  className={cn(
                    "shrink-0 px-3 py-2 rounded-xl border text-[11px] font-black uppercase tracking-wider transition-all",
                    selectedSchedule?.schedule_id === s.schedule_id
                      ? "border-indigo-500/60 bg-indigo-500/15 text-foreground"
                      : "border-border bg-card/60 text-muted-foreground hover:border-border hover:text-muted-foreground"
                  )}
                >
                  {s.title.length > 18 ? s.title.slice(0, 18) + "…" : s.title}
                </button>
              ))}
            </div>
          )}

          {selectedSchedule ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              {/* Header Section */}
              <div className="flex flex-wrap items-start gap-6 bg-card/40 p-6 rounded-[32px] border border-border relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                  <Activity className="w-40 h-40 text-indigo-500" />
                </div>
                <div className="relative z-10 space-y-6 flex-1">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-[20px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                      <Zap className="w-7 h-7 text-indigo-500" />
                    </div>
                    <div>
                      <h2 className="text-lg sm:text-2xl font-black tracking-tight text-foreground uppercase break-words">{selectedSchedule.title}</h2>
                      <div className="flex flex-wrap items-center gap-3 sm:gap-6 mt-2">
                        <div className="flex items-center gap-2 text-[11px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Mail className="w-3.5 h-3.5 text-indigo-500" />
                          <span>{selectedSchedule.email_recipient}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] font-bold text-muted-foreground uppercase tracking-widest">
                          <Clock className="w-3.5 h-3.5 text-indigo-500" />
                          <span className="capitalize">{selectedSchedule.schedule_type}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] font-bold text-muted-foreground uppercase tracking-widest">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            selectedSchedule.status === 'active' ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" :
                            selectedSchedule.status === 'draft' ? "bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.5)]" :
                            "bg-slate-500"
                          )} />
                          <span className={cn(
                            "capitalize",
                            selectedSchedule.status === 'draft' ? "text-amber-400" : ""
                          )}>{selectedSchedule.status}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
                    {[
                      { label: 'Next Run', val: selectedSchedule.next_run ? formatDate(selectedSchedule.next_run) : (selectedSchedule.schedule_type === 'manual' ? 'Manual only' : '—'), icon: Calendar },
                      { label: 'Last Run', val: selectedSchedule.last_run ? formatDate(selectedSchedule.last_run) : 'Never', icon: History },
                      { label: 'Frequency', val: (selectedSchedule.schedule_type || 'manual') + (selectedSchedule.schedule_time ? ` @ ${selectedSchedule.schedule_time}` : ''), icon: Cpu },
                      { label: 'Email', val: selectedSchedule.email_recipient ? 'Configured' : 'Not set', icon: Mail }
                    ].map((item, i) => (
                      <div key={i} className="space-y-1.5">
                        <div className="flex items-center gap-2 text-[9px] font-black text-muted-foreground uppercase tracking-[0.2em]">
                          <item.icon className="w-3 h-3" />
                          {item.label}
                        </div>
                        <div className="text-xs font-black text-muted-foreground uppercase tracking-wider">{item.val}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="relative z-10 flex flex-col gap-3">
                  {selectedSchedule.status === 'draft' ? (
                    <>
                      <Button
                        onClick={handleActivate}
                        disabled={isActivating}
                        className="h-14 px-10 rounded-2xl bg-amber-500 hover:bg-amber-600 text-foreground text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-amber-500/20 transition-all active:scale-95 disabled:opacity-50 min-w-[200px] flex items-center justify-center gap-3"
                      >
                        {isActivating ? (
                          <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                          <Zap className="w-5 h-5" />
                        )}
                        {isActivating ? "ACTIVATING..." : "ACTIVATE"}
                      </Button>
                      {activateError && (
                        <div className="flex items-start gap-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 max-w-[220px]">
                          <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                          <p className="text-[10px] font-bold text-red-400 leading-relaxed">{activateError}</p>
                        </div>
                      )}
                    </>
                  ) : (
                  <Button 
                    onClick={handleRunNow}
                    disabled={isRunning}
                    className="h-14 px-10 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-foreground text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 min-w-[200px] flex items-center justify-center gap-3"
                  >
                    {isRunning ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Play className="w-5 h-5 fill-current" />
                    )}
                    {isRunning ? "RUNNING..." : "RUN NOW"}
                  </Button>
                  )}
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => setIsEditing(true)}
                      className="flex-1 h-12 rounded-xl border-border bg-card/60 text-muted-foreground hover:bg-foreground/5 transition-all"
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={() => setDeleteConfirmId(selectedSchedule.schedule_id)}
                      className="flex-1 h-12 rounded-xl border-red-500/20 bg-red-500/5 text-red-500 hover:bg-red-500/10 transition-all"
                    >
                      <Trash className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Main Dashboard Grid */}
              <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">

                {/* Left Column - Progress, Pipeline & Live Logs */}
                <div className="col-span-1 xl:col-span-8 space-y-6 min-w-0">

                  {/* Current Run Progress */}
                  <div className="bg-card/40 rounded-[32px] border border-border p-4 sm:p-6 flex flex-col sm:flex-row items-center gap-6 sm:gap-8">
                    <div className="relative w-24 h-24 shrink-0">
                      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                        <circle className="text-border" strokeWidth="8" stroke="currentColor" fill="transparent" r="42" cx="50" cy="50" />
                        <motion.circle 
                          className="text-indigo-500" 
                          strokeWidth="8" 
                          strokeDasharray={264}
                          initial={{ strokeDashoffset: 264 }}
                          animate={{ strokeDashoffset: 264 - (264 * currentProgress) / 100 }}
                          strokeLinecap="round" 
                          stroke="currentColor" 
                          fill="transparent" 
                          r="42" cx="50" cy="50" 
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-lg font-black text-foreground">{currentProgress}%</span>
                        <span className="text-[7px] font-black text-muted-foreground uppercase tracking-widest">Progress</span>
                      </div>
                    </div>
                    
                    <div className="flex-1 space-y-3 w-full">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <div className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">Current Status</div>
                          <div className="text-base font-black text-foreground uppercase tracking-tight">
                            {isRunning ? "Running Automation..." : "Idle"}
                          </div>
                        </div>
                        <div className="text-right space-y-1">
                          <div className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em]">ETA</div>
                          <div className="text-base font-black text-foreground uppercase tracking-tight">
                            {isRunning ? `${Math.max(0, Math.round(((100 - currentProgress) / 100) * 30))}s` : "--"}
                          </div>
                        </div>
                      </div>
                      <div className="h-2 w-full bg-border rounded-full overflow-hidden">
                        <motion.div 
                          className="h-full bg-gradient-to-r from-indigo-600 to-purple-600"
                          initial={{ width: 0 }}
                          animate={{ width: `${currentProgress}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Execution Pipeline */}
                  <div className="bg-card/40 rounded-[32px] border border-border p-4 sm:p-6 space-y-4 sm:space-y-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Workflow className="w-5 h-5 text-indigo-500" />
                        <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Execution Pipeline</h3>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={cn("w-2 h-2 rounded-full bg-indigo-500", isRunning && "animate-pulse")} />
                        <span className="text-[9px] font-black text-indigo-500 uppercase tracking-widest">{isRunning ? "Live Tracking" : "Idle"}</span>
                      </div>
                    </div>

                    <div className="overflow-x-auto scroll-x-smooth -mx-4 px-4">
                      <div className="relative flex items-center justify-between px-2 min-w-[420px]">
                      {/* Connector Line */}
                      <div className="absolute top-5 left-8 right-8 h-0.5 bg-border z-0" />
                      
                      {pipelineSteps.map((step) => (
                        <div key={step.id} className="relative z-10 flex flex-col items-center gap-2 group">
                          <div className={cn(
                            "w-10 h-10 rounded-xl border flex items-center justify-center transition-all duration-500 shadow-xl",
                            step.status === 'completed' ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-500" :
                            step.status === 'running' ? "bg-indigo-500/10 border-indigo-500 text-indigo-500 animate-pulse" :
                            "bg-background border-border text-muted-foreground/60"
                          )}>
                            {step.status === 'completed' ? <Check className="w-5 h-5" /> : 
                             step.status === 'running' ? <RefreshCw className="w-4 h-4 animate-spin-slow" /> :
                             <span className="text-xs font-black">{step.id}</span>}
                          </div>
                          <div className="text-center space-y-0.5 max-w-[70px]">
                            <div className={cn(
                              "text-[9px] font-black uppercase tracking-widest leading-tight transition-colors",
                              step.status === 'pending' ? "text-muted-foreground/60" : "text-foreground"
                            )}>{step.name}</div>
                            {step.status === 'completed' && (
                              <div className="text-[8px] font-black text-emerald-500 uppercase tracking-widest">{step.duration}</div>
                            )}
                          </div>
                        </div>
                      ))}
                      </div>
                    </div>
                  </div>

                  {/* Live Logs Panel */}
                  <div className="bg-card/40 rounded-[32px] border border-border overflow-hidden flex flex-col">
                    <div className="px-4 sm:px-6 py-4 border-b border-border shrink-0 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-indigo-500" />
                        <h3 className="text-[11px] font-black text-foreground uppercase tracking-[0.2em]">Live Logs</h3>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline" size="sm"
                          onClick={() => setActiveModal('aiplan')}
                          className="h-8 px-3 rounded-lg border-border bg-transparent text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-foreground/5 gap-1.5"
                        >
                          <Brain className="w-3.5 h-3.5" /> AI Plan
                        </Button>
                        <Button
                          variant="outline" size="sm"
                          onClick={() => setActiveModal('script')}
                          className="h-8 px-3 rounded-lg border-border bg-transparent text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-foreground/5 gap-1.5"
                        >
                          <Code className="w-3.5 h-3.5" /> Script
                        </Button>
                        <Button
                          variant="outline" size="sm"
                          onClick={() => setActiveModal('history')}
                          className="h-8 px-3 rounded-lg border-border bg-transparent text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-foreground/5 gap-1.5"
                        >
                          <History className="w-3.5 h-3.5" /> History
                        </Button>
                      </div>
                    </div>

                    <div className="h-64 sm:h-80 p-4 sm:p-6 overflow-y-auto hide-scrollbar space-y-2 font-mono">
                      {liveLogs.length > 0 ? (
                        liveLogs.map((log, i) => (
                          <div key={i} className="flex items-start gap-4 text-[11px] py-1 group hover:bg-foreground/5 rounded px-2 transition-colors">
                            <span className="text-muted-foreground/60 shrink-0">{log.time}</span>
                            <span className={cn("font-black shrink-0 w-20", log.type === 'error' ? 'text-red-400' : 'text-indigo-400')}>[{log.engine || 'SYS'}]</span>
                            <span className="text-muted-foreground">{log.message}</span>
                          </div>
                        ))
                      ) : (
                        <div className="py-16 text-center">
                          <Terminal className="w-8 h-8 text-border mx-auto mb-3" />
                          <p className="text-[10px] font-black text-muted-foreground/60 uppercase tracking-widest">Waiting for execution logs...</p>
                        </div>
                      )}
                      {isRunning && (
                        <div className="flex items-center gap-2 text-[11px] py-1 px-2">
                          <Loader2 className="w-3 h-3 animate-spin text-indigo-500" />
                          <span className="text-indigo-500 animate-pulse">Processing next instruction...</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Column - Summary & Browser */}
                <div className="col-span-1 xl:col-span-4 space-y-6 min-w-0">

                  {/* Execution Summary - compact strip, backed by real run data */}
                  <div className="bg-card/40 rounded-[32px] border border-border p-4 sm:p-5">
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        {
                          label: 'Elapsed',
                          val: isRunning || elapsedSeconds > 0
                            ? `${Math.floor(elapsedSeconds / 60)}:${String(elapsedSeconds % 60).padStart(2, '0')}`
                            : '--',
                          icon: Timer, color: 'text-indigo-500'
                        },
                        {
                          label: 'Progress',
                          val: isRunning || currentProgress > 0 ? `${currentProgress}%` : '--',
                          icon: Activity, color: 'text-emerald-500'
                        },
                        {
                          label: 'CPU',
                          val: resourceUsage ? `${resourceUsage.cpu_percent}%` : isRunning ? '...' : '--',
                          icon: Gauge, color: 'text-orange-500'
                        },
                        {
                          label: 'Memory',
                          val: resourceUsage ? `${resourceUsage.memory_mb.toFixed(0)} MB` : isRunning ? '...' : '--',
                          icon: HardDrive, color: 'text-pink-500'
                        },
                        {
                          label: 'Log Lines',
                          val: String(liveLogs.length),
                          icon: Network, color: 'text-blue-500'
                        },
                        {
                          label: 'Browser',
                          val: liveScreenshot ? 'Streaming' : isRunning ? 'Connecting' : 'Idle',
                          icon: Globe, color: 'text-purple-500'
                        }
                      ].map((item, i) => (
                        <div key={i} className="flex items-center gap-2 p-2.5 rounded-xl bg-background border border-border min-w-0">
                          <item.icon className={cn("w-3.5 h-3.5 shrink-0", item.color)} />
                          <div className="min-w-0">
                            <div className="text-[8px] font-bold text-muted-foreground uppercase tracking-widest truncate">{item.label}</div>
                            <div className="text-[10px] font-black text-foreground uppercase truncate">{item.val}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Live Browser Preview */}
                  <div className="bg-card/40 rounded-[32px] border border-border overflow-hidden flex flex-col">
                    <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-white/[0.02]">
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-indigo-500" />
                        <span className="text-[10px] font-black text-foreground uppercase tracking-widest">Live Browser</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setActiveModal('browser')}
                          className="p-1.5 rounded-lg hover:bg-foreground/5 text-muted-foreground hover:text-foreground transition-all"
                        >
                          <Maximize2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="aspect-video bg-black relative group cursor-pointer" onClick={() => setActiveModal('browser')}>
                      {liveScreenshot ? (
                        <img 
                          src={liveScreenshot.startsWith('data:') ? liveScreenshot : `data:image/jpeg;base64,${liveScreenshot}`} 
                          alt="Live Browser" 
                          className="w-full h-full object-contain"
                        />
                      ) : (
                        <>
                          <img 
                            src="https://images.unsplash.com/photo-1614064641938-3bbee52942c7?q=80&w=1000&auto=format&fit=crop" 
                            alt="Browser Preview" 
                            className="w-full h-full object-cover opacity-40 grayscale"
                          />
                          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                            <div className="w-12 h-12 rounded-full border-2 border-indigo-500/30 border-t-indigo-500 animate-spin" />
                            <span className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] animate-pulse">
                              {isRunning ? "Streaming CDP..." : "Waiting for execution..."}
                            </span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Final Result Card */}
                  <div className="bg-gradient-to-br from-indigo-600/20 to-purple-600/20 rounded-[32px] border border-indigo-500/30 p-6 space-y-4 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-6 opacity-10">
                      <Shield className="w-20 h-20 text-foreground" />
                    </div>
                    <div className="relative z-10 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                          <h3 className="text-xs font-black text-foreground uppercase tracking-[0.2em]">Final Result</h3>
                        </div>
                        {selectedSchedule.email_recipient && selectedSchedule.extracted_content && (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                            <Mail className="w-3 h-3 text-emerald-400" />
                            <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Email Sent</span>
                          </div>
                        )}
                      </div>
                      <div className="p-4 rounded-2xl bg-background/60 border border-white/5 backdrop-blur-sm max-h-28 overflow-y-auto hide-scrollbar">
                        <p className="text-xs text-muted-foreground leading-relaxed font-medium whitespace-pre-wrap">
                          {selectedSchedule.extracted_content || "No results available yet. Run the schedule to see data."}
                        </p>
                      </div>
                      {selectedSchedule.extracted_content && (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            onClick={() => setActiveModal('result')}
                            className="flex-1 h-11 rounded-xl border-white/20 bg-transparent text-foreground text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-all gap-2"
                          >
                            <Maximize2 className="w-3.5 h-3.5" />
                            View Full
                          </Button>
                          <Button
                            onClick={() => {
                              const blob = new Blob([selectedSchedule.extracted_content], { type: 'text/plain' });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = `report-${selectedSchedule.schedule_id}.txt`;
                              a.click();
                            }}
                            className="flex-1 h-11 rounded-xl bg-white text-indigo-600 text-[10px] font-black uppercase tracking-widest hover:bg-background transition-all gap-2"
                          >
                            <Download className="w-4 h-4" />
                            Download
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              </div>
            </motion.div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
              <div className="relative">
                <div className="absolute -inset-4 bg-indigo-500/20 rounded-full blur-2xl animate-pulse" />
                <div className="relative w-24 h-24 rounded-[32px] bg-card border border-border flex items-center justify-center text-indigo-500 shadow-2xl">
                  <Activity className="w-12 h-12" />
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-black text-foreground uppercase tracking-tight">Select an Automation</h3>
                <p className="text-sm text-muted-foreground max-w-xs mx-auto font-bold uppercase tracking-widest leading-relaxed">
                  Choose a task from the sidebar to monitor its real-time execution and results.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Script Modal */}
      <AnimatePresence>
        {activeModal === 'script' && selectedSchedule && (
          <ModalShell
            title="Automation Script"
            icon={Code}
            onClose={() => setActiveModal(null)}
            maxWidth="max-w-4xl"
            headerAction={
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => handleCopyCode(selectedSchedule.generated_script)}
                className="h-9 px-4 rounded-xl border-border bg-white/5 text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-white/10 gap-2"
              >
                {copySuccess ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                {copySuccess || "COPY CODE"}
              </Button>
            }
          >
            <div className="rounded-2xl border border-border bg-background overflow-hidden">
              <div className="px-4 py-2 border-b border-border bg-white/[0.02] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-red-500/50" />
                  <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                  <div className="w-2 h-2 rounded-full bg-green-500/50" />
                </div>
                <span className="text-[9px] font-black text-muted-foreground/60 uppercase tracking-widest">automation_script.py</span>
              </div>
              <pre className="p-6 text-[12px] font-mono text-muted-foreground overflow-x-auto leading-relaxed hide-scrollbar">
                <code>{selectedSchedule.generated_script || "# No script generated yet."}</code>
              </pre>
            </div>
          </ModalShell>
        )}
      </AnimatePresence>

      {/* AI Planning Modal */}
      <AnimatePresence>
        {activeModal === 'aiplan' && selectedSchedule && (
          <ModalShell title="AI Planning" icon={Brain} onClose={() => setActiveModal(null)}>
            <div className="space-y-6">
              {selectedSchedule.user_prompt && (
                <div className="p-5 rounded-2xl bg-background border border-indigo-500/20 space-y-3">
                  <div className="flex items-center gap-2.5">
                    <UserIcon className="w-4 h-4 text-indigo-400" />
                    <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">User Goal</h4>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{selectedSchedule.user_prompt}</p>
                </div>
              )}

              <div className="p-6 rounded-2xl bg-background border border-border space-y-4">
                <div className="flex items-center gap-2.5">
                  <Target className="w-4 h-4 text-purple-500" />
                  <h4 className="text-[11px] font-black text-foreground uppercase tracking-widest">Execution Strategy</h4>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {selectedSchedule.assistant_response || "No strategy recorded for this schedule."}
                </p>
              </div>

              <div className="space-y-3">
                <div className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Original Agent Plan</div>
                {selectedSchedule.plan_data ? (() => {
                  try {
                    const tasks = JSON.parse(selectedSchedule.plan_data) as any[];
                    return tasks.map((task: any, i: number) => (
                      <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-background border border-border">
                        <div className="w-5 h-5 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[9px] font-black text-indigo-500">{i + 1}</div>
                        <span className="text-xs text-muted-foreground font-medium">{task.title || String(task)}</span>
                      </div>
                    ));
                  } catch {
                    return <p className="text-xs text-muted-foreground ml-1 leading-relaxed">{selectedSchedule.plan_data}</p>;
                  }
                })() : (
                  <p className="text-[10px] text-muted-foreground/60 italic ml-1">No plan data stored for this schedule.</p>
                )}
              </div>
            </div>
          </ModalShell>
        )}
      </AnimatePresence>

      {/* History Modal */}
      <AnimatePresence>
        {activeModal === 'history' && selectedSchedule && (
          <ModalShell title="Run History" icon={History} onClose={() => setActiveModal(null)} maxWidth="max-w-3xl">
            {runs.length > 0 ? (
              <div className="overflow-x-auto scroll-x-smooth">
                <table className="w-full text-left text-[11px] min-w-[480px]">
                  <thead>
                    <tr className="text-muted-foreground font-black uppercase tracking-widest border-b border-border">
                      <th className="pb-4 px-2">Run ID</th>
                      <th className="pb-4 px-2">Date</th>
                      <th className="pb-4 px-2">Status</th>
                      <th className="pb-4 px-2">Engine</th>
                      <th className="pb-4 px-2">Duration</th>
                      <th className="pb-4 px-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {runs.map((run) => (
                      <tr key={run.run_id} className="group hover:bg-foreground/5 transition-colors">
                        <td className="py-4 px-2 font-mono text-indigo-400 truncate max-w-[100px]">{run.run_id}</td>
                        <td className="py-4 px-2 text-muted-foreground whitespace-nowrap">{formatDate(run.created_at).split(',')[0]}</td>
                        <td className="py-4 px-2">
                          <span className={cn(
                            "px-2 py-0.5 rounded-md text-[9px] font-black uppercase whitespace-nowrap",
                            run.status === 'completed' ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                          )}>{run.status}</span>
                        </td>
                        <td className="py-4 px-2 text-muted-foreground font-bold">{run.engine}</td>
                        <td className="py-4 px-2 text-muted-foreground font-bold">{run.duration_seconds}s</td>
                        <td className="py-4 px-2 text-right">
                          <button
                            onClick={() => { setSelectedRun(run); setActiveModal('runDetail'); }}
                            className="p-2 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all"
                            title="View run details"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-16 text-center">
                <History className="w-8 h-8 text-border mx-auto mb-3" />
                <p className="text-[10px] font-black text-muted-foreground/60 uppercase tracking-widest">No runs recorded yet.</p>
              </div>
            )}
          </ModalShell>
        )}
      </AnimatePresence>

      {/* Run Detail Modal */}
      <AnimatePresence>
        {activeModal === 'runDetail' && selectedRun && (
          <ModalShell
            title={`Run Details — ${selectedRun.run_id}`}
            icon={ExternalLink}
            onClose={() => { setActiveModal('history'); setSelectedRun(null); }}
            maxWidth="max-w-3xl"
            headerAction={
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownloadRunLog(selectedRun)}
                className="h-9 px-4 rounded-xl border-border bg-white/5 text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-white/10 gap-2"
              >
                <Download className="w-3.5 h-3.5" />
                Download Log
              </Button>
            }
          >
            <div className="space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-foreground/5 rounded-xl p-3">
                  <p className="text-[9px] font-black text-muted-foreground uppercase tracking-widest mb-1">Status</p>
                  <span className={cn(
                    "px-2 py-0.5 rounded-md text-[9px] font-black uppercase whitespace-nowrap",
                    selectedRun.status === 'completed' ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                  )}>{selectedRun.status}</span>
                </div>
                <div className="bg-foreground/5 rounded-xl p-3">
                  <p className="text-[9px] font-black text-muted-foreground uppercase tracking-widest mb-1">Engine</p>
                  <p className="text-xs font-bold text-foreground">{selectedRun.engine || '—'}</p>
                </div>
                <div className="bg-foreground/5 rounded-xl p-3">
                  <p className="text-[9px] font-black text-muted-foreground uppercase tracking-widest mb-1">Duration</p>
                  <p className="text-xs font-bold text-foreground">{selectedRun.duration_seconds != null ? `${selectedRun.duration_seconds}s` : '—'}</p>
                </div>
                <div className="bg-foreground/5 rounded-xl p-3">
                  <p className="text-[9px] font-black text-muted-foreground uppercase tracking-widest mb-1">Date</p>
                  <p className="text-xs font-bold text-foreground">{formatDate(selectedRun.created_at)}</p>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Output (stdout)</p>
                  <button
                    onClick={() => handleCopyRunField('output', selectedRun.output && selectedRun.output.trim().length > 0 ? selectedRun.output : 'No output recorded for this run.')}
                    className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-lg hover:bg-white/10"
                  >
                    {copiedRunField === 'output' ? <CheckCircle2 className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    {copiedRunField === 'output' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <pre className="bg-black/90 text-emerald-400 rounded-xl p-4 text-[11px] font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto border border-border">
                  {selectedRun.output && selectedRun.output.trim().length > 0 ? selectedRun.output : 'No output recorded for this run.'}
                </pre>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Error (stderr)</p>
                  <button
                    onClick={() => handleCopyRunField('error', selectedRun.error_log && selectedRun.error_log.trim().length > 0 ? selectedRun.error_log : 'No errors recorded for this run.')}
                    className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-lg hover:bg-white/10"
                  >
                    {copiedRunField === 'error' ? <CheckCircle2 className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    {copiedRunField === 'error' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <pre className={cn(
                  "rounded-xl p-4 text-[11px] font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto border border-border",
                  selectedRun.error_log && selectedRun.error_log.trim().length > 0 ? "bg-black/90 text-red-400" : "bg-black/90 text-muted-foreground"
                )}>
                  {selectedRun.error_log && selectedRun.error_log.trim().length > 0 ? selectedRun.error_log : 'No errors recorded for this run.'}
                </pre>
              </div>
            </div>
          </ModalShell>
        )}
      </AnimatePresence>

      {/* Live Browser Expanded Modal */}
      <AnimatePresence>
        {activeModal === 'browser' && selectedSchedule && (
          <ModalShell title="Live Browser" icon={Globe} onClose={() => setActiveModal(null)} maxWidth="max-w-4xl">
            <div className="aspect-video bg-black relative rounded-2xl overflow-hidden border border-border">
              {liveScreenshot ? (
                <img 
                  src={liveScreenshot.startsWith('data:') ? liveScreenshot : `data:image/jpeg;base64,${liveScreenshot}`} 
                  alt="Live Browser" 
                  className="w-full h-full object-contain"
                />
              ) : (
                <>
                  <img 
                    src="https://images.unsplash.com/photo-1614064641938-3bbee52942c7?q=80&w=1000&auto=format&fit=crop" 
                    alt="Browser Preview" 
                    className="w-full h-full object-cover opacity-40 grayscale"
                  />
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                    <div className="w-12 h-12 rounded-full border-2 border-indigo-500/30 border-t-indigo-500 animate-spin" />
                    <span className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] animate-pulse">
                      {isRunning ? "Streaming CDP..." : "Waiting for execution..."}
                    </span>
                  </div>
                </>
              )}
              <div className="absolute bottom-4 left-4 right-4 p-3 rounded-xl bg-background/80 backdrop-blur-md border border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-[9px] font-black text-muted-foreground uppercase truncate max-w-[220px]">
                    {liveLogs.filter(l => l.message.includes('https://')).pop()?.message.match(/https?:\/\/[^\s]+/)?.[0] || "https://browser.live"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button className="p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground"><RefreshCw className="w-3 h-3" /></button>
                  <button className="p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground"><ZoomIn className="w-3 h-3" /></button>
                </div>
              </div>
            </div>
          </ModalShell>
        )}
      </AnimatePresence>

      {/* Final Result Modal */}
      <AnimatePresence>
        {activeModal === 'result' && selectedSchedule && (
          <ModalShell
            title="Final Result"
            icon={CheckCircle2}
            onClose={() => setActiveModal(null)}
            maxWidth="max-w-2xl"
            headerAction={
              selectedSchedule.extracted_content ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const blob = new Blob([selectedSchedule.extracted_content], { type: 'text/plain' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `report-${selectedSchedule.schedule_id}.txt`;
                    a.click();
                  }}
                  className="h-9 px-4 rounded-xl border-border bg-white/5 text-muted-foreground text-[10px] font-black uppercase tracking-widest hover:bg-white/10 gap-2"
                >
                  <Download className="w-3.5 h-3.5" />
                  DOWNLOAD
                </Button>
              ) : undefined
            }
          >
            <div className="p-5 rounded-2xl bg-background border border-border">
              <p className="text-sm text-muted-foreground leading-relaxed font-medium whitespace-pre-wrap">
                {selectedSchedule.extracted_content || "No results available yet. Run the schedule to see data."}
              </p>
            </div>
          </ModalShell>
        )}
      </AnimatePresence>

      {/* Modals (Edit/Delete) - Reusing existing logic but with premium styling */}
      <AnimatePresence>
        {isEditing && (
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-background/80 backdrop-blur-xl p-4">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md bg-card rounded-[32px] shadow-2xl border border-border p-8 space-y-8"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-black text-xl text-foreground uppercase tracking-tight">Edit Schedule</h3>
                <button onClick={() => setIsEditing(false)} className="text-muted-foreground hover:text-foreground"><X className="w-6 h-6" /></button>
              </div>
              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Task Title</label>
                  <input 
                    value={editData.title} 
                    onChange={e => setEditData({...editData, title: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-background border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Frequency</label>
                  <select 
                    value={editData.type} 
                    onChange={e => setEditData({...editData, type: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-background border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest ml-1">Delivery Email</label>
                  <input 
                    value={editData.email} 
                    onChange={e => setEditData({...editData, email: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-background border border-border text-sm font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                </div>
              </div>
              <div className="flex gap-4 pt-4">
                <Button variant="ghost" onClick={() => setIsEditing(false)} className="flex-1 h-14 rounded-2xl text-[11px] font-black uppercase tracking-widest">CANCEL</Button>
                <Button onClick={handleUpdate} className="flex-1 h-14 rounded-2xl bg-indigo-600 text-foreground text-[11px] font-black uppercase tracking-widest shadow-xl shadow-indigo-500/20">SAVE CHANGES</Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirmId && (
          <div className="fixed inset-0 z-[120] flex items-center justify-center bg-background/80 backdrop-blur-xl p-4">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-sm bg-card rounded-[32px] shadow-2xl border border-border p-8 text-center space-y-6"
            >
              <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto">
                <AlertCircle className="w-8 h-8 text-red-500" />
              </div>
              <div className="space-y-2">
                <h3 className="font-black text-xl text-foreground uppercase tracking-tight">Confirm Deletion</h3>
                <p className="text-sm text-muted-foreground font-bold uppercase tracking-widest leading-relaxed">
                  Are you sure you want to delete this schedule? This action cannot be undone.
                </p>
              </div>
              <div className="flex gap-4 pt-2">
                <Button 
                  variant="ghost" 
                  onClick={() => setDeleteConfirmId(null)} 
                  className="flex-1 h-14 rounded-2xl text-[11px] font-black uppercase tracking-widest"
                >
                  CANCEL
                </Button>
                <Button 
                  onClick={handleDelete} 
                  className="flex-1 h-14 bg-red-500 hover:bg-red-600 text-foreground text-[11px] font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-red-500/20"
                >
                  DELETE
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
