"use client";

import React, { useMemo, useState, useEffect, useRef, useCallback } from "react";
import {
  CheckCircle2,
  Circle,
  CircleDotDashed,
  CircleX,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Clock,
  ListChecks,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
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
  isAiTyping?: boolean;
}

const isCompleted = (status?: string) => status === "completed";
const isRunning = (status?: string) => status === "in-progress" || status === "running";
const isFailed = (status?: string) => status === "failed";

function formatElapsed(sec: number) {
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

export default function Plan({ tasks: propTasks = [], thoughts = [], isAiTyping }: PlanProps) {
  const [isWorkflowVisible, setIsWorkflowVisible] = useState(true);
  const [showSummary, setShowSummary] = useState(false);
  const [showFullHistory, setShowFullHistory] = useState(false);
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(new Set());
  const prevAiTyping = useRef<boolean | undefined>(undefined);
  const startedAt = useRef<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const finalElapsed = useRef(0);

  useEffect(() => {
    if (isAiTyping && startedAt.current === null) {
      startedAt.current = Date.now();
    }
  }, [isAiTyping]);

  useEffect(() => {
    if (!isAiTyping || !startedAt.current) return;
    const t = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt.current!) / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, [isAiTyping]);

  useEffect(() => {
    if (prevAiTyping.current === true && isAiTyping === false) {
      finalElapsed.current = startedAt.current
        ? Math.floor((Date.now() - startedAt.current) / 1000)
        : 0;
      const allDone =
        propTasks.length > 0 &&
        propTasks.every((t) => isCompleted(t.status) || isFailed(t.status));
      if (allDone) {
        setShowSummary(true);
        setIsWorkflowVisible(true);
      } else {
        setIsWorkflowVisible(false);
      }
    }
    prevAiTyping.current = isAiTyping;
  }, [isAiTyping, propTasks]);

  const activeTaskIndex = useMemo(() => {
    if (propTasks.length === 0) return -1;
    const runningIdx = propTasks.findIndex((t) => isRunning(t.status));
    if (runningIdx !== -1) return runningIdx;
    const firstPendingIdx = propTasks.findIndex((t) => !isCompleted(t.status));
    return firstPendingIdx === -1 ? -1 : firstPendingIdx;
  }, [propTasks]);

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
    for (let i = 0; i < activeTask.subtasks.length; i++) {
      list.push(activeTask.subtasks[i]);
      if (!(isCompleted(activeTask.subtasks[i].status) || isRunning(activeTask.subtasks[i].status)))
        break;
    }
    return list;
  }, [activeTask]);

  const completedMainCount = useMemo(
    () => propTasks.filter((t) => isCompleted(t.status)).length,
    [propTasks]
  );
  const failedMainCount = useMemo(
    () => propTasks.filter((t) => isFailed(t.status)).length,
    [propTasks]
  );
  const totalMainCount = propTasks.length;
  const runningCount = activeTask && isRunning(activeTask.status) ? 1 : 0;
  const pendingCount = Math.max(
    0,
    totalMainCount -
      completedMainCount -
      failedMainCount -
      (activeTask && !isCompleted(activeTask.status) && !isFailed(activeTask.status) ? 1 : 0)
  );
  const overallProgress =
    totalMainCount > 0
      ? Math.min(
          100,
          Math.round(
            ((completedMainCount +
              (activeTask && !isCompleted(activeTask.status) ? 0.5 : 0)) /
              totalMainCount) *
              100
          )
        )
      : 0;
  const currentSubtaskCompletedCount = useMemo(
    () => currentBranchSubtasks.filter((s) => isCompleted(s.status)).length,
    [currentBranchSubtasks]
  );

  const toggleTaskExpand = useCallback((id: string) => {
    setExpandedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const renderSubtasks = (task: Task, isCurrent: boolean) => {
    const subtasksToShow = isCurrent
      ? task.subtasks.filter(
          (_, sIdx) =>
            sIdx <= activeSubtaskIndex ||
            isCompleted(task.subtasks[sIdx]?.status) ||
            isRunning(task.subtasks[sIdx]?.status)
        )
      : task.subtasks;

    return (
      <div className="space-y-0.5">
        {task.description && (
          <p className="mb-1.5 text-[10px] leading-snug text-[#374151]">{task.description}</p>
        )}
        {subtasksToShow.map((sub, sIdx) => {
          const subCompleted = isCompleted(sub.status);
          const subRunning = isRunning(sub.status);
          const realIdx = isCurrent ? task.subtasks.indexOf(sub) : sIdx;
          const subCurrent = isCurrent && realIdx === activeSubtaskIndex && !subCompleted;
          return (
            <motion.div
              key={sub.id}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: sIdx * 0.03, duration: 0.15 }}
              className="flex items-start gap-1.5 pl-2"
            >
              <div className="mt-[3px] shrink-0">
                {subCompleted ? (
                  <CheckCircle2 className="h-3 w-3 text-[#10B981]" />
                ) : subRunning || subCurrent ? (
                  <CircleDotDashed className="h-3 w-3 text-[#22D3EE] animate-spin" />
                ) : (
                  <Circle className="h-3 w-3 text-[#2D3748]" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <span
                  className={cn(
                    "text-[11px] leading-snug",
                    subCompleted
                      ? "text-[#374151]"
                      : subCurrent
                      ? "font-medium text-[#E2E8F0]"
                      : "text-[#4B5563]"
                  )}
                >
                  {sub.title}
                </span>
                {sub.description && !subCompleted && (
                  <p className="mt-0.5 text-[10px] leading-snug text-[#2D3748]">{sub.description}</p>
                )}
              </div>
            </motion.div>
          );
        })}

        {isCurrent && thoughts.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 rounded-[8px] border border-[#0f1e2d] bg-cyan-950/20 px-2.5 py-2"
          >
            <div className="mb-1 flex items-center gap-1.5 text-[9px] font-black uppercase tracking-[0.18em] text-[#22D3EE]/70">
              <Sparkles className="h-2.5 w-2.5" />
              AI Reasoning
            </div>
            {thoughts.map((thought, tIdx) => (
              <p key={tIdx} className="text-[10px] leading-relaxed italic text-[#4B5563]">
                {thought}
              </p>
            ))}
          </motion.div>
        )}
      </div>
    );
  };

  const renderTaskList = (tasks: Task[]) => (
    <div className="space-y-[3px]">
      {tasks.map((task, index) => {
        const isCurrent = index === activeTaskIndex;
        const isTaskCompleted = isCompleted(task.status);
        const isTaskFailed = isFailed(task.status);
        const isManuallyExpanded = expandedTaskIds.has(task.id);
        const isExpanded = isCurrent || isManuallyExpanded;
        const isCollapsible = isTaskCompleted || isTaskFailed;

        return (
          <motion.div
            key={task.id}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.03, duration: 0.18 }}
            className={cn(
              "relative overflow-hidden rounded-[9px] border",
              isCurrent
                ? "border-[#22D3EE]/20 bg-[#050d18]"
                : isTaskCompleted
                ? "border-[#0f1f10]/60 bg-[#040807]"
                : isTaskFailed
                ? "border-[#200f0f]/60 bg-[#070404]"
                : "border-[#0d1522]/60 bg-[#040609]"
            )}
          >
            <div
              className={cn(
                "absolute left-0 top-0 h-full w-[2px]",
                isCurrent
                  ? "bg-gradient-to-b from-[#22D3EE] to-[#10B981]"
                  : isTaskCompleted
                  ? "bg-[#10B981]/30"
                  : isTaskFailed
                  ? "bg-[#EF4444]/30"
                  : "bg-[#1a2535]/50"
              )}
            />

            <div
              className={cn(
                "flex items-center gap-2 px-2.5 py-[7px]",
                isCollapsible && "cursor-pointer select-none"
              )}
              onClick={isCollapsible ? () => toggleTaskExpand(task.id) : undefined}
            >
              <div className="shrink-0">
                {isTaskCompleted ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-[#10B981]/80" />
                ) : isTaskFailed ? (
                  <CircleX className="h-3.5 w-3.5 text-[#EF4444]/80" />
                ) : isCurrent ? (
                  <CircleDotDashed className="h-3.5 w-3.5 text-[#22D3EE] animate-spin" />
                ) : (
                  <Circle className="h-3.5 w-3.5 text-[#1e2a38]" />
                )}
              </div>

              <span
                className={cn(
                  "shrink-0 inline-flex h-[18px] w-[18px] items-center justify-center rounded-full text-[9px] font-bold",
                  isCurrent ? "bg-[#22D3EE]/10 text-[#22D3EE]" : "bg-white/[0.03] text-[#374151]"
                )}
              >
                {index + 1}
              </span>

              <span
                className={cn(
                  "min-w-0 flex-1 truncate text-[12px] font-medium leading-none",
                  isCurrent
                    ? "text-[#CBD5E1]"
                    : isTaskCompleted
                    ? "text-[#374151] line-through decoration-[#1e2535]"
                    : isTaskFailed
                    ? "text-[#5a2020]"
                    : "text-[#64748B]"
                )}
              >
                {task.title}
              </span>

              <div className="flex shrink-0 items-center gap-1.5">
                <span
                  className={cn(
                    "hidden sm:inline-flex items-center rounded-full px-1.5 py-[2px] text-[9px] font-semibold border",
                    isTaskCompleted
                      ? "border-emerald-900/30 bg-emerald-950/40 text-emerald-600"
                      : isCurrent
                      ? "border-cyan-900/30 bg-cyan-950/40 text-cyan-500"
                      : isTaskFailed
                      ? "border-red-900/30 bg-red-950/40 text-red-600"
                      : "border-[#1a2535]/60 bg-transparent text-[#2D3748]"
                  )}
                >
                  {isTaskCompleted
                    ? "Done"
                    : isCurrent
                    ? "Running"
                    : isTaskFailed
                    ? "Failed"
                    : "Pending"}
                </span>
                {isCollapsible && (
                  <ChevronDown
                    className={cn(
                      "h-3 w-3 text-[#2D3748] transition-transform duration-200",
                      isManuallyExpanded && "rotate-180"
                    )}
                  />
                )}
              </div>
            </div>

            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.16 }}
                  className="overflow-hidden"
                >
                  <div className="border-t border-[#080e18]/70 px-3 pt-2 pb-2.5">
                    {renderSubtasks(task, isCurrent)}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </div>
  );

  const renderStatusBar = () => (
    <div className="flex items-center gap-2 border-t border-[#080e18]/70 px-3 py-1.5">
      <div className="flex shrink-0 items-center gap-1.5 text-[10px]">
        <span className="flex items-center gap-[3px] text-emerald-600">
          <CheckCircle2 className="h-2.5 w-2.5" />
          {completedMainCount}
        </span>
        {runningCount > 0 && (
          <>
            <span className="text-[#151e2a]">·</span>
            <span className="flex items-center gap-[3px] text-cyan-600">
              <CircleDotDashed className="h-2.5 w-2.5 animate-spin" />
              {runningCount}
            </span>
          </>
        )}
        {pendingCount > 0 && (
          <>
            <span className="text-[#151e2a]">·</span>
            <span className="flex items-center gap-[3px] text-[#2D3748]">
              <Circle className="h-2.5 w-2.5" />
              {pendingCount}
            </span>
          </>
        )}
        {failedMainCount > 0 && (
          <>
            <span className="text-[#151e2a]">·</span>
            <span className="flex items-center gap-[3px] text-red-700">
              <CircleX className="h-2.5 w-2.5" />
              {failedMainCount}
            </span>
          </>
        )}
      </div>
      <div className="h-[2px] flex-1 overflow-hidden rounded-full bg-[#080e18]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${overallProgress}%` }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="h-full rounded-full bg-gradient-to-r from-[#10B981] to-[#22D3EE]"
        />
      </div>
      <span className="shrink-0 text-[10px] font-semibold text-[#2D3748]">{overallProgress}%</span>
      {isAiTyping && startedAt.current && (
        <span className="shrink-0 flex items-center gap-[3px] text-[10px] text-[#1e2a38]">
          <Clock className="h-2.5 w-2.5" />
          {formatElapsed(elapsedSec)}
        </span>
      )}
    </div>
  );

  const renderSummaryCard = () => {
    const allSuccess = failedMainCount === 0;
    return (
      <div className="px-2.5 pb-2.5 pt-2 space-y-1.5">
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className={cn(
            "rounded-[9px] border p-2.5",
            allSuccess
              ? "border-emerald-900/30 bg-emerald-950/20"
              : "border-amber-900/30 bg-amber-950/15"
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <CheckCircle2
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  allSuccess ? "text-emerald-500" : "text-amber-500"
                )}
              />
              <div className="min-w-0">
                <div
                  className={cn(
                    "text-[11px] font-semibold leading-none",
                    allSuccess ? "text-emerald-500" : "text-amber-500"
                  )}
                >
                  Workflow {allSuccess ? "Completed" : "Finished with errors"}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0 text-[10px] text-[#2D3748]">
                  <span>{completedMainCount}/{totalMainCount} tasks</span>
                  {finalElapsed.current > 0 && (
                    <span className="flex items-center gap-[3px]">
                      <Clock className="h-2 w-2" />
                      {formatElapsed(finalElapsed.current)}
                    </span>
                  )}
                  {failedMainCount > 0 && (
                    <span className="text-red-700">{failedMainCount} failed</span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={() => setShowFullHistory((v) => !v)}
              className="flex shrink-0 items-center gap-1 rounded-[6px] border border-[#0f1a28] bg-white/[0.02] px-2 py-1 text-[10px] font-semibold text-[#374151] transition-all hover:border-[#1a2a3a] hover:text-[#64748B]"
            >
              <ListChecks className="h-3 w-3" />
              <span className="hidden sm:inline">
                {showFullHistory ? "Hide" : "View Execution"}
              </span>
              <ChevronDown
                className={cn(
                  "h-2.5 w-2.5 transition-transform duration-200",
                  showFullHistory && "rotate-180"
                )}
              />
            </button>
          </div>

          <div className="mt-2 h-[2px] overflow-hidden rounded-full bg-[#080e18]">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                allSuccess
                  ? "bg-gradient-to-r from-[#10B981] to-[#22D3EE]"
                  : "bg-gradient-to-r from-[#F59E0B] to-[#EF4444]"
              )}
              style={{ width: `${Math.round((completedMainCount / totalMainCount) * 100)}%` }}
            />
          </div>
        </motion.div>

        <AnimatePresence>
          {showFullHistory && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {renderTaskList(propTasks)}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  };

  return (
    <div className="relative w-full overflow-hidden rounded-[12px] border border-[#0d1520] bg-[#020408]/98 shadow-[0_8px_32px_rgba(0,0,0,0.55)] backdrop-blur-xl">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_0%,rgba(34,211,238,0.06),transparent_45%)] opacity-100" />

      <div className="relative z-10 flex items-center justify-between gap-2 border-b border-[#080e18] px-3 py-2">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-1.5 w-1.5 rounded-full transition-colors duration-300",
              isAiTyping
                ? "animate-pulse bg-[#22D3EE] shadow-[0_0_6px_rgba(34,211,238,0.8)]"
                : showSummary && failedMainCount === 0
                ? "bg-[#10B981] shadow-[0_0_5px_rgba(16,185,129,0.6)]"
                : showSummary
                ? "bg-[#F59E0B] shadow-[0_0_5px_rgba(245,158,11,0.5)]"
                : "bg-[#1e2a38]"
            )}
          />
          <span className="text-[10px] font-black uppercase tracking-[0.22em] text-[#475569]">
            Execution Trace
          </span>
          {totalMainCount > 0 && !showSummary && (
            <span className="text-[9px] text-[#1e2a38]">
              {totalMainCount}
            </span>
          )}
        </div>
        <button
          onClick={() => setIsWorkflowVisible((v) => !v)}
          className="flex items-center gap-[3px] text-[9px] font-bold uppercase tracking-[0.16em] text-[#1e2a38] transition-colors hover:text-[#374151]"
        >
          {isWorkflowVisible ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
          {isWorkflowVisible ? "Hide" : showSummary ? "Show" : "Show Workflow"}
        </button>
      </div>

      <AnimatePresence>
        {isWorkflowVisible && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            {showSummary ? (
              renderSummaryCard()
            ) : (
              <>
                {propTasks.length > 0 && (
                  <div className="px-2.5 pt-2.5 pb-1">
                    {renderTaskList(propTasks)}
                  </div>
                )}
                {totalMainCount > 0 && renderStatusBar()}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
