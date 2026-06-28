"use client";

import React, { useMemo, useState } from "react";
import {
  CheckCircle2,
  Circle,
  CircleDotDashed,
  CircleX,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
} from "lucide-react";
import { AnimatePresence, motion, Variants } from "framer-motion";
import { cn } from "../../../lib/utils";

export interface Subtask {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  tools?: string[];
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  level: number;
  dependencies: string[];
  subtasks: Subtask[];
  details?: string;
  token_usage?: {
    input: number;
    output: number;
    total: number;
    cost: number;
  };
}

interface PlanProps {
  tasks?: Task[];
  thoughts?: string[];
  onHide?: () => void;
}

const palette = {
  bg: "#05070A",
  surface: "#111827",
  border: "#232B36",
  primary: "#F8FAFC",
  secondary: "#CBD5E1",
  muted: "#64748B",
  success: "#10B981",
  active: "#22D3EE",
  warning: "#F59E0B",
  error: "#EF4444",
};

const isCompleted = (status?: string) => status === "completed";
const isRunning = (status?: string) => status === "in-progress" || status === "running";
const isFailed = (status?: string) => status === "failed";

export default function Plan({ tasks: propTasks = [], thoughts = [] }: PlanProps) {
  const [isWorkflowVisible, setIsWorkflowVisible] = useState(true);

  const activeTaskIndex = useMemo(() => {
    if (propTasks.length === 0) return -1;
    const runningIdx = propTasks.findIndex((t) => isRunning(t.status));
    if (runningIdx !== -1) return runningIdx;
    const firstPendingIdx = propTasks.findIndex((t) => !isCompleted(t.status));
    return firstPendingIdx === -1 ? -1 : firstPendingIdx;
  }, [propTasks]);

  const visibleTasks = useMemo(() => {
    if (activeTaskIndex === -1) return propTasks;
    return propTasks.filter((_, index) => index <= activeTaskIndex || isCompleted(propTasks[index]?.status));
  }, [propTasks, activeTaskIndex]);

  const activeTask = activeTaskIndex >= 0 ? propTasks[activeTaskIndex] : null;

  const activeSubtaskIndex = useMemo(() => {
    if (!activeTask) return -1;
    const subtasks = activeTask.subtasks || [];
    const runningIdx = subtasks.findIndex((s) => isRunning(s.status));
    if (runningIdx !== -1) return runningIdx;
    const firstPendingIdx = subtasks.findIndex((s) => !isCompleted(s.status));
    return firstPendingIdx === -1 ? subtasks.length - 1 : firstPendingIdx;
  }, [activeTask]);

  const currentBranchSubtasks = useMemo(() => {
    if (!activeTask) return [] as Subtask[];
    const list: Subtask[] = [];
    for (let i = 0; i < activeTask.subtasks.length; i += 1) {
      list.push(activeTask.subtasks[i]);
      if (!(isCompleted(activeTask.subtasks[i].status) || isRunning(activeTask.subtasks[i].status))) break;
    }
    return list;
  }, [activeTask]);

  const completedMainCount = useMemo(() => propTasks.filter((task) => isCompleted(task.status)).length, [propTasks]);
  const totalMainCount = propTasks.length;
  const overallProgress = totalMainCount > 0 ? Math.min(100, Math.round(((completedMainCount + (activeTask && !isCompleted(activeTask.status) ? 1 : 0)) / totalMainCount) * 100)) : 0;
  const currentSubtaskCompletedCount = useMemo(
    () => currentBranchSubtasks.filter((sub) => isCompleted(sub.status)).length,
    [currentBranchSubtasks]
  );

  const getStatusIcon = (status: string, active: boolean) => {
    if (isCompleted(status)) {
      return (
        <motion.div initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="relative">
          <CheckCircle2 className="h-5 w-5 text-[#10B981] drop-shadow-[0_0_12px_rgba(16,185,129,0.45)]" />
          <motion.div
            className="absolute inset-0 rounded-full bg-emerald-500/20 blur-sm"
            animate={{ scale: [1, 1.4, 1], opacity: [0.35, 0, 0.35] }}
            transition={{ duration: 2.2, repeat: Infinity }}
          />
        </motion.div>
      );
    }
    if (isRunning(status) || active) {
      return (
        <div className="relative">
          <CircleDotDashed className="h-5 w-5 text-[#22D3EE] animate-spin" />
          <motion.div
            className="absolute inset-[-2px] rounded-full border border-cyan-400/40"
            animate={{ opacity: [0.35, 1, 0.35], scale: [1, 1.14, 1] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        </div>
      );
    }
    if (isFailed(status)) return <CircleX className="h-5 w-5 text-[#EF4444]" />;
    return <Circle className="h-5 w-5 text-[#6B7280]" />;
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, x: -14, height: 0 },
    visible: (i: number) => ({
      opacity: 1,
      x: 0,
      height: "auto",
      transition: { delay: i * 0.08, type: "spring", stiffness: 120, damping: 18 },
    }),
    exit: (i: number) => ({
      opacity: 0,
      x: -14,
      height: 0,
      transition: { delay: (visibleTasks.length - i) * 0.03, duration: 0.18 },
    }),
  };

  const activeConnector = activeTask ? (isCompleted(activeTask.status) ? "#10B981" : "#22D3EE") : "#374151";

  return (
    <div className="relative w-full overflow-hidden rounded-[20px] border border-[#232B36] bg-[#05070A]/95 shadow-[0_20px_70px_rgba(0,0,0,0.48)] backdrop-blur-xl">
      <div className="pointer-events-none absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.11),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.08),transparent_26%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.06] bg-[linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-[size:28px_28px]" />

      <div className="relative z-10 flex items-center justify-between gap-3 border-b border-[#232B36] px-4 sm:px-5 py-3.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="h-2 w-2 rounded-full bg-[#22D3EE] shadow-[0_0_12px_rgba(34,211,238,0.6)]" />
          <span className="truncate text-[11px] sm:text-[13px] font-black uppercase tracking-[0.26em] text-[#F8FAFC]">Execution Trace</span>
        </div>
        <button
          onClick={() => setIsWorkflowVisible((v) => !v)}
          className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.22em] text-[#9CA3AF] transition-colors hover:text-[#F8FAFC]"
        >
          {isWorkflowVisible ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {isWorkflowVisible ? "Hide" : "Show Workflow"}
        </button>
      </div>

      <div className="relative z-10 px-3 sm:px-4 py-3 sm:py-4">
        <AnimatePresence mode="wait">
          {isWorkflowVisible && (
            <motion.div variants={containerVariants} initial="hidden" animate="visible" exit="exit" className="relative space-y-0">
              {visibleTasks.map((task, index) => {
                const isCurrent = index === activeTaskIndex;
                const isTaskCompleted = isCompleted(task.status);
                const shouldExpand = isCurrent || isTaskCompleted;

                return (
                  <motion.div key={task.id} custom={index} variants={itemVariants} className="relative">
                    {index < visibleTasks.length - 1 && (
                      <motion.div
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: 1 }}
                        transition={{ duration: 0.45, ease: "easeOut" }}
                        className="absolute left-[16px] sm:left-[18px] top-12 bottom-[-10px] w-px origin-top border-l border-dashed border-[#232B36]"
                        style={{ borderColor: isTaskCompleted ? "rgba(16,185,129,0.55)" : isCurrent ? "rgba(34,211,238,0.85)" : "#374151" }}
                      />
                    )}

                    <motion.div
                      whileHover={{ y: -2, scale: 1.004 }}
                      transition={{ duration: 0.18 }}
                      className={cn(
                        "relative overflow-hidden rounded-[18px] border backdrop-blur-md shadow-[0_12px_36px_rgba(0,0,0,0.22)]",
                        isCurrent
                          ? "border-[#22D3EE]/60 bg-gradient-to-r from-[#111827]/98 via-[#111827]/92 to-[#0f172a]/92"
                          : isTaskCompleted
                            ? "border-[#1F2937] bg-[#111827]/72"
                            : "border-[#232B36] bg-[#0B0F14]/76"
                      )}
                    >
                      <div className={cn("absolute left-0 top-0 h-full w-[3px]", isCurrent ? "bg-gradient-to-b from-[#22D3EE] to-[#10B981]" : isTaskCompleted ? "bg-gradient-to-b from-[#10B981] to-[#34D399]" : "bg-[#374151]")} />
                      <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-4 pl-4 sm:pl-5">
                        <div className="mt-0.5 shrink-0">{getStatusIcon(task.status, isCurrent)}</div>

                        <div className="min-w-0 flex-1 space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className={cn(
                                "inline-flex h-6 min-w-6 items-center justify-center rounded-full border px-2 text-[10px] font-black uppercase tracking-[0.18em]",
                                isCurrent ? "border-[#22D3EE]/50 bg-[#22D3EE]/10 text-[#22D3EE]" : "border-[#374151] bg-white/[0.03] text-[#9CA3AF]"
                              )}>
                                {index + 1}
                              </span>
                              <div className="min-w-0">
                                <h4 className={cn(
                                  "truncate text-[18px] font-semibold leading-tight tracking-tight",
                                  isCurrent ? "text-[#F8FAFC]" : isTaskCompleted ? "text-[#FFFFFF]" : "text-[#F8FAFC]/90"
                                )}>
                                  {task.title}
                                </h4>
                                {task.description && <p className="mt-0.5 line-clamp-1 text-[14px] leading-snug text-[#9CA3AF]">{task.description}</p>}
                              </div>
                            </div>

                            <div className="flex shrink-0 items-center gap-2">
                              <span className={cn(
                                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] font-semibold",
                                isTaskCompleted
                                  ? "border-emerald-500/20 bg-emerald-500/10 text-[#10B981]"
                                  : isCurrent
                                    ? "border-cyan-400/25 bg-cyan-400/10 text-[#22D3EE]"
                                    : "border-[#374151] bg-white/[0.03] text-[#9CA3AF]"
                              )}>
                                <span className={cn("h-2 w-2 rounded-full", isTaskCompleted ? "bg-[#10B981]" : isCurrent ? "bg-[#22D3EE] animate-pulse" : "bg-[#6B7280]")} />
                                {isTaskCompleted ? "Completed" : isCurrent ? "Current" : "Pending"}
                              </span>
                              {isTaskCompleted && <CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5 text-[#10B981] drop-shadow-[0_0_8px_rgba(16,185,129,0.35)]" />}
                            </div>
                          </div>

                          <AnimatePresence>
                            {shouldExpand && (
                              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden pt-1.5 space-y-1.5 sm:space-y-2">
                                {task.subtasks.map((sub, sIdx) => {
                                  const subCompleted = isCompleted(sub.status);
                                  const subRunning = isRunning(sub.status);
                                  const shouldReveal = sIdx <= activeSubtaskIndex || subCompleted || subRunning;
                                  const subCurrent = sIdx === activeSubtaskIndex && shouldReveal && !subCompleted;
                                  if (!shouldReveal) return null;

                                  return (
                                    <motion.div
                                      key={sub.id}
                                      initial={{ opacity: 0, x: -12, y: 4 }}
                                      animate={{ opacity: 1, x: 0, y: 0 }}
                                      transition={{ duration: 0.32, delay: sIdx * 0.06 }}
                                      className="relative flex items-start gap-2 sm:gap-3 pl-6 sm:pl-7"
                                    >
                                      <div className="absolute left-[6px] sm:left-[8px] top-[-6px] bottom-[-6px] w-0.5">
                                        <div className={cn("absolute left-0 top-0 h-full w-px border-l border-dashed", subCompleted ? "border-[#10B981]/70" : subCurrent ? "border-[#22D3EE]/80" : "border-[#374151]")} />
                                        <div className={cn("absolute left-0 top-[12px] h-px w-4 sm:w-5 border-t border-dashed", subCompleted ? "border-[#10B981]/70" : subCurrent ? "border-[#22D3EE]/80" : "border-[#374151]")} />
                                      </div>

                                      <div className="mt-[1px] shrink-0">
                                        {subCompleted ? (
                                          <CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5 text-[#10B981] drop-shadow-[0_0_8px_rgba(16,185,129,0.35)]" />
                                        ) : subRunning ? (
                                          <div className="relative">
                                            <CircleDotDashed className="h-4 w-4 sm:h-5 sm:w-5 text-[#22D3EE] animate-spin" />
                                            <motion.div className="absolute inset-0 rounded-full border border-cyan-400/40" animate={{ opacity: [0.4, 1, 0.4], scale: [1, 1.18, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                                          </div>
                                        ) : subCurrent ? (
                                          <div className="relative">
                                            <Circle className="h-4 w-4 sm:h-5 sm:w-5 text-[#22D3EE]" />
                                            <motion.div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-sm" animate={{ scale: [1, 1.4, 1], opacity: [0.35, 0, 0.35] }} transition={{ duration: 1.8, repeat: Infinity }} />
                                          </div>
                                        ) : (
                                          <Circle className="h-4 w-4 sm:h-5 sm:w-5 text-[#6B7280]" />
                                        )}
                                      </div>

                                      <div className="min-w-0 flex flex-col pt-0.5">
                                        <span className={cn("truncate text-[16px] font-medium", subCompleted ? "text-[#E5E7EB]" : subCurrent ? "text-[#FFFFFF]" : "text-[#D1D5DB]")}>{sub.title}</span>
                                        <span className="max-w-[44rem] text-[14px] leading-snug text-[#9CA3AF]">{sub.description}</span>
                                      </div>
                                    </motion.div>
                                  );
                                })}

                                {isCurrent && thoughts.length > 0 && (
                                  <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-3 rounded-[14px] border border-[#1F2937] bg-white/[0.03] px-3 py-3">
                                    <div className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.22em] text-[#22D3EE]">
                                      <Sparkles className="h-3.5 w-3.5" />
                                      AI Reasoning
                                    </div>
                                    <div className="space-y-2">
                                      {thoughts.map((thought, tIdx) => (
                                        <p key={tIdx} className="text-[13px] leading-relaxed italic text-[#CBD5E1]">{thought}</p>
                                      ))}
                                    </div>
                                  </motion.div>
                                )}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </div>
                    </motion.div>
                  </motion.div>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="relative z-10 px-3 sm:px-4 pb-3 sm:pb-4">
        <div className="grid grid-cols-4 gap-2 sm:gap-3 rounded-[16px] border border-[#232B36] bg-[#0B0F14]/85 px-3 py-3">
          <div className="col-span-4 sm:col-span-1 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[#22D3EE]/25 bg-cyan-400/10 shadow-[0_0_20px_rgba(34,211,238,0.08)]">
              <Loader2 className="h-4 w-4 animate-pulse text-[#22D3EE]" />
            </div>
            <div className="min-w-0">
              <div className="text-[10px] font-black uppercase tracking-[0.2em] text-[#9CA3AF]">Current Progress</div>
              <div className="text-[14px] font-semibold text-[#F8FAFC]">{Math.min(totalMainCount, completedMainCount + (activeTask ? 1 : 0))} / {totalMainCount} steps completed</div>
            </div>
          </div>

          <div className="col-span-4 sm:col-span-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#232B36]">
              <motion.div initial={{ width: 0 }} animate={{ width: `${overallProgress}%` }} transition={{ duration: 0.5, ease: "easeOut" }} className="h-full rounded-full bg-gradient-to-r from-[#10B981] via-[#22D3EE] to-[#10B981] shadow-[0_0_12px_rgba(34,211,238,0.25)]" />
            </div>
            <div className="w-10 text-right text-[11px] font-semibold text-[#9CA3AF]">{overallProgress}%</div>
          </div>

          <div className="col-span-2 sm:col-span-1 flex items-center justify-between gap-2 rounded-[14px] border border-[#232B36] bg-white/[0.02] px-3 py-2">
            <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
            <span className="text-[11px] font-medium text-[#E5E7EB]">Completed</span>
            <span className="text-[13px] font-semibold text-[#F8FAFC]">{completedMainCount}</span>
          </div>

          <div className="col-span-2 sm:col-span-1 flex items-center justify-between gap-2 rounded-[14px] border border-[#232B36] bg-white/[0.02] px-3 py-2">
            <CircleDotDashed className="h-4 w-4 text-[#22D3EE]" />
            <span className="text-[11px] font-medium text-[#E5E7EB]">In Progress</span>
            <span className="text-[13px] font-semibold text-[#F8FAFC]">{activeTask && isRunning(activeTask.status) ? 1 : 0}</span>
          </div>

          <div className="col-span-2 sm:col-span-1 flex items-center justify-between gap-2 rounded-[14px] border border-[#232B36] bg-white/[0.02] px-3 py-2">
            <Circle className="h-4 w-4 text-[#6B7280]" />
            <span className="text-[11px] font-medium text-[#E5E7EB]">Pending</span>
            <span className="text-[13px] font-semibold text-[#F8FAFC]">{Math.max(0, totalMainCount - completedMainCount - (activeTask && !isCompleted(activeTask.status) ? 1 : 0))}</span>
          </div>

          <div className="col-span-2 sm:col-span-1 flex items-center justify-between gap-2 rounded-[14px] border border-[#232B36] bg-white/[0.02] px-3 py-2">
            <CircleX className="h-4 w-4 text-[#EF4444]" />
            <span className="text-[11px] font-medium text-[#E5E7EB]">Failed</span>
            <span className="text-[13px] font-semibold text-[#F8FAFC]">{propTasks.filter((t) => isFailed(t.status)).length}</span>
          </div>

          <div className="col-span-4 flex items-center justify-between rounded-[14px] border border-[#232B36] bg-white/[0.02] px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#22D3EE]" />
              <span className="text-[11px] font-semibold text-[#9CA3AF]">Subtasks in current branch</span>
            </div>
            <span className="text-[12px] font-semibold text-[#F8FAFC]">{currentSubtaskCompletedCount} / {currentBranchSubtasks.length}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
