import React from "react";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";

interface AgentStage {
  id: string;
  agent_stage: string;
  stage_name: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  status: string;
  error_message?: string;
}

interface ToolExecution {
  id: string;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output: Record<string, any>;
  status: string;
  error_message?: string;
}

interface ProcessingPanelProps {
  agentHistory: AgentStage[];
  toolHistory: ToolExecution[];
  isBrowserActive: boolean;
  browserFrame: string | null;
}

export function ProcessingPanel({
  agentHistory,
  toolHistory,
  isBrowserActive,
  browserFrame,
}: ProcessingPanelProps) {
  if (agentHistory.length === 0 && !isBrowserActive) {
    return null;
  }

  const getAgentStatusIcon = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <CheckCircle2 className="size-4 text-emerald-500" />;
      case "IN_PROGRESS":
        return <Loader2 className="size-4 text-blue-500 animate-spin" />;
      case "FAILED":
        return <AlertCircle className="size-4 text-red-500" />;
      default:
        return <Loader2 className="size-4 text-slate-400 animate-spin" />;
    }
  };

  const getAgentStatusText = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "Completed";
      case "IN_PROGRESS":
        return "Processing";
      case "FAILED":
        return "Failed";
      default:
        return "Pending";
    }
  };

  return (
    <div className="border-t border-[#2f2f2f] bg-slate-50 dark:bg-[#1a1a1a]">
      {/* Agent Stages */}
      <div className="p-4 space-y-3">
        <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-2">
          Agent Execution
        </h3>
        
        {agentHistory.map((stage, index) => (
          <div
            key={stage.id}
            className="bg-white dark:bg-[#212121] rounded-lg border border-slate-200 dark:border-[#2f2f2f] p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {getAgentStatusIcon(stage.status)}
                <span className="text-sm font-semibold text-slate-900 dark:text-white">
                  {stage.stage_name}
                </span>
              </div>
              <span className={`
                text-xs px-2 py-1 rounded-full
                ${stage.status === "COMPLETED" 
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200" 
                  : stage.status === "FAILED"
                  ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                  : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                }
              `}>
                {getAgentStatusText(stage.status)}
              </span>
            </div>

            {stage.input_data && Object.keys(stage.input_data).length > 0 && (
              <div className="mb-2">
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Input:</p>
                <pre className="text-xs bg-slate-100 dark:bg-[#171717] p-2 rounded overflow-x-auto text-slate-700 dark:text-slate-300">
                  {JSON.stringify(stage.input_data, null, 2).slice(0, 200)}
                  {JSON.stringify(stage.input_data, null, 2).length > 200 ? "..." : ""}
                </pre>
              </div>
            )}

            {stage.output_data && Object.keys(stage.output_data).length > 0 && (
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Output:</p>
                <pre className="text-xs bg-slate-100 dark:bg-[#171717] p-2 rounded overflow-x-auto text-slate-700 dark:text-slate-300">
                  {JSON.stringify(stage.output_data, null, 2).slice(0, 200)}
                  {JSON.stringify(stage.output_data, null, 2).length > 200 ? "..." : ""}
                </pre>
              </div>
            )}

            {stage.error_message && (
              <div className="mt-2 p-2 bg-red-100 dark:bg-red-900/30 rounded text-red-800 dark:text-red-200 text-xs">
                <AlertCircle className="size-3 inline mr-1" />
                {stage.error_message}
              </div>
            )}
          </div>
        ))}

        {/* Browser View */}
        {isBrowserActive && (
          <div className="mt-4">
            <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-2">
              Browser Execution
            </h3>
            
            <div className="bg-white dark:bg-[#212121] rounded-lg border border-slate-200 dark:border-[#2f2f2f] overflow-hidden">
              {/* Browser Header */}
              <div className="h-10 bg-slate-100 dark:bg-[#2f2f2f] border-b border-[#2f2f2f] flex items-center px-3 gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                </div>
                <div className="flex-1">
                  <div className="bg-white dark:bg-[#171717] border border-[#3e3e3f] rounded px-2 py-1 text-xs text-slate-700 dark:text-slate-300">
                    https://arxiv.org/abs/2403.11985
                  </div>
                </div>
              </div>

              {/* Browser Content */}
              <div className="h-48 bg-white dark:bg-[#171717] flex items-center justify-center">
                {browserFrame ? (
                  <img
                    src={`data:image/jpeg;base64,${browserFrame}`}
                    alt="Live Browser Screencast"
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="text-center p-4">
                    <Loader2 className="size-8 text-emerald-500 animate-spin mx-auto mb-2" />
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Connecting to browser...
                    </p>
                  </div>
                )}
              </div>

              {/* Tool Logs */}
              {toolHistory.length > 0 && (
                <div className="border-t border-[#2f2f2f] p-3 max-h-32 overflow-y-auto">
                  <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-2">
                    Tool Execution
                  </p>
                  <div className="space-y-2">
                    {toolHistory.slice(-3).map((tool) => (
                      <div
                        key={tool.id}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="text-slate-700 dark:text-slate-300">
                          {tool.tool_name}
                        </span>
                        <span className={`
                          px-2 py-0.5 rounded
                          ${tool.status === "COMPLETED"
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
                            : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                          }
                        `}>
                          {tool.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}