"use client";

import React, { useState } from "react";
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX, ChevronDown, ChevronRight, ChevronUp, Sparkles, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
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
  details?: string; // Added to support dynamic stage details
}

interface PlanProps {
  tasks: Task[];
}

export default function Plan({ tasks }: PlanProps) {
  const allCompleted = tasks.every(t => t.status === 'completed');
  // If it's already completed on mount (history), don't auto-collapse
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [expandedTasks, setExpandedTasks] = React.useState<string[]>(tasks.map(t => t.id));

  // Only auto-collapse if it's a LIVE transition to completed
  const wasAllCompleted = React.useRef(allCompleted);
  React.useEffect(() => {
    // If it was NOT completed and now it IS, then auto-collapse (Live Chat)
    if (allCompleted && !wasAllCompleted.current) {
      // Small delay before collapsing to let the user see the final checkmark
      const timer = setTimeout(() => {
        setIsCollapsed(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
    wasAllCompleted.current = allCompleted;
  }, [allCompleted]);

  const toggleTask = (taskId: string) => {
    setExpandedTasks(prev => 
      prev.includes(taskId) ? prev.filter(id => id !== taskId) : [...prev, taskId]
    );
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case "in-progress": return (
        <div className="relative flex items-center justify-center">
          <CircleDotDashed className="w-4 h-4 text-blue-500 animate-spin" />
          <motion.div 
            className="absolute w-6 h-6 rounded-full border border-blue-500/20"
            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </div>
      );
      case "failed": return <CircleX className="w-4 h-4 text-red-500" />;
      case "need-help": return <CircleAlert className="w-4 h-4 text-yellow-500" />;
      default: return <Circle className="w-4 h-4 text-slate-600" />;
    }
  };

  return (
    <div className="w-full max-w-2xl my-4">
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-2 h-2 rounded-full",
            allCompleted ? "bg-green-500" : "bg-blue-500 animate-pulse"
          )} />
          <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
            {allCompleted ? "Execution Complete" : "Agent Processing"}
          </span>
        </div>
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="text-[10px] font-bold text-indigo-500 hover:text-indigo-400 transition-colors flex items-center gap-1.5 tracking-wider"
        >
          {isCollapsed ? "VIEW WORKFLOW" : "HIDE WORKFLOW"}
          {isCollapsed ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
        </button>
      </div>

      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="space-y-4 relative"
          >
            {/* Vertical Line connecting steps */}
            <div className="absolute left-[19px] top-2 bottom-2 w-[1px] bg-slate-200 dark:bg-slate-800 z-0" />

            {tasks.map((task, idx) => (
              <div key={task.id} className="relative z-10">
                <div 
                  className="flex items-start gap-4 group cursor-pointer"
                  onClick={() => toggleTask(task.id)}
                >
                  <div className="mt-0.5 bg-slate-50 dark:bg-[#0f0f11] rounded-full p-1">
                    {getStatusIcon(task.status)}
                  </div>
                  
                  <div className="flex-1 pt-0.5">
                    <div className="flex items-center justify-between">
                      <span className={cn(
                        "text-[13px] font-bold tracking-tight transition-colors",
                        task.status === 'completed' ? 'text-slate-400' : 'text-slate-900 dark:text-slate-100',
                        task.status === 'in-progress' && 'text-blue-500'
                      )}>
                        {task.title}
                      </span>
                      {task.status === 'in-progress' && (
                        <span className="text-[9px] font-bold bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded uppercase tracking-tighter">
                          in-progress
                        </span>
                      )}
                      {task.status === 'pending' && (
                        <div className="flex items-center gap-1">
                           <span className="text-[9px] font-bold text-slate-500 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">{idx + 1}</span>
                           <span className="text-[9px] font-bold text-slate-500 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded uppercase tracking-tighter">pending</span>
                        </div>
                      )}
                    </div>

                    <AnimatePresence>
                      {expandedTasks.includes(task.id) && (
                        <motion.div 
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden"
                        >
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                            {task.description}
                          </p>
                          
                          {task.details && (
                            <div className="mt-2 p-2.5 rounded-lg bg-indigo-500/5 border border-indigo-500/10 text-[11px] text-indigo-400/90 font-medium italic whitespace-pre-wrap">
                              {task.details}
                            </div>
                          )}

                          {task.subtasks.length > 0 && (
                            <div className="mt-3 space-y-2 pl-2 border-l border-slate-200 dark:border-slate-800">
                              {task.subtasks.map(sub => (
                                <div key={sub.id} className="flex flex-col gap-1">
                                  <div className="flex items-center gap-2">
                                    <div className={cn(
                                      "w-1 h-1 rounded-full",
                                      sub.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                                    )} />
                                    <span className={cn(
                                      "text-[11px]",
                                      sub.status === 'completed' ? 'text-slate-500 line-through' : 'text-slate-300'
                                    )}>
                                      {sub.title}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}