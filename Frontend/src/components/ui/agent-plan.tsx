"use client";

import React, { useMemo, useState, useEffect, useRef } from "react";
import {
  CheckCircle2,
  Circle,
  CircleDotDashed,
  CircleX,
  ChevronDown,
  ChevronUp,
  Zap,
  Brain,
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
  thought?: string;
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
  taskThoughts?: Record<string, string>;
  onHide?: () => void;
  isAiTyping?: boolean;
}

const isCompleted = (status?: string) => status === "completed";
const isRunning   = (status?: string) => status === "in-progress" || status === "running";
const isFailed    = (status?: string) => status === "failed";

export default function Plan({
  tasks: propTasks = [],
  thoughts = [],
  taskThoughts = {},
  isAiTyping,
}: PlanProps) {
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});
  const [manualToggle, setManualToggle]   = useState<Record<string, boolean>>({});
  const prevStatuses = useRef<Record<string, string>>({});


  const activeTask = useMemo(() => {
    const running = propTasks.find((t) => isRunning(t.status));
    if (running) return running;
    const pending = propTasks.find((t) => !isCompleted(t.status) && !isFailed(t.status));
    return pending ?? null;
  }, [propTasks]);

  const activeTaskId = activeTask?.id ?? null;

  useEffect(() => {
    propTasks.forEach((task) => {
      const prev = prevStatuses.current[task.id];
      const curr = task.status;

      if (prev === curr) return;
      prevStatuses.current[task.id] = curr;

      if (!manualToggle[task.id]) {
        if (isRunning(curr)) {
          setExpandedTasks((e) => ({ ...e, [task.id]: true }));
        } else if (isCompleted(curr)) {
          const timer = setTimeout(() => {
            setExpandedTasks((e) => {
              if (manualToggle[task.id]) return e;
              return { ...e, [task.id]: false };
            });
          }, 1800);
          return () => clearTimeout(timer);
        }
      }
    });
  }, [propTasks]);

  const toggleTask = (id: string) => {
    setManualToggle((m) => ({ ...m, [id]: true }));
    setExpandedTasks((e) => ({ ...e, [id]: !e[id] }));
  };

  const completedCount = propTasks.filter((t) => isCompleted(t.status)).length;
  const totalCount     = propTasks.length;
  const progress       = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  const activeTaskIdx = activeTask ? propTasks.indexOf(activeTask) : -1;
  const anyRunning = propTasks.some((t) => isRunning(t.status));

  const getStatusIcon = (status: string, isActive: boolean) => {
    if (isCompleted(status))
      return (
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 20 }}>
          <CheckCircle2 className="h-[18px] w-[18px] text-emerald-400" />
        </motion.div>
      );
    if (isRunning(status) || isActive)
      return <CircleDotDashed className="h-[18px] w-[18px] text-sky-400 animate-spin" />;
    if (isFailed(status))
      return <CircleX className="h-[18px] w-[18px] text-red-400" />;
    return <Circle className="h-[18px] w-[18px] text-slate-600" />;
  };

  const statusColor = (status: string, isActive: boolean) => {
    if (isCompleted(status)) return "text-emerald-400";
    if (isRunning(status) || isActive) return "text-sky-400";
    if (isFailed(status)) return "text-red-400";
    return "text-slate-500";
  };

  const statusLabel = (status: string, isActive: boolean) => {
    if (isCompleted(status)) return "Done";
    if (isRunning(status) || isActive) return "Running";
    if (isFailed(status)) return "Failed";
    return "Waiting";
  };

  const parseThoughtInline = (text: string) => {
    // Unescape markdown characters like \* -> *, \_ -> _, \` -> `
    let cleanText = text.replace(/\\([*_`~#|])/g, "$1");

    // 1. Bold text (**text**)
    const boldParts = cleanText.split(/(\*\*.*?\*\*)/g);
    return boldParts.map((bPart, bIdx) => {
      if (bPart.startsWith("**") && bPart.endsWith("**")) {
        return <strong key={bIdx} className="font-bold text-foreground dark:text-gray-200">{bPart.slice(2, -2)}</strong>;
      }
      
      // 2. Italic text (*text*)
      const italicParts = bPart.split(/(\*.*?\*)/g);
      return italicParts.map((tPart, tIdx) => {
        if (tPart.startsWith("*") && tPart.endsWith("*")) {
          return <em key={tIdx} className="italic text-foreground/80">{tPart.slice(1, -1)}</em>;
        }

        // 3. Inline code (`code`)
        const codeParts = tPart.split(/(\`.*?\`)/g);
        return codeParts.map((cPart, cIdx) => {
          if (cPart.startsWith("`") && cPart.endsWith("`")) {
            return (
              <code key={cIdx} className="px-1.5 py-0.5 mx-0.5 rounded font-mono text-[11px] font-semibold bg-indigo-500/10 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400 border border-indigo-500/5 dark:border-indigo-500/10">
                {cPart.slice(1, -1)}
              </code>
            );
          }
          
          // 4. Links ([text](url))
          const linkParts = cPart.split(/(\[.*?\]\(.*?\))/g);
          return linkParts.map((lPart, lIdx) => {
            const match = lPart.match(/\[(.*?)\]\((.*?)\)/);
            if (match) {
              return (
                <a key={lIdx} href={match[2]} target="_blank" rel="noreferrer" className="text-sky-500 dark:text-sky-400 underline hover:text-sky-400">
                  {match[1]}
                </a>
              );
            }
            return lPart;
          });
        });
      });
    });
  };

  const renderThoughtBlocks = (content: string) => {
    if (!content) return null;
    
    const lines = content.split("\n");
    const blocks: React.ReactNode[] = [];
    let currentTableRows: string[][] = [];
    let inTable = false;
    
    const pushTable = (key: number) => {
      if (currentTableRows.length === 0) return;
      
      const isSepRow = (row: string[]) => row.every(cell => /^:?-+:?$/.test(cell.trim()));
      const cleanedRows = currentTableRows.filter(row => !isSepRow(row));
      
      if (cleanedRows.length > 0) {
        const header = cleanedRows[0];
        const body = cleanedRows.slice(1);
        
        blocks.push(
          <div key={`table-${key}`} className="my-2.5 overflow-hidden rounded-lg border border-border bg-card/50 shadow-sm max-w-full">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[11px] border-collapse">
                <thead>
                  <tr className="bg-muted/30 border-b border-border/80">
                    {header.map((h, i) => (
                      <th key={i} className="px-3 py-2 font-bold text-muted-foreground uppercase tracking-wider">
                        {parseThoughtInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, ri) => (
                    <tr key={ri} className="border-b border-border/30 last:border-0 hover:bg-muted/15">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-2 text-foreground/80 align-middle">
                          {parseThoughtInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      }
      currentTableRows = [];
      inTable = false;
    };
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      
      // 1. Headings (###, ##, #)
      if (trimmed.startsWith("### ")) {
        blocks.push(
          <h4 key={i} className="text-[12px] font-bold text-foreground mt-3 mb-1 uppercase tracking-wider text-indigo-500/90 dark:text-indigo-400/95">
            {parseThoughtInline(trimmed.slice(4))}
          </h4>
        );
        continue;
      }
      if (trimmed.startsWith("## ")) {
        blocks.push(
          <h3 key={i} className="text-[13px] font-bold text-foreground mt-3.5 mb-1.5 uppercase tracking-wide text-indigo-500 dark:text-indigo-400">
            {parseThoughtInline(trimmed.slice(3))}
          </h3>
        );
        continue;
      }
      if (trimmed.startsWith("# ")) {
        blocks.push(
          <h2 key={i} className="text-[14px] font-black text-foreground mt-4 mb-2 tracking-tight">
            {parseThoughtInline(trimmed.slice(2))}
          </h2>
        );
        continue;
      }

      // 2. Tables
      if (trimmed.startsWith("|")) {
        inTable = true;
        const cells = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        currentTableRows.push(cells);
        continue;
      }
      
      if (inTable && !trimmed.startsWith("|")) {
        pushTable(i);
      }
      
      if (!trimmed) continue;
      
      // 3. Bullet list items (supporting -, *, ., •)
      if (
        trimmed.startsWith("- ") ||
        trimmed.startsWith("* ") ||
        trimmed.startsWith(". ") ||
        trimmed.startsWith("• ")
      ) {
        blocks.push(
          <div key={i} className="flex items-start gap-2 text-xs text-foreground/80 leading-relaxed pl-2 py-0.5">
            <span className="text-indigo-400 mt-1 shrink-0">•</span>
            <span>{parseThoughtInline(trimmed.slice(2))}</span>
          </div>
        );
        continue;
      }
      
      // 4. Regular paragraph
      blocks.push(
        <p key={i} className="text-xs text-foreground/85 leading-relaxed py-0.5">
          {parseThoughtInline(line)}
        </p>
      );
    }
    
    if (inTable) {
      pushTable(lines.length);
    }
    
    return <div className="space-y-1">{blocks}</div>;
  };

  return (
    <div className="w-full rounded-2xl border border-border bg-card shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-muted/20">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-400" />
          </span>
          <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-foreground/70">Agent Plan</span>
          <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
            {completedCount}/{totalCount}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 w-32">
            <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            </div>
            <span className="text-[10px] font-bold text-muted-foreground tabular-nums">{progress}%</span>
          </div>
        </div>
      </div>

      {/* Active stage indicator — shown only while a task is running */}
      <AnimatePresence>
        {anyRunning && activeTask && (
          <motion.div
            key="stage-indicator"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="flex items-center gap-2.5 px-5 py-2 bg-sky-500/[0.07] border-b border-sky-500/10">
              <Zap className="h-3 w-3 text-sky-400 shrink-0" />
              <span className="text-[11px] text-sky-400/70 font-medium truncate">
                <span className="font-bold text-sky-400">
                  Step {String(activeTaskIdx + 1).padStart(2, "0")}
                </span>
                <span className="mx-1.5 text-sky-400/40">·</span>
                {activeTask.title}
              </span>
              <span className="ml-auto flex h-1.5 w-1.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-1.5 w-1.5 rounded-full bg-sky-400 opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-sky-400" />
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tasks */}
      <div className="px-4 py-3 space-y-2">
        <AnimatePresence initial={false}>
          {propTasks.map((task, idx) => {
            const isActive   = task.id === activeTaskId;
            const isExpanded = expandedTasks[task.id] ?? isActive;
            const hasSubs    = task.subtasks && task.subtasks.length > 0;

            const activeSubIdx = isActive
              ? (() => {
                  const ri = task.subtasks.findIndex((s) => isRunning(s.status));
                  if (ri !== -1) return ri;
                  const pi = task.subtasks.findIndex((s) => !isCompleted(s.status));
                  return pi === -1 ? task.subtasks.length - 1 : pi;
                })()
              : -1;

            return (
              <motion.div
                key={task.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22 }}
                className={cn(
                  "rounded-xl border overflow-hidden transition-all duration-200",
                  isActive
                    ? "border-sky-500 bg-sky-500/10 shadow-[0_0_15px_rgba(56,189,248,0.12)] ring-1 ring-sky-500/20"
                    : isCompleted(task.status)
                    ? "border-emerald-500/15 bg-card dark:bg-emerald-950/[0.02] shadow-sm"
                    : isFailed(task.status)
                    ? "border-red-500/20 bg-red-500/[0.03]"
                    : "border-border bg-transparent"
                )}
              >
                {/* Task Row — clickable header */}
                <button
                  onClick={() => toggleTask(task.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/10 transition-colors group"
                >
                  <div className="shrink-0">{getStatusIcon(task.status, isActive)}</div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-bold text-muted-foreground tabular-nums">{String(idx + 1).padStart(2, "0")}</span>
                      <span className={cn(
                        "text-[14px] font-semibold leading-snug transition-colors",
                        isCompleted(task.status) ? "text-foreground/80 font-semibold" : isActive ? "text-sky-400 font-bold" : "text-foreground/75"
                      )}>
                        {task.title}
                      </span>
                    </div>
                    {task.description && !isExpanded && (
                      <p className="mt-0.5 text-[12px] text-muted-foreground line-clamp-1">{task.description}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {(() => {
                      const label = statusLabel(task.status, isActive);
                      if (label === "Running") {
                        return (
                          <span className="bg-sky-500/15 text-sky-400 border border-sky-500/25 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider animate-pulse flex items-center gap-1 shrink-0">
                            <span className="w-1 h-1 rounded-full bg-sky-400 animate-ping shrink-0" />
                            {label}
                          </span>
                        );
                      }
                      if (label === "Done") {
                        return (
                          <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 shrink-0">
                            {label}
                          </span>
                        );
                      }
                      if (label === "Failed") {
                        return (
                          <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 shrink-0">
                            {label}
                          </span>
                        );
                      }
                      return (
                        <span className="bg-slate-500/5 text-slate-500 border border-slate-500/10 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 shrink-0">
                          {label}
                        </span>
                      );
                    })()}
                    <span className="text-muted-foreground/45 group-hover:text-muted-foreground transition-colors ml-0.5">
                      {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </span>
                  </div>
                </button>

                {/* Expanded content */}
                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      key="expanded"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.22, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-3 pt-0 space-y-3">
                        {/* Description */}
                        {task.description && (
                          <p className="text-[13px] text-muted-foreground leading-relaxed">{task.description}</p>
                        )}

                        {/* Task Thought (Reasoning) */}
                        {task.thought && (
                          <div className="bg-indigo-500/[0.02] dark:bg-indigo-500/[0.01] border-l-2 border-indigo-500/40 dark:border-indigo-400/30 border border-indigo-500/10 p-3.5 rounded-lg text-xs text-foreground/90 leading-relaxed mt-2 shadow-sm">
                            <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-indigo-500 dark:text-indigo-400 mb-2">
                              <Brain className="w-3 h-3 shrink-0" />
                              Stage Thoughts
                            </div>
                            <div className="font-sans">
                              {renderThoughtBlocks(task.thought)}
                            </div>
                          </div>
                        )}

                        {/* Subtasks — reasoning appears inline after the active sub-step */}
                        {hasSubs && (
                          <div className="space-y-1.5 border-l-2 border-border pl-4 ml-1">
                            {task.subtasks.map((sub, si) => {
                              const subActive = si === activeSubIdx && isActive;
                              const showSub   = isCompleted(sub.status) || isRunning(sub.status) || subActive || isCompleted(task.status);
                              if (!showSub && !isActive && !isExpanded) return null;

                              const subLabel = sub.title || `Step ${si + 1}`;

                              return (
                                <React.Fragment key={sub.id}>
                                  <motion.div
                                    initial={{ opacity: 0, x: -8 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: si * 0.04 }}
                                    className="flex items-start gap-2.5"
                                  >
                                    <div className="mt-[2px] shrink-0">
                                      {isCompleted(sub.status) ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/80" />
                                      ) : isRunning(sub.status) || subActive ? (
                                        <CircleDotDashed className="h-3.5 w-3.5 text-sky-400 animate-spin" />
                                      ) : (
                                        <Circle className="h-3.5 w-3.5 text-muted-foreground/30" />
                                      )}
                                    </div>
                                    <div>
                                      <p className={cn(
                                        "text-[12px] font-medium leading-snug",
                                        isCompleted(sub.status) ? "text-foreground/75" :
                                        (isRunning(sub.status) || subActive) ? "text-foreground/85" : "text-muted-foreground/50"
                                      )}>
                                        {subLabel}
                                      </p>
                                      {sub.description && (
                                        <p className="text-[11px] text-muted-foreground/70 mt-0.5 leading-relaxed">{sub.description}</p>
                                      )}
                                    </div>
                                  </motion.div>

                                  {/* Internal reasoning is kept hidden from the UI;
                                      the agent still uses memory for learning, but
                                      only the current execution steps are shown. */}
                                </React.Fragment>
                              );
                            })}
                          </div>
                        )}


                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Synthesizing Indicator */}
      {isAiTyping && totalCount > 0 && completedCount === totalCount && (
        <div className="mx-4 mb-4 p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.03] flex items-center gap-3 animate-pulse">
          <CircleDotDashed className="h-5.5 w-5.5 text-indigo-400 animate-spin shrink-0" />
          <div className="flex-1">
            <p className="text-[12px] font-bold text-indigo-400">Synthesizing Final Response</p>
            <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
              Analyzing compiled search details, extracting product information, and generating comparative suggestion report...
            </p>
          </div>
        </div>
      )}

      {/* Live Thoughts / Activity Log */}
      {thoughts && thoughts.length > 0 && (
        <div className="px-5 pb-3.5 pt-3 border-t border-border bg-muted/5 flex flex-col gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/45 block">
            Agent Activity Log
          </span>
          <div className="max-h-[120px] overflow-y-auto space-y-1.5 pr-2 scrollbar-thin">
            {thoughts.map((thought, idx) => (
              <div key={idx} className="text-[11px] text-foreground/70 leading-relaxed font-mono pl-3.5 border-l border-indigo-500/30">
                {thought}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer stats */}
      {propTasks.length > 0 && (
        <div className="px-4 pb-4">
          <div className="grid grid-cols-4 gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5">
            {[
              { label: "Done",    value: propTasks.filter((t) => isCompleted(t.status)).length,  color: "text-emerald-400" },
              { label: "Running", value: propTasks.filter((t) => isRunning(t.status)).length,    color: "text-sky-400"  },
              { label: "Waiting", value: propTasks.filter((t) => !isCompleted(t.status) && !isRunning(t.status) && !isFailed(t.status)).length, color: "text-muted-foreground/50" },
              { label: "Failed",  value: propTasks.filter((t) => isFailed(t.status)).length,     color: "text-red-400"  },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex flex-col items-center gap-0.5">
                <span className={cn("text-[15px] font-bold tabular-nums", color)}>{value}</span>
                <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground/40">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
