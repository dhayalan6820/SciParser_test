import * as React from "react";
import { Button } from "./button";
import { sciparserApi } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { 
  Calendar, Clock, Code, Play, Pencil, Trash, 
  ChevronLeft, Mail, CheckCircle2, AlertCircle,
  ExternalLink, Copy, Download
} from "lucide-react";
import { motion } from "framer-motion";

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

  React.useEffect(() => {
    fetchSchedules();
  }, []);

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
      setSchedules(prev => prev.filter(s => s.schedule_id !== deleteConfirmId));
      if (selectedSchedule?.schedule_id === deleteConfirmId) setSelectedSchedule(null);
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
      await sciparserApi.runSchedule(selectedSchedule.schedule_id);
      // Poll for updates or just refresh after a bit
      setTimeout(fetchSchedules, 6000);
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
    <div className="flex flex-col h-full w-full bg-background overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-border bg-card px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack} className="rounded-full">
            <ChevronLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground">Automation Schedules</h1>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">Manage your recurring browser tasks</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchSchedules} className="gap-2 text-xs font-bold">
            <Clock className="w-4 h-4" />
            REFRESH
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Schedule List */}
        <div className="w-80 border-r border-border bg-card flex flex-col shrink-0">
          <div className="p-4 border-b border-border">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Your Schedules</div>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-40 gap-3">
                <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                <span className="text-xs text-muted-foreground">Loading...</span>
              </div>
            ) : schedules.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <Calendar className="w-8 h-8 text-muted-foreground mx-auto" />
                <p className="text-xs text-muted-foreground">No schedules found. Create one from the chat!</p>
              </div>
            ) : (
              schedules.map((s) => (
                <div
                  key={s.schedule_id}
                  onClick={() => setSelectedSchedule(s)}
                  className={cn(
                    "p-3 rounded-xl cursor-pointer transition-all border",
                    selectedSchedule?.schedule_id === s.schedule_id
                      ? "bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-500/30"
                      : "bg-transparent border-transparent hover:bg-muted"
                  )}
                >
                  <div className="font-bold text-sm truncate mb-1 text-foreground">{s.title}</div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span className="px-1.5 py-0.5 rounded bg-muted uppercase font-bold tracking-tighter">
                      {s.schedule_type}
                    </span>
                    <span>•</span>
                    <span>{formatDate(s.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Main Content - Details */}
        <div className="flex-1 overflow-y-auto bg-background p-8">
          {selectedSchedule ? (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-4xl mx-auto space-y-8"
            >
              {/* Title & Actions */}
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <h2 className="text-2xl font-bold tracking-tight text-foreground">{selectedSchedule.title}</h2>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Mail className="w-4 h-4" />
                      <span>{selectedSchedule.email_recipient}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-4 h-4" />
                      <span className="capitalize">{selectedSchedule.schedule_type}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className={cn("w-2 h-2 rounded-full", selectedSchedule.status === 'active' ? "bg-emerald-500" : "bg-slate-400")} />
                      <span className="capitalize">{selectedSchedule.status}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button 
                    onClick={handleRunNow}
                    disabled={isRunning}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2 font-bold text-xs px-6 rounded-xl disabled:opacity-50"
                  >
                    {isRunning ? (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <Play className="w-4 h-4 fill-current" />
                    )}
                    {isRunning ? "RUNNING..." : "RUN NOW"}
                  </Button>
                  <Button 
                    variant="outline" 
                    size="icon" 
                    onClick={() => {
                      setEditData({ 
                        title: selectedSchedule.title, 
                        type: selectedSchedule.schedule_type, 
                        email: selectedSchedule.email_recipient 
                      });
                      setIsEditing(true);
                    }}
                    className="rounded-xl border-slate-200 dark:border-white/10"
                  >
                    <Pencil className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="outline" 
                    size="icon" 
                    onClick={() => setDeleteConfirmId(selectedSchedule.schedule_id)}
                    className="rounded-xl border-red-200 text-red-500 hover:bg-red-50 dark:border-red-900/30 dark:hover:bg-red-900/10"
                  >
                    <Trash className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Delete Confirmation Modal */}
              {deleteConfirmId && (
                <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="w-full max-w-sm bg-white dark:bg-[#1a1a1e] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#2f2f3d] p-6 text-center space-y-4"
                  >
                    <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mx-auto">
                      <AlertCircle className="w-6 h-6 text-red-500" />
                    </div>
                    <div className="space-y-2">
                      <h3 className="font-bold text-lg">Confirm Deletion</h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        Are you sure you want to delete this schedule? This action cannot be undone.
                      </p>
                    </div>
                    <div className="flex gap-3 pt-2">
                      <Button 
                        variant="ghost" 
                        onClick={() => setDeleteConfirmId(null)} 
                        className="flex-1 text-xs font-bold"
                      >
                        CANCEL
                      </Button>
                      <Button 
                        onClick={handleDelete} 
                        className="flex-1 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-xl"
                      >
                        DELETE
                      </Button>
                    </div>
                  </motion.div>
                </div>
              )}

              {/* Edit Modal */}
              {isEditing && (
                <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                  <div className="w-full max-w-md bg-white dark:bg-[#1a1a1e] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#2f2f3d] p-6 space-y-4">
                    <h3 className="font-bold text-lg">Edit Schedule</h3>
                    <div className="space-y-3">
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-400 uppercase">Title</label>
                        <input 
                          value={editData.title} 
                          onChange={e => setEditData({...editData, title: e.target.value})}
                          className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-sm"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-400 uppercase">Frequency</label>
                        <select 
                          value={editData.type} 
                          onChange={e => setEditData({...editData, type: e.target.value})}
                          className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-sm"
                        >
                          <option value="daily">Daily</option>
                          <option value="weekly">Weekly</option>
                          <option value="monthly">Monthly</option>
                        </select>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-400 uppercase">Email Recipient</label>
                        <input 
                          value={editData.email} 
                          onChange={e => setEditData({...editData, email: e.target.value})}
                          className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-sm"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                      <Button variant="ghost" onClick={() => setIsEditing(false)}>CANCEL</Button>
                      <Button onClick={handleUpdate} className="bg-indigo-600 text-white px-6 rounded-xl">SAVE CHANGES</Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Grid Layout for Code and Results */}
              <div className="grid grid-cols-1 gap-6">
                {/* Generated Script Toggle */}
                <div className="bg-white dark:bg-[#16161a] rounded-2xl border border-slate-200 dark:border-[#232329] overflow-hidden shadow-sm">
                  <div className="px-6 py-4 border-b border-slate-100 dark:border-white/5 flex items-center justify-between bg-slate-50/50 dark:bg-white/5">
                    <div className="flex items-center gap-2">
                      <Code className="w-4 h-4 text-indigo-500" />
                      <span className="text-xs font-bold uppercase tracking-wider">Automation Script</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => setShowScript(!showScript)}
                        className="h-8 px-3 text-[10px] font-bold gap-1.5 border-indigo-500/20 text-indigo-500"
                      >
                        {showScript ? "HIDE SCRIPT" : "VIEW SCRIPT"}
                      </Button>
                      {showScript && (
                        <>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleCopyCode(selectedSchedule.generated_script)}
                            className="h-8 px-3 text-[10px] font-bold gap-1.5"
                          >
                            {copySuccess ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                            {copySuccess || "COPY"}
                          </Button>
                          <Button variant="ghost" size="sm" className="h-8 px-3 text-[10px] font-bold gap-1.5">
                            <Download className="w-3.5 h-3.5" />
                            DOWNLOAD
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {showScript && (
                    <div className="p-0 bg-[#0d0d0f]">
                      <pre className="p-6 text-[13px] font-mono text-slate-300 overflow-x-auto leading-relaxed">
                        <code>{selectedSchedule.generated_script || "# No script generated yet."}</code>
                      </pre>
                    </div>
                  )}
                </div>

                {/* Last Run Results */}
                <div className="bg-white dark:bg-[#16161a] rounded-2xl border border-slate-200 dark:border-[#232329] overflow-hidden shadow-sm">
                  <div className="px-6 py-4 border-b border-slate-100 dark:border-white/5 flex items-center justify-between bg-slate-50/50 dark:bg-white/5">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      <span className="text-xs font-bold uppercase tracking-wider">Last Run Results</span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-bold">COMPLETED 2 HOURS AGO</span>
                  </div>
                  <div className="p-6">
                    {selectedSchedule.extracted_content ? (
                      <div className="prose dark:prose-invert max-w-none text-sm text-slate-600 dark:text-slate-300">
                        {selectedSchedule.extracted_content}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
                        <AlertCircle className="w-8 h-8 text-slate-300" />
                        <p className="text-xs text-slate-400">No results available yet. Run the schedule to see data.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-indigo-50 dark:bg-indigo-900/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                <Calendar className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold">Select a schedule to view details</h3>
              <p className="text-sm text-slate-400 max-w-xs mx-auto">
                Choose an automation from the sidebar to see its generated code, execution history, and results.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};