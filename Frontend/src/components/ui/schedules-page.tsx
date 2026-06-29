import * as React from "react";
import { Button } from "./button";
import { sciparserApi } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { 
  Calendar, Clock, Code, Play, Pencil, Trash, 
  ChevronLeft, Mail, CheckCircle2, AlertCircle,
  ExternalLink, Copy, Download, RefreshCw, Pause,
  ChevronRight, Activity, Cpu, Database, Globe,
  Layout, Layers, Zap, Shield, Info, Search,
  Terminal, Workflow, Target, MessageSquare,
  ArrowRight, Loader2, Sparkles, User as UserIcon,
  Check, X, MoreVertical, Maximize2, ZoomIn,
  History, Timer, Gauge, Network,
  Brain
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Schedule {
  schedule_id: string;
  title: string;
  schedule_type: string;
  email_recipient: string;
  status: string;
  generated_script: string;
  extracted_content: string;
  assistant_response?: string;
  plan_data?: string;
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
  error?: string;
}

interface SchedulesPageProps {
  onBack: () => void;
}

export const SchedulesPage: React.FC<SchedulesPageProps> = ({ onBack }) => {
  const { theme } = useTheme();
  const [schedules, setSchedules] = React.useState<Schedule[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedSchedule, setSelectedSchedule] = React.useState<Schedule | null>(null);
  const [copySuccess, setCopySuccess] = React.useState<string | null>(null);
  const [isRunning, setIsRunning] = React.useState(false);
  const [showScript, setShowScript] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [editData, setEditData] = React.useState({ title: "", type: "", email: "" });
  const [deleteConfirmId, setDeleteConfirmId] = React.useState<string | null>(null);
  const [activeTab, setActiveTab] = React.useState("pipeline");
  const [currentProgress, setCurrentProgress] = React.useState(0);
  const [liveLogs, setLiveLogs] = React.useState<any[]>([]);
  const [liveScreenshot, setLiveScreenshot] = React.useState<string | null>(null);
  const [pipelineSteps, setPipelineSteps] = React.useState([
    { id: 1, name: "Initialize", status: "pending", duration: "--", time: "--" },
    { id: 2, name: "Generate Plan", status: "pending", duration: "--", time: "--" },
    { id: 3, name: "Generate Script", status: "pending", duration: "--", time: "--" },
    { id: 4, name: "Execute Automation", status: "pending", duration: "--", time: "--" },
    { id: 5, name: "Extract Result", status: "pending", duration: "--", time: "--" },
    { id: 6, name: "Save Result", status: "pending", duration: "--", time: "--" }
  ]);
  
  const [runs, setRuns] = React.useState<ScheduleRun[]>([]);

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

  // WebSocket for real-time monitoring
  React.useEffect(() => {
    if (!selectedSchedule || !isRunning) return;

    const token = localStorage.getItem("access_token");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/sciparser/v1/ws/schedule/${selectedSchedule.schedule_id}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'log') {
          setLiveLogs(prev => [...prev, msg]);
        } else if (msg.type === 'pipeline_update') {
          setPipelineSteps(prev => prev.map(step => 
            step.id === msg.step_id ? { ...step, status: msg.status, time: msg.time || step.time } : step
          ));
          // Update progress based on step
          setCurrentProgress(Math.round((msg.step_id / 6) * 100));
        } else if (msg.type === 'screenshot') {
          setLiveScreenshot(msg.frame);
        }
      } catch (err) {
        console.error("Schedule WS error:", err);
      }
    };

    return () => ws.close();
  }, [selectedSchedule, isRunning]);

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
      setPipelineSteps(prev => prev.map(s => ({ ...s, status: 'pending', time: '--' })));
      
      await sciparserApi.runSchedule(selectedSchedule.schedule_id);
      
      setTimeout(fetchSchedules, 10000);
    } catch (err) {
      console.error("Failed to run schedule:", err);
    } finally {
      setTimeout(() => setIsRunning(false), 2000);
    }
  };

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopySuccess("Code copied!");
    setTimeout(() => setCopySuccess(null), 2000);
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
    <div className="flex flex-col h-full w-full bg-[#05070A] overflow-hidden text-[#F8FAFC]">
      {/* Header */}
      <div className="h-20 border-b border-[#1F2937] bg-[#111827]/50 px-8 flex items-center justify-between shrink-0 backdrop-blur-xl z-10">
        <div className="flex items-center gap-6">
          <Button variant="ghost" size="icon" onClick={onBack} className="rounded-2xl hover:bg-white/5 text-[#64748B] hover:text-white transition-all">
            <ChevronLeft className="w-6 h-6" />
          </Button>
          <div className="h-10 w-px bg-[#1F2937]" />
          <div>
            <h1 className="text-xl font-black tracking-tight text-white uppercase">Automation Monitoring</h1>
            <p className="text-[10px] text-[#64748B] uppercase tracking-[0.2em] font-bold">Real-time AI orchestration dashboard</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">System Online</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchSchedules} className="h-11 px-6 rounded-xl border-[#1F2937] bg-transparent text-[#CBD5E1] text-[11px] font-black uppercase tracking-[0.15em] hover:bg-white/5 gap-2">
            <RefreshCw className="w-4 h-4" />
            REFRESH
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Schedule List */}
        <div className="w-[320px] border-r border-[#1F2937] bg-[#05070A] flex flex-col shrink-0">
          <div className="p-6 border-b border-[#1F2937] flex items-center justify-between">
            <div className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em]">Your Schedules</div>
            <div className="px-2 py-1 rounded-md bg-[#111827] border border-[#1F2937] text-[9px] text-[#64748B] font-bold">{schedules.length}</div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 hide-scrollbar">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-40 gap-4">
                <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                <span className="text-[10px] font-black text-[#64748B] uppercase tracking-widest">Syncing...</span>
              </div>
            ) : schedules.length === 0 ? (
              <div className="p-10 text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[#111827] border border-[#1F2937] flex items-center justify-center mx-auto">
                  <Calendar className="w-6 h-6 text-[#374151]" />
                </div>
                <p className="text-[11px] text-[#64748B] font-bold uppercase leading-relaxed">No schedules found.<br/>Create one from the chat!</p>
              </div>
            ) : (
              schedules.map((s) => (
                <div
                  key={s.schedule_id}
                  onClick={() => setSelectedSchedule(s)}
                  className={cn(
                    "group relative overflow-hidden rounded-[20px] border p-4 transition-all duration-300 cursor-pointer",
                    selectedSchedule?.schedule_id === s.schedule_id
                      ? "border-indigo-500/40 bg-indigo-500/10 text-white shadow-[0_0_30px_rgba(99,102,241,0.1)]"
                      : "border-[#1F2937] bg-[#111827]/40 text-[#64748B] hover:border-[#374151] hover:bg-[#111827]"
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
                        selectedSchedule?.schedule_id === s.schedule_id ? "bg-indigo-500 text-white" : "bg-[#1F2937] text-[#64748B]"
                      )}>
                        {s.schedule_type}
                      </span>
                    </div>
                    <span className="text-[9px] text-[#374151] font-black uppercase">{formatDate(s.created_at).split(',')[0]}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Main Content - Premium Dashboard */}
        <div className="flex-1 overflow-y-auto bg-[#05070A] p-8 hide-scrollbar">
          {selectedSchedule ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-[1400px] mx-auto space-y-8"
            >
              {/* Header Section */}
              <div className="flex items-start justify-between bg-[#111827]/40 p-8 rounded-[32px] border border-[#1F2937] relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                  <Activity className="w-40 h-40 text-indigo-500" />
                </div>
                <div className="relative z-10 space-y-6 flex-1">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-[20px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                      <Zap className="w-7 h-7 text-indigo-500" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-black tracking-tight text-white uppercase">{selectedSchedule.title}</h2>
                      <div className="flex items-center gap-6 mt-2">
                        <div className="flex items-center gap-2 text-[11px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Mail className="w-3.5 h-3.5 text-indigo-500" />
                          <span>{selectedSchedule.email_recipient}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Clock className="w-3.5 h-3.5 text-indigo-500" />
                          <span className="capitalize">{selectedSchedule.schedule_type}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] font-bold text-[#64748B] uppercase tracking-widest">
                          <div className={cn("w-2 h-2 rounded-full", selectedSchedule.status === 'active' ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" : "bg-slate-500")} />
                          <span className="capitalize">{selectedSchedule.status}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-8 pt-4">
                    {[
                      { label: 'Next Run', val: 'Tomorrow, 09:00 AM', icon: Calendar },
                      { label: 'Last Run', val: '2 hours ago', icon: History },
                      { label: 'Current Engine', val: 'Playwright', icon: Cpu },
                      { label: 'Attempt', val: '1 / 3', icon: RefreshCw }
                    ].map((item, i) => (
                      <div key={i} className="space-y-1.5">
                        <div className="flex items-center gap-2 text-[9px] font-black text-[#64748B] uppercase tracking-[0.2em]">
                          <item.icon className="w-3 h-3" />
                          {item.label}
                        </div>
                        <div className="text-xs font-black text-[#CBD5E1] uppercase tracking-wider">{item.val}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="relative z-10 flex flex-col gap-3">
                  <Button 
                    onClick={handleRunNow}
                    disabled={isRunning}
                    className="h-14 px-10 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 min-w-[200px] flex items-center justify-center gap-3"
                  >
                    {isRunning ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Play className="w-5 h-5 fill-current" />
                    )}
                    {isRunning ? "RUNNING..." : "RUN NOW"}
                  </Button>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => setIsEditing(true)}
                      className="flex-1 h-12 rounded-xl border-[#1F2937] bg-[#111827]/60 text-[#CBD5E1] hover:bg-white/5 transition-all"
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
              <div className="grid grid-cols-12 gap-8">
                
                {/* Left Column - Progress & Pipeline */}
                <div className="col-span-8 space-y-8">
                  
                  {/* Current Run Progress */}
                  <div className="bg-[#111827]/40 rounded-[32px] border border-[#1F2937] p-8 flex items-center gap-10">
                    <div className="relative w-32 h-32 shrink-0">
                      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                        <circle className="text-[#1F2937]" strokeWidth="8" stroke="currentColor" fill="transparent" r="42" cx="50" cy="50" />
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
                        <span className="text-2xl font-black text-white">{currentProgress}%</span>
                        <span className="text-[8px] font-black text-[#64748B] uppercase tracking-widest">Progress</span>
                      </div>
                    </div>
                    
                    <div className="flex-1 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <div className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">Current Status</div>
                          <div className="text-lg font-black text-white uppercase tracking-tight">Running Automation...</div>
                        </div>
                        <div className="text-right space-y-1">
                          <div className="text-[10px] font-black text-[#64748B] uppercase tracking-[0.2em]">ETA</div>
                          <div className="text-lg font-black text-white uppercase tracking-tight">30s</div>
                        </div>
                      </div>
                      <div className="h-2 w-full bg-[#1F2937] rounded-full overflow-hidden">
                        <motion.div 
                          className="h-full bg-gradient-to-r from-indigo-600 to-purple-600"
                          initial={{ width: 0 }}
                          animate={{ width: `${currentProgress}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[9px] font-black text-[#64748B] uppercase tracking-widest">
                        <span>Started: 04:42:10 PM</span>
                        <span>3 / 4 Steps Completed</span>
                      </div>
                    </div>
                  </div>

                  {/* Execution Pipeline */}
                  <div className="bg-[#111827]/40 rounded-[32px] border border-[#1F2937] p-8 space-y-8">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Workflow className="w-5 h-5 text-indigo-500" />
                        <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Execution Pipeline</h3>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                        <span className="text-[9px] font-black text-indigo-500 uppercase tracking-widest">Live Tracking</span>
                      </div>
                    </div>

                    <div className="relative flex items-center justify-between px-4">
                      {/* Connector Line */}
                      <div className="absolute top-6 left-10 right-10 h-0.5 bg-[#1F2937] z-0" />
                      
                      {pipelineSteps.map((step, i) => (
                        <div key={step.id} className="relative z-10 flex flex-col items-center gap-4 group">
                          <div className={cn(
                            "w-12 h-12 rounded-2xl border flex items-center justify-center transition-all duration-500 shadow-xl",
                            step.status === 'completed' ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-500" :
                            step.status === 'running' ? "bg-indigo-500/10 border-indigo-500 text-indigo-500 animate-pulse" :
                            "bg-[#05070A] border-[#1F2937] text-[#374151]"
                          )}>
                            {step.status === 'completed' ? <Check className="w-6 h-6" /> : 
                             step.status === 'running' ? <RefreshCw className="w-5 h-5 animate-spin-slow" /> :
                             <span className="text-sm font-black">{step.id}</span>}
                          </div>
                          <div className="text-center space-y-1">
                            <div className={cn(
                              "text-[10px] font-black uppercase tracking-widest transition-colors",
                              step.status === 'pending' ? "text-[#374151]" : "text-white"
                            )}>{step.name}</div>
                            <div className="text-[8px] font-bold text-[#64748B] uppercase tracking-tighter">{step.time}</div>
                            {step.status === 'completed' && (
                              <div className="text-[8px] font-black text-emerald-500 uppercase tracking-widest">{step.duration}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Tabs for AI Context & Logs */}
                  <div className="bg-[#111827]/40 rounded-[32px] border border-[#1F2937] overflow-hidden flex flex-col min-h-[500px]">
                    <div className="px-8 pt-6 flex items-center gap-8 border-b border-[#1F2937] shrink-0">
                      {[
                        { id: 'pipeline', label: 'Live Logs', icon: Terminal },
                        { id: 'ai', label: 'AI Planning', icon: Brain },
                        { id: 'script', label: 'Generated Script', icon: Code },
                        { id: 'history', label: 'Run History', icon: History }
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={cn(
                            "flex items-center gap-2.5 pb-4 text-[11px] font-black uppercase tracking-[0.15em] transition-all relative",
                            activeTab === tab.id ? "text-indigo-500" : "text-[#64748B] hover:text-[#CBD5E1]"
                          )}
                        >
                          <tab.icon className="w-4 h-4" />
                          {tab.label}
                          {activeTab === tab.id && (
                            <motion.div layoutId="activeTabSchedules" className="absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]" />
                          )}
                        </button>
                      ))}
                    </div>

                    <div className="flex-1 p-6 overflow-y-auto hide-scrollbar">
                      <AnimatePresence mode="wait">
                        {activeTab === 'pipeline' && (
                          <motion.div
                            key="logs"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="space-y-2 font-mono"
                          >
                            {liveLogs.length > 0 ? (
                              liveLogs.map((log, i) => (
                                <div key={i} className="flex items-start gap-4 text-[11px] py-1 group hover:bg-white/5 rounded px-2 transition-colors">
                                  <span className="text-[#374151] shrink-0">{log.time}</span>
                                  <span className={cn("font-black shrink-0 w-20", log.type === 'error' ? 'text-red-400' : 'text-indigo-400')}>[{log.engine || 'SYS'}]</span>
                                  <span className="text-[#CBD5E1]">{log.message}</span>
                                </div>
                              ))
                            ) : (
                              <div className="py-20 text-center">
                                <Terminal className="w-8 h-8 text-[#1F2937] mx-auto mb-3" />
                                <p className="text-[10px] font-black text-[#374151] uppercase tracking-widest">Waiting for execution logs...</p>
                              </div>
                            )}
                            {isRunning && (
                              <div className="flex items-center gap-2 text-[11px] py-1 px-2">
                                <Loader2 className="w-3 h-3 animate-spin text-indigo-500" />
                                <span className="text-indigo-500 animate-pulse">Processing next instruction...</span>
                              </div>
                            )}
                          </motion.div>
                        )}

                        {activeTab === 'ai' && (
                          <motion.div
                            key="ai"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="space-y-6"
                          >
                            <div className="p-6 rounded-2xl bg-[#05070A] border border-[#1F2937] space-y-4">
                              <div className="flex items-center gap-2.5">
                                <Target className="w-4 h-4 text-purple-500" />
                                <h4 className="text-[11px] font-black text-white uppercase tracking-widest">Execution Strategy</h4>
                              </div>
                              <p className="text-sm text-[#CBD5E1] leading-relaxed">
                                {selectedSchedule.assistant_response || "The agent will use Playwright to navigate to the target URL, perform a visual check of the page content, and extract the required data points. If Playwright fails due to complex UI or anti-bot measures, the system will automatically fallback to the Browser Use engine for a more resilient interaction."}
                              </p>
                            </div>
                            
                            {/* Rehydrated Plan */}
                            <div className="space-y-3">
                              <div className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Original Agent Plan</div>
                              {selectedSchedule.plan_data ? (
                                (JSON.parse(selectedSchedule.plan_data) as any[]).map((task: any, i: number) => (
                                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-[#05070A] border border-[#1F2937]">
                                    <div className="w-5 h-5 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[9px] font-black text-indigo-500">{i + 1}</div>
                                    <span className="text-xs text-[#CBD5E1] font-medium">{task.title}</span>
                                  </div>
                                ))
                              ) : (
                                <p className="text-[10px] text-[#374151] italic ml-1">No plan data stored for this schedule.</p>
                              )}
                            </div>
                          </motion.div>
                        )}

                        {activeTab === 'script' && (
                          <motion.div
                            key="script"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="space-y-6"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                                  <Code className="w-5 h-5 text-indigo-500" />
                                </div>
                                <div>
                                  <h4 className="text-sm font-black text-white uppercase tracking-widest">Automation Script</h4>
                                  <p className="text-[10px] text-[#64748B] font-bold uppercase tracking-widest">Production-ready Python code</p>
                                </div>
                              </div>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                onClick={() => handleCopyCode(selectedSchedule.generated_script)}
                                className="h-9 px-4 rounded-xl border-[#1F2937] bg-white/5 text-[#CBD5E1] text-[10px] font-black uppercase tracking-widest hover:bg-white/10 gap-2"
                              >
                                {copySuccess ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                                {copySuccess || "COPY CODE"}
                              </Button>
                            </div>
                            <div className="rounded-2xl border border-[#1F2937] bg-[#05070A] overflow-hidden">
                              <div className="px-4 py-2 border-b border-[#1F2937] bg-white/[0.02] flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <div className="w-2 h-2 rounded-full bg-red-500/50" />
                                  <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                                  <div className="w-2 h-2 rounded-full bg-green-500/50" />
                                </div>
                                <span className="text-[9px] font-black text-[#374151] uppercase tracking-widest">automation_script.py</span>
                              </div>
                              <pre className="p-6 text-[12px] font-mono text-[#CBD5E1] overflow-x-auto leading-relaxed hide-scrollbar max-h-[600px]">
                                <code>{selectedSchedule.generated_script || "# No script generated yet."}</code>
                              </pre>
                            </div>
                          </motion.div>
                        )}

                        {activeTab === 'history' && (
                          <motion.div
                            key="history"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="space-y-4"
                          >
                            <table className="w-full text-left text-[11px]">
                              <thead>
                                <tr className="text-[#64748B] font-black uppercase tracking-widest border-b border-[#1F2937]">
                                  <th className="pb-4 px-2">Run ID</th>
                                  <th className="pb-4 px-2">Date</th>
                                  <th className="pb-4 px-2">Status</th>
                                  <th className="pb-4 px-2">Engine</th>
                                  <th className="pb-4 px-2">Duration</th>
                                  <th className="pb-4 px-2 text-right">Action</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-[#1F2937]">
                                {runs.map((run) => (
                                  <tr key={run.run_id} className="group hover:bg-white/5 transition-colors">
                                    <td className="py-4 px-2 font-mono text-indigo-400">{run.run_id}</td>
                                    <td className="py-4 px-2 text-[#CBD5E1]">{formatDate(run.created_at).split(',')[0]}</td>
                                    <td className="py-4 px-2">
                                      <span className={cn(
                                        "px-2 py-0.5 rounded-md text-[9px] font-black uppercase",
                                        run.status === 'completed' ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                                      )}>{run.status}</span>
                                    </td>
                                    <td className="py-4 px-2 text-[#64748B] font-bold">{run.engine}</td>
                                    <td className="py-4 px-2 text-[#64748B] font-bold">{run.duration_seconds}s</td>
                                    <td className="py-4 px-2 text-right">
                                      <button className="p-2 rounded-lg hover:bg-white/10 text-[#64748B] hover:text-white transition-all">
                                        <ExternalLink className="w-3.5 h-3.5" />
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </div>

                {/* Right Column - Summary & Browser */}
                <div className="col-span-4 space-y-8">
                  
                  {/* Execution Summary */}
                  <div className="bg-[#111827]/40 rounded-[32px] border border-[#1F2937] p-8 space-y-6">
                    <div className="flex items-center gap-3">
                      <Gauge className="w-5 h-5 text-indigo-500" />
                      <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Execution Summary</h3>
                    </div>
                    
                    <div className="space-y-4">
                      {[
                        { label: 'Memory Usage', val: '245 MB', icon: Database, color: 'text-indigo-500' },
                        { label: 'CPU Usage', val: '12%', icon: Activity, color: 'text-emerald-500' },
                        { label: 'Network Status', val: 'Stable', icon: Network, color: 'text-blue-500' },
                        { label: 'Browser Status', val: 'Active', icon: Globe, color: 'text-purple-500' }
                      ].map((item, i) => (
                        <div key={i} className="flex items-center justify-between p-4 rounded-2xl bg-[#05070A] border border-[#1F2937]">
                          <div className="flex items-center gap-3">
                            <item.icon className={cn("w-4 h-4", item.color)} />
                            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-widest">{item.label}</span>
                          </div>
                          <span className="text-xs font-black text-white uppercase">{item.val}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Live Browser Preview */}
                  <div className="bg-[#111827]/40 rounded-[32px] border border-[#1F2937] overflow-hidden flex flex-col">
                    <div className="px-6 py-4 border-b border-[#1F2937] flex items-center justify-between bg-white/[0.02]">
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-indigo-500" />
                        <span className="text-[10px] font-black text-white uppercase tracking-widest">Live Browser</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button className="p-1.5 rounded-lg hover:bg-white/5 text-[#64748B] hover:text-white transition-all">
                          <Maximize2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="aspect-video bg-black relative group">
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
                      
                      {/* Browser Toolbar Overlay */}
                      <div className="absolute bottom-4 left-4 right-4 p-3 rounded-xl bg-[#05070A]/80 backdrop-blur-md border border-white/10 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        <div className="flex items-center gap-3">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-[9px] font-black text-[#CBD5E1] uppercase truncate max-w-[150px]">
                            {liveLogs.filter(l => l.message.includes('https://')).pop()?.message.match(/https?:\/\/[^\s]+/)?.[0] || "https://browser.live"}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button className="p-1.5 rounded-lg hover:bg-white/10 text-[#64748B] hover:text-white"><RefreshCw className="w-3 h-3" /></button>
                          <button className="p-1.5 rounded-lg hover:bg-white/10 text-[#64748B] hover:text-white"><ZoomIn className="w-3 h-3" /></button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Final Result Card (If completed) */}
                  <div className="bg-gradient-to-br from-indigo-600/20 to-purple-600/20 rounded-[32px] border border-indigo-500/30 p-8 space-y-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-6 opacity-10">
                      <Shield className="w-20 h-20 text-white" />
                    </div>
                    <div className="relative z-10 space-y-4">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Final Result</h3>
                      </div>
                      <div className="p-5 rounded-2xl bg-[#05070A]/60 border border-white/5 backdrop-blur-sm">
                        <p className="text-xs text-[#CBD5E1] leading-relaxed font-medium">
                          {selectedSchedule.extracted_content || "No results available yet. Run the schedule to see data."}
                        </p>
                      </div>
                      {selectedSchedule.extracted_content && (
                        <Button 
                          onClick={() => {
                            const blob = new Blob([selectedSchedule.extracted_content], { type: 'text/plain' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `report-${selectedSchedule.schedule_id}.txt`;
                            a.click();
                          }}
                          className="w-full h-12 rounded-xl bg-white text-indigo-600 text-[10px] font-black uppercase tracking-widest hover:bg-[#F8FAFC] transition-all gap-2"
                        >
                          <Download className="w-4 h-4" />
                          DOWNLOAD FULL REPORT
                        </Button>
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
                <div className="relative w-24 h-24 rounded-[32px] bg-[#111827] border border-[#1F2937] flex items-center justify-center text-indigo-500 shadow-2xl">
                  <Activity className="w-12 h-12" />
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-black text-white uppercase tracking-tight">Select an Automation</h3>
                <p className="text-sm text-[#64748B] max-w-xs mx-auto font-bold uppercase tracking-widest leading-relaxed">
                  Choose a task from the sidebar to monitor its real-time execution and results.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modals (Edit/Delete) - Reusing existing logic but with premium styling */}
      <AnimatePresence>
        {isEditing && (
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-[#05070A]/80 backdrop-blur-xl p-4">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md bg-[#111827] rounded-[32px] shadow-2xl border border-[#1F2937] p-8 space-y-8"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-black text-xl text-white uppercase tracking-tight">Edit Schedule</h3>
                <button onClick={() => setIsEditing(false)} className="text-[#64748B] hover:text-white"><X className="w-6 h-6" /></button>
              </div>
              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Task Title</label>
                  <input 
                    value={editData.title} 
                    onChange={e => setEditData({...editData, title: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-[#05070A] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Frequency</label>
                  <select 
                    value={editData.type} 
                    onChange={e => setEditData({...editData, type: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-[#05070A] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Delivery Email</label>
                  <input 
                    value={editData.email} 
                    onChange={e => setEditData({...editData, email: e.target.value})}
                    className="w-full px-5 py-4 rounded-2xl bg-[#05070A] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                </div>
              </div>
              <div className="flex gap-4 pt-4">
                <Button variant="ghost" onClick={() => setIsEditing(false)} className="flex-1 h-14 rounded-2xl text-[11px] font-black uppercase tracking-widest">CANCEL</Button>
                <Button onClick={handleUpdate} className="flex-1 h-14 rounded-2xl bg-indigo-600 text-white text-[11px] font-black uppercase tracking-widest shadow-xl shadow-indigo-500/20">SAVE CHANGES</Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirmId && (
          <div className="fixed inset-0 z-[120] flex items-center justify-center bg-[#05070A]/80 backdrop-blur-xl p-4">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-sm bg-[#111827] rounded-[32px] shadow-2xl border border-[#1F2937] p-8 text-center space-y-6"
            >
              <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto">
                <AlertCircle className="w-8 h-8 text-red-500" />
              </div>
              <div className="space-y-2">
                <h3 className="font-black text-xl text-white uppercase tracking-tight">Confirm Deletion</h3>
                <p className="text-sm text-[#64748B] font-bold uppercase tracking-widest leading-relaxed">
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
                  className="flex-1 h-14 bg-red-500 hover:bg-red-600 text-white text-[11px] font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-red-500/20"
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
