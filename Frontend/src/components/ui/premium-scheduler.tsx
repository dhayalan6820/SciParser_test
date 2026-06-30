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
  
  // Advanced Options
  const [retryCount, setRetryCount] = React.useState(3);
  const [timeout, setTimeoutVal] = React.useState(120);
  const [headless, setHeadless] = React.useState(true);

  // Truncate tool output to keep token cost low
  const summarizeOutput = (raw: unknown, maxChars = 500): string => {
    const str = typeof raw === 'string' ? raw : JSON.stringify(raw ?? '');
    if (str.length <= maxChars) return str;
    return str.slice(0, maxChars) + `… [+${str.length - maxChars} chars truncated]`;
  };

  const handleCreateSchedule = async () => {
    setScheduleError("");
    try {
      setLoading(true);

      // Build compact tool context — only SUCCESS/COMPLETED tools, output truncated
      const tool_context = (toolLogs || [])
        .filter(log => log.status === 'SUCCESS' || log.status === 'COMPLETED')
        .map(log => ({
          tool_name: log.tool_name,
          output: summarizeOutput(log.tool_output)
        }));

      const data = {
        chat_id: chatId,
        title: taskName || "New Automation Task",
        schedule_type: scheduleType,
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

  // All tool logs for display; success-only count drives the badge
  const allTools = toolLogs || [];
  const successTools = allTools.filter(
    log => log.status === 'SUCCESS' || log.status === 'COMPLETED'
  );

  // --- FIX: Ensure activeTab switches correctly ---
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#05070A]/80 backdrop-blur-xl p-4 md:p-8">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full max-w-[1400px] h-full max-h-[95vh] bg-[#05070A] rounded-[24px] shadow-2xl border border-[#1F2937] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="min-h-14 sm:h-20 px-4 sm:px-8 border-b border-[#1F2937] flex items-center justify-between bg-[#111827]/50 shrink-0 py-3 sm:py-0">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="w-9 h-9 sm:w-12 sm:h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shrink-0">
              <Calendar className="w-5 h-5 sm:w-6 sm:h-6 text-indigo-500" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base sm:text-xl font-black tracking-tight text-white uppercase truncate">Schedule Automation Task</h1>
              <p className="hidden sm:block text-xs text-[#64748B] font-bold uppercase tracking-widest">Configure and schedule your automation to run on a recurring basis.</p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={onClose} 
            className="h-10 w-10 sm:h-12 sm:w-12 rounded-2xl hover:bg-white/5 text-[#64748B] hover:text-white transition-all shrink-0"
          >
            <X className="w-5 h-5 sm:w-6 sm:h-6" />
          </Button>
        </div>

        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left Panel - Configuration */}
          <div className="w-full md:w-[38%] border-b md:border-b-0 md:border-r border-[#1F2937] bg-[#05070A] flex flex-col overflow-y-auto hide-scrollbar p-5 sm:p-8 space-y-6 sm:space-y-10 shrink-0">
            
            {/* 1. Schedule Configuration */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500 text-[10px] font-black border border-emerald-500/20">1</div>
                <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Schedule Configuration</h3>
              </div>
              
              <div className="space-y-4">
                <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Frequency</label>
                <div className="grid grid-cols-3 gap-3">
                  {['daily', 'weekly', 'monthly'].map((type) => (
                    <button
                      key={type}
                      onClick={() => setScheduleType(type)}
                      className={cn(
                        "flex flex-col items-center justify-center gap-3 p-5 rounded-2xl border transition-all duration-300 group",
                        scheduleType === type 
                          ? "bg-indigo-500/10 border-indigo-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.15)]" 
                          : "bg-[#111827] border-[#1F2937] text-[#64748B] hover:border-[#374151] hover:text-[#CBD5E1]"
                      )}
                    >
                      <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
                        scheduleType === type ? "bg-indigo-500 text-white" : "bg-[#1F2937] text-[#64748B] group-hover:bg-[#374151]"
                      )}>
                        <Calendar className="w-5 h-5" />
                      </div>
                      <span className="text-[11px] font-black uppercase tracking-widest">{type}</span>
                      {scheduleType === type && (
                        <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
                          <Check className="w-2.5 h-2.5 text-white" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Time of Day</label>
                  <div className="relative">
                    <Clock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
                    <select className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-[#111827] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none">
                      <option>09:00 AM</option>
                      <option>12:00 PM</option>
                      <option>06:00 PM</option>
                      <option>12:00 AM</option>
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Timezone</label>
                  <div className="relative">
                    <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
                    <select className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-[#111827] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 appearance-none">
                      <option>(GMT+05:30) Asia/Kolkata</option>
                      <option>(GMT+00:00) UTC</option>
                      <option>(GMT-05:00) EST</option>
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] pointer-events-none" />
                  </div>
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 space-y-3">
                <div className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Next Run Preview</div>
                <div className="flex items-center gap-4">
                  <Calendar className="w-5 h-5 text-indigo-500" />
                  <div>
                    <div className="text-sm font-bold text-white">Tomorrow, 29 Jun 2026</div>
                    <div className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">at 09:00 AM (GMT+05:30)</div>
                  </div>
                </div>
              </div>
            </section>

            {/* 2. Notifications */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-500 text-[10px] font-black border border-indigo-500/20">2</div>
                <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Notifications</h3>
              </div>
              <div className="space-y-4">
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B] group-focus-within:text-indigo-500 transition-colors" />
                  <input
                    type="email"
                    placeholder="example@company.com"
                    value={emailRecipient}
                    onChange={(e) => setEmailRecipient(e.target.value)}
                    className="w-full pl-11 pr-4 py-4 rounded-xl bg-[#111827] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all placeholder:text-[#64748B]"
                  />
                  <button className="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 rounded-lg bg-[#1F2937] text-[10px] font-black text-[#CBD5E1] hover:bg-[#374151] transition-colors uppercase tracking-widest">
                    + Add more
                  </button>
                </div>
                <div className="flex items-center gap-2 px-1">
                  <Bell className="w-3.5 h-3.5 text-indigo-500" />
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-widest">Receive results and alerts via email.</span>
                </div>
              </div>
            </section>

            {/* 3. Task Details */}
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-purple-500/10 flex items-center justify-center text-purple-500 text-[10px] font-black border border-purple-500/20">3</div>
                <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Task Details</h3>
              </div>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Task Name <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    placeholder="e.g. Check website availability"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    className="w-full px-4 py-4 rounded-xl bg-[#111827] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all placeholder:text-[#64748B]"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-[#64748B] uppercase tracking-widest ml-1">Description (Optional)</label>
                  <textarea
                    placeholder="Provide a brief description of this task..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-4 py-4 rounded-xl bg-[#111827] border border-[#1F2937] text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all placeholder:text-[#64748B] min-h-[100px] resize-none"
                  />
                  <div className="text-right text-[10px] font-bold text-[#64748B] uppercase tracking-widest">0 / 500</div>
                </div>
              </div>
            </section>

            {/* 4. Advanced Options */}
            <section className="space-y-6 pb-8">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-500 text-[10px] font-black border border-indigo-500/20">4</div>
                  <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Advanced Options</h3>
                </div>
                <ChevronDown className="w-4 h-4 text-[#64748B]" />
              </div>
              <div className="p-5 rounded-2xl bg-[#111827] border border-[#1F2937] space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-indigo-500" />
                    <span className="text-[11px] font-bold text-[#CBD5E1] uppercase tracking-wider">Retry Attempts</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={() => setRetryCount(Math.max(0, retryCount - 1))} className="w-8 h-8 rounded-lg bg-[#1F2937] border border-[#374151] flex items-center justify-center text-white hover:bg-[#374151]">-</button>
                    <span className="text-sm font-black text-white w-4 text-center">{retryCount}</span>
                    <button onClick={() => setRetryCount(Math.min(5, retryCount + 1))} className="w-8 h-8 rounded-lg bg-[#1F2937] border border-[#374151] flex items-center justify-center text-white hover:bg-[#374151]">+</button>
                  </div>
                </div>
                <div className="h-px bg-[#1F2937]" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-[11px] font-bold text-[#CBD5E1] uppercase tracking-wider">Execution Timeout</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input 
                      type="number" 
                      value={timeout} 
                      onChange={(e) => setTimeoutVal(parseInt(e.target.value))}
                      className="w-16 px-2 py-1.5 rounded-lg bg-[#1F2937] border border-[#374151] text-xs font-black text-white text-center focus:outline-none"
                    />
                    <span className="text-[10px] font-bold text-[#64748B] uppercase">sec</span>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* Right Panel - AI Context & Preview */}
          <div className="flex-1 bg-[#05070A] flex flex-col overflow-hidden">
            {/* Tabs */}
            <div className="px-8 pt-6 flex items-center gap-8 border-b border-[#1F2937] shrink-0">
              {[
                { id: 'context', label: 'AI Context', icon: Brain },
                { id: 'plan', label: 'AI Plan', icon: Workflow },
                { id: 'response', label: 'AI Response', icon: MessageSquare },
                { id: 'tools', label: 'MCP Tools', icon: Cpu, count: successTools.length }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={cn(
                    "flex items-center gap-2.5 pb-4 text-[11px] font-black uppercase tracking-[0.15em] transition-all relative",
                    activeTab === tab.id ? "text-indigo-500" : "text-[#64748B] hover:text-[#CBD5E1]"
                  )}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 rounded-md bg-[#111827] border border-[#1F2937] text-[9px] text-indigo-400">
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
            <div className="flex-1 overflow-y-auto p-8 hide-scrollbar space-y-8">
              <AnimatePresence mode="wait">
                {activeTab === 'context' && (
                  <motion.div
                    key="context"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="grid grid-cols-2 gap-6"
                  >
                    {/* User Inputs */}
                    <div className="p-6 rounded-2xl bg-[#111827] border border-[#1F2937] space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <UserIcon className="w-4 h-4 text-emerald-500" />
                          <h4 className="text-[11px] font-black text-white uppercase tracking-widest">User Inputs</h4>
                        </div>
                        <Info className="w-4 h-4 text-[#64748B]" />
                      </div>
                      <p className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">View the inputs provided for this task.</p>
                      <div className="p-4 rounded-xl bg-[#05070A] border border-[#1F2937] min-h-[120px] overflow-y-auto max-h-[200px] hide-scrollbar">
                        <p className="text-sm text-[#CBD5E1] leading-relaxed italic">"{userPrompt}"</p>
                      </div>
                      <button className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-[#1F2937] hover:bg-[#374151] transition-colors group">
                        <span className="text-[10px] font-black text-[#CBD5E1] uppercase tracking-widest">View Details</span>
                        <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-all" />
                      </button>
                    </div>

                    {/* AI Understanding */}
                    <div className="p-6 rounded-2xl bg-[#111827] border border-[#1F2937] space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <Sparkles className="w-4 h-4 text-indigo-500" />
                          <h4 className="text-[11px] font-black text-white uppercase tracking-widest">AI Plan (Agent Plan)</h4>
                        </div>
                        <Info className="w-4 h-4 text-[#64748B]" />
                      </div>
                      <p className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">Steps the agent will follow to complete the task.</p>
                      <div className="space-y-3 overflow-y-auto max-h-[200px] hide-scrollbar">
                        {displayPlan && displayPlan.length > 0 ? (
                          displayPlan.map((task, i) => (
                            <div key={task.id || i} className="flex items-center gap-3">
                              <div className="w-5 h-5 rounded-md bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[9px] font-black text-indigo-500 shrink-0">{i + 1}</div>
                              <span className="text-xs text-[#CBD5E1] font-medium truncate">{task.title}</span>
                            </div>
                          ))
                        ) : (
                          <div className="py-6 flex flex-col items-center justify-center gap-2">
                            <Workflow className="w-6 h-6 text-[#374151]" />
                            <p className="text-[10px] font-black text-[#374151] uppercase tracking-widest">No plan in selected context</p>
                          </div>
                        )}
                      </div>
                      <button 
                        onClick={() => handleTabChange('plan')}
                        className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-[#1F2937] hover:bg-[#374151] transition-colors group"
                      >
                        <span className="text-[10px] font-black text-[#CBD5E1] uppercase tracking-widest">View Full Plan</span>
                        <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-all" />
                      </button>
                    </div>

                    {/* AI Response Summary */}
                    <div className="col-span-2 p-6 rounded-2xl bg-[#111827] border border-[#1F2937] space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <Target className="w-4 h-4 text-purple-500" />
                          <h4 className="text-[11px] font-black text-white uppercase tracking-widest">AI Response (Summary)</h4>
                        </div>
                        <Info className="w-4 h-4 text-[#64748B]" />
                      </div>
                      <p className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">AI understanding and response.</p>
                      <div className="p-5 rounded-xl bg-[#05070A] border border-[#1F2937] overflow-y-auto max-h-[200px] hide-scrollbar">
                        <p className="text-sm text-[#CBD5E1] leading-relaxed">
                          {aiResponse || "I will check the website availability by navigating to the provided URL, validating the HTTP status code and page content. If the site is down or returns an error, I will notify you via email with the details."}
                        </p>
                      </div>
                      <button 
                        onClick={() => handleTabChange('response')}
                        className="w-full py-3 flex items-center justify-between px-4 rounded-xl bg-[#1F2937] hover:bg-[#374151] transition-colors group"
                      >
                        <span className="text-[10px] font-black text-[#CBD5E1] uppercase tracking-widest">View Full Response</span>
                        <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-all" />
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
                        <h4 className="text-sm font-black text-white uppercase tracking-widest">AI Plan</h4>
                        <p className="text-[10px] text-[#64748B] font-bold uppercase tracking-widest">Full step-by-step execution plan.</p>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {displayPlan && displayPlan.length > 0 ? (
                        displayPlan.map((task, i) => (
                          <div key={task.id || i} className="p-5 rounded-2xl bg-[#111827] border border-[#1F2937] space-y-3">
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="w-6 h-6 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[10px] font-black text-indigo-500 shrink-0">{i + 1}</div>
                                <span className="text-xs font-black text-white uppercase tracking-wider truncate">{task.title}</span>
                              </div>
                              <div className="px-2 py-0.5 rounded-md bg-[#05070A] border border-[#1F2937] text-[9px] text-[#64748B] font-bold uppercase shrink-0">
                                {task.status || "pending"}
                              </div>
                            </div>
                            <p className="text-xs text-[#CBD5E1] leading-relaxed pl-9">{task.description}</p>
                            {task.subtasks && task.subtasks.length > 0 && (
                              <div className="pl-9 pt-2 space-y-2">
                                {task.subtasks.map((sub: Subtask, si: number) => (
                                  <div key={sub.id || si} className="flex items-center gap-2 text-[10px] text-[#64748B]">
                                    <div className="w-1.5 h-1.5 rounded-full bg-[#374151]" />
                                    <span>{sub.title}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="py-20 flex flex-col items-center justify-center bg-[#111827] border border-[#1F2937] rounded-[32px] border-dashed">
                          <Workflow className="w-10 h-10 text-[#374151] mb-4" />
                          <p className="text-xs font-black text-[#64748B] uppercase tracking-widest">No plan data available</p>
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
                        <h4 className="text-sm font-black text-white uppercase tracking-widest">AI Response</h4>
                        <p className="text-[10px] text-[#64748B] font-bold uppercase tracking-widest">The full response for the selected context.</p>
                      </div>
                    </div>

                    <div className="p-8 rounded-[32px] bg-[#111827] border border-[#1F2937] min-h-[400px] overflow-y-auto hide-scrollbar">
                      <p className="text-[#CBD5E1] leading-relaxed whitespace-pre-wrap text-sm">
                        {aiResponse || "No AI response selected"}
                      </p>
                    </div>
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
                          <h4 className="text-sm font-black text-white uppercase tracking-widest">
                            MCP Tools ({successTools.length} / {allTools.length})
                          </h4>
                          <p className="text-[10px] text-[#64748B] font-bold uppercase tracking-widest">
                            Success tools included in script generation
                          </p>
                        </div>
                      </div>
                      {/* Info pill: how many will be sent */}
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">
                          {successTools.length} will be sent
                        </span>
                      </div>
                    </div>

                    {allTools.length === 0 ? (
                      <div className="py-20 flex flex-col items-center justify-center bg-[#111827] border border-[#1F2937] rounded-[32px] border-dashed">
                        <Cpu className="w-10 h-10 text-[#374151] mb-4" />
                        <p className="text-xs font-black text-[#64748B] uppercase tracking-widest">No tool activity recorded</p>
                        <p className="text-[10px] text-[#374151] mt-2 uppercase font-bold">Run an automation first to populate the tool log.</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                        {allTools.map((log, i) => {
                          const isSuccess = log.status === 'SUCCESS' || log.status === 'COMPLETED';
                          const isFailed  = log.status === 'FAILED'  || log.status === 'ERROR';
                          return (
                            <div
                              key={log.id || i}
                              className={cn(
                                "p-5 rounded-2xl border transition-all",
                                isSuccess
                                  ? "bg-[#111827] border-emerald-500/30"
                                  : isFailed
                                  ? "bg-[#111827]/50 border-[#1F2937] opacity-50"
                                  : "bg-[#111827] border-[#1F2937]"
                              )}
                            >
                              <div className="flex items-center gap-3">
                                <div className={cn(
                                  "w-9 h-9 rounded-xl border flex items-center justify-center shrink-0",
                                  isSuccess
                                    ? "bg-emerald-500/10 border-emerald-500/20"
                                    : "bg-[#05070A] border-[#1F2937]"
                                )}>
                                  <Terminal className={cn(
                                    "w-4 h-4",
                                    isSuccess ? "text-emerald-500" : "text-[#64748B]"
                                  )} />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="text-xs font-black text-white uppercase tracking-wider truncate">
                                    {log.tool_name}
                                  </div>
                                  <div className={cn(
                                    "text-[10px] font-bold uppercase tracking-widest",
                                    isSuccess ? "text-emerald-500" :
                                    isFailed  ? "text-red-400" :
                                    "text-[#64748B]"
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
                              <div className="mt-3 p-2 rounded-lg bg-black/20 border border-white/5 text-[9px] text-[#64748B] font-mono line-clamp-3 overflow-hidden">
                                {summarizeOutput(log.tool_output, 200)}
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
                  <h4 className="text-[11px] font-black text-white uppercase tracking-widest">Execution Flow Preview</h4>
                </div>
                <p className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">How this task will be executed.</p>
                
                <div className="relative p-8 rounded-[32px] bg-[#111827] border border-[#1F2937] overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5" />
                  
                  <div className="relative flex items-center justify-between gap-4">
                    {[
                      { label: 'Generate AI Plan', sub: 'Understand task & create plan', icon: UserIcon, color: 'text-emerald-500' },
                      { label: 'Generate Script (Playwright)', sub: 'Create automation script', icon: Database, color: 'text-indigo-500' },
                      { label: 'Execute Playwright', sub: 'Run script in browser', icon: Cpu, color: 'text-purple-500' }
                    ].map((node, i) => (
                      <React.Fragment key={i}>
                        <div className="flex flex-col items-center gap-4 text-center max-w-[140px]">
                          <div className="w-12 h-12 rounded-2xl bg-[#05070A] border border-[#1F2937] flex items-center justify-center shadow-xl">
                            <node.icon className={cn("w-6 h-6", node.color)} />
                          </div>
                          <div className="space-y-1">
                            <div className="text-[10px] font-black text-white uppercase tracking-widest">{node.label}</div>
                            <div className="text-[9px] text-[#64748B] font-bold uppercase tracking-tight leading-tight">{node.sub}</div>
                          </div>
                        </div>
                        {i < 2 && <ArrowRight className="w-4 h-4 text-[#1F2937]" />}
                      </React.Fragment>
                    ))}

                    <ArrowRight className="w-4 h-4 text-[#1F2937]" />

                    {/* Fallback Node */}
                    <div className="relative group">
                      <div className="absolute -inset-4 bg-indigo-500/5 rounded-3xl border border-indigo-500/20 border-dashed" />
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-[9px] font-black text-indigo-400 uppercase tracking-widest">If Failed</div>
                      <div className="flex flex-col items-center gap-4 text-center max-w-[140px] relative z-10">
                        <div className="w-12 h-12 rounded-2xl bg-[#05070A] border border-indigo-500/30 flex items-center justify-center shadow-xl">
                          <RefreshCw className="w-6 h-6 text-indigo-400" />
                        </div>
                        <div className="space-y-1">
                          <div className="text-[10px] font-black text-white uppercase tracking-widest">Browser Use</div>
                          <div className="text-[9px] text-[#64748B] font-bold uppercase tracking-tight leading-tight">(Attempt 1-3)</div>
                          <div className="text-[8px] text-indigo-400 font-black uppercase tracking-widest">Fallback & retry up to 3 attempts</div>
                        </div>
                      </div>
                    </div>

                    <ArrowRight className="w-4 h-4 text-[#1F2937]" />

                    <div className="flex flex-col items-center gap-4 text-center max-w-[140px]">
                      <div className="w-12 h-12 rounded-2xl bg-[#05070A] border border-emerald-500/30 flex items-center justify-center shadow-xl">
                        <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="text-[10px] font-black text-white uppercase tracking-widest">Complete Task</div>
                        <div className="text-[9px] text-[#64748B] font-bold uppercase tracking-tight leading-tight">Store results & notify</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Execution Config Summary */}
                <div className="grid grid-cols-4 gap-4">
                  {[
                    { label: 'Retry Attempts', val: 'Max 3 attempts', icon: RefreshCw },
                    { label: 'Timeout', val: '120 seconds', icon: Clock },
                    { label: 'Browser', val: 'Chromium (Headless)', icon: Globe },
                    { label: 'Notification', val: 'On Failure & Success', icon: Bell },
                    { label: 'Log Retention', val: '30 Days', icon: Database }
                  ].map((item, i) => (
                    <div key={i} className={cn("p-4 rounded-xl bg-[#111827] border border-[#1F2937] space-y-2", i === 4 && "col-span-1")}>
                      <div className="text-[9px] font-black text-[#64748B] uppercase tracking-widest">{item.label}</div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider">{item.val}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Selection Summary */}
              <div className="p-8 rounded-[32px] bg-gradient-to-br from-[#111827] to-[#05070A] border border-[#1F2937] relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-10">
                  <Layout className="w-32 h-32 text-indigo-500" />
                </div>
                <div className="relative z-10 space-y-6">
                  <div className="flex items-center gap-3">
                    <Layers className="w-5 h-5 text-indigo-500" />
                    <h4 className="text-[11px] font-black text-white uppercase tracking-widest">Selection Summary</h4>
                  </div>
                  <p className="text-[11px] text-[#64748B] font-bold uppercase tracking-wider">Review your schedule configuration.</p>
                  
                  <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Calendar className="w-3.5 h-3.5" /> Frequency
                        </div>
                        <span className="text-xs font-black text-white uppercase">{scheduleType}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Clock className="w-3.5 h-3.5" /> Time of Day
                        </div>
                        <span className="text-xs font-black text-white uppercase">09:00 AM</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Globe className="w-3.5 h-3.5" /> Timezone
                        </div>
                        <span className="text-xs font-black text-white uppercase">Asia/Kolkata (GMT+05:30)</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Mail className="w-3.5 h-3.5" /> Delivery Email
                        </div>
                        <span className="text-xs font-black text-white truncate max-w-[150px]">{emailRecipient || "example@company.com"}</span>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Terminal className="w-3.5 h-3.5" /> Task Name
                        </div>
                        <span className="text-xs font-black text-white uppercase truncate max-w-[150px]">{taskName || "Check website availability"}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
                          <Calendar className="w-3.5 h-3.5" /> Next Run
                        </div>
                        <span className="text-xs font-black text-white uppercase text-right">Tomorrow, 29 Jun 2026 at 09:00 AM</span>
                      </div>
                      <div className="pt-4">
                        <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/20 flex items-center gap-3">
                          <Shield className="w-5 h-5 text-emerald-500" />
                          <div>
                            <div className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Secure & Reilable</div>
                            <div className="text-[9px] text-[#64748B] font-bold uppercase tracking-tight leading-tight">Your schedule is encrypted and runs on our secure infrastructure.</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-8 py-4 border-t border-[#1F2937] bg-[#111827]/50 flex flex-col gap-3 shrink-0">
              {scheduleError && (
                <div className="flex items-start gap-3 px-5 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] font-bold text-red-400 leading-relaxed">{scheduleError}</p>
                </div>
              )}
              {scheduleSuccess && (
                <div className="flex items-center gap-3 px-5 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <p className="text-[11px] font-bold text-emerald-400 uppercase tracking-widest">Schedule created successfully!</p>
                </div>
              )}
              <div className="flex items-center justify-between gap-4">
                <button 
                  onClick={onClose} 
                  className="text-[11px] font-black text-[#64748B] hover:text-white transition-colors uppercase tracking-[0.2em]"
                >
                  Cancel
                </button>
                <div className="flex items-center gap-4">
                  <Button 
                    variant="outline"
                    className="h-14 px-8 rounded-2xl border-[#1F2937] bg-transparent text-[#CBD5E1] text-[11px] font-black uppercase tracking-[0.15em] hover:bg-white/5"
                  >
                    Save Draft
                  </Button>
                  <Button 
                    onClick={handleCreateSchedule}
                    disabled={loading || !taskName || scheduleSuccess}
                    className="h-14 px-12 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-black uppercase tracking-[0.2em] shadow-2xl shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 min-w-[240px] flex items-center justify-center gap-3"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Generating Script...</span>
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
