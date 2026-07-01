import React from "react";
import { CheckCircle2, Loader2, AlertCircle, Wrench, Clock } from "lucide-react";

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
}: ProcessingPanelProps) {
  const hasStages = agentHistory.length > 0;
  const hasTools = toolHistory.length > 0;

  if (!hasStages && !hasTools) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-3 text-center px-4">
        <Clock className="w-8 h-8 text-[#3A3A3A]" />
        <p className="text-xs text-[#6B7280] leading-relaxed">
          No history yet for this thread.
          <br />
          Run an agent task to see execution details here.
        </p>
      </div>
    );
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />;
      case "IN_PROGRESS":
        return <Loader2 className="size-4 text-blue-400 animate-spin shrink-0" />;
      case "FAILED":
        return <AlertCircle className="size-4 text-red-500 shrink-0" />;
      default:
        return <Loader2 className="size-4 text-slate-400 animate-spin shrink-0" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "bg-emerald-900/40 text-emerald-300 border border-emerald-800/40";
      case "FAILED":
        return "bg-red-900/40 text-red-300 border border-red-800/40";
      case "IN_PROGRESS":
        return "bg-blue-900/40 text-blue-300 border border-blue-800/40";
      default:
        return "bg-[#2A2A2A] text-[#9CA3AF] border border-[#333]";
    }
  };

  return (
    <div className="flex flex-col gap-0 divide-y divide-[#2A2A2A]">

      {/* Agent Stages */}
      {hasStages && (
        <div className="p-4 space-y-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-[#6B7280] mb-3">
            Agent Execution
          </p>
          {agentHistory.map((stage) => (
            <div
              key={stage.id}
              className="bg-[#141414] rounded-xl border border-[#2A2A2A] p-3 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {getStatusIcon(stage.status)}
                  <span className="text-xs font-semibold text-[#F8FAFC] truncate">
                    {stage.stage_name}
                  </span>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold shrink-0 ${getStatusBadge(stage.status)}`}>
                  {stage.status}
                </span>
              </div>

              {stage.input_data && Object.keys(stage.input_data).length > 0 && (
                <details className="group">
                  <summary className="text-[10px] text-[#6B7280] cursor-pointer hover:text-[#9CA3AF] transition-colors list-none flex items-center gap-1">
                    <span className="group-open:hidden">▶</span>
                    <span className="hidden group-open:inline">▼</span>
                    Input
                  </summary>
                  <pre className="mt-1 text-[10px] bg-[#0D0D0F] border border-[#232323] p-2 rounded-lg overflow-x-auto text-[#9CA3AF] leading-relaxed">
                    {JSON.stringify(stage.input_data, null, 2).slice(0, 300)}
                    {JSON.stringify(stage.input_data, null, 2).length > 300 ? "\n…" : ""}
                  </pre>
                </details>
              )}

              {stage.output_data && Object.keys(stage.output_data).length > 0 && (
                <details className="group">
                  <summary className="text-[10px] text-[#6B7280] cursor-pointer hover:text-[#9CA3AF] transition-colors list-none flex items-center gap-1">
                    <span className="group-open:hidden">▶</span>
                    <span className="hidden group-open:inline">▼</span>
                    Output
                  </summary>
                  <pre className="mt-1 text-[10px] bg-[#0D0D0F] border border-[#232323] p-2 rounded-lg overflow-x-auto text-[#9CA3AF] leading-relaxed">
                    {JSON.stringify(stage.output_data, null, 2).slice(0, 300)}
                    {JSON.stringify(stage.output_data, null, 2).length > 300 ? "\n…" : ""}
                  </pre>
                </details>
              )}

              {stage.error_message && (
                <div className="p-2 bg-red-900/20 border border-red-800/30 rounded-lg text-red-300 text-[10px] flex items-start gap-1.5">
                  <AlertCircle className="size-3 shrink-0 mt-0.5" />
                  {stage.error_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tool Execution Logs — always shown when available */}
      {hasTools && (
        <div className="p-4 space-y-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-[#6B7280] mb-3">
            Tool Execution ({toolHistory.length})
          </p>
          {toolHistory.map((tool) => (
            <div
              key={tool.id}
              className="bg-[#141414] rounded-xl border border-[#2A2A2A] p-3 space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Wrench className="size-3.5 text-[#22D3EE] shrink-0" />
                  <span className="text-xs font-semibold text-[#F8FAFC] truncate font-mono">
                    {tool.tool_name}
                  </span>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold shrink-0 ${getStatusBadge(tool.status)}`}>
                  {tool.status}
                </span>
              </div>

              {tool.tool_input && Object.keys(tool.tool_input).length > 0 && (
                <details className="group">
                  <summary className="text-[10px] text-[#6B7280] cursor-pointer hover:text-[#9CA3AF] transition-colors list-none flex items-center gap-1">
                    <span className="group-open:hidden">▶</span>
                    <span className="hidden group-open:inline">▼</span>
                    Input
                  </summary>
                  <pre className="mt-1 text-[10px] bg-[#0D0D0F] border border-[#232323] p-2 rounded-lg overflow-x-auto text-[#9CA3AF] leading-relaxed">
                    {JSON.stringify(tool.tool_input, null, 2).slice(0, 300)}
                    {JSON.stringify(tool.tool_input, null, 2).length > 300 ? "\n…" : ""}
                  </pre>
                </details>
              )}

              {tool.tool_output && Object.keys(tool.tool_output).length > 0 && (
                <details className="group">
                  <summary className="text-[10px] text-[#6B7280] cursor-pointer hover:text-[#9CA3AF] transition-colors list-none flex items-center gap-1">
                    <span className="group-open:hidden">▶</span>
                    <span className="hidden group-open:inline">▼</span>
                    Output
                  </summary>
                  <pre className="mt-1 text-[10px] bg-[#0D0D0F] border border-[#232323] p-2 rounded-lg overflow-x-auto text-[#9CA3AF] leading-relaxed">
                    {JSON.stringify(tool.tool_output, null, 2).slice(0, 300)}
                    {JSON.stringify(tool.tool_output, null, 2).length > 300 ? "\n…" : ""}
                  </pre>
                </details>
              )}

              {tool.error_message && (
                <div className="p-2 bg-red-900/20 border border-red-800/30 rounded-lg text-red-300 text-[10px] flex items-start gap-1.5">
                  <AlertCircle className="size-3 shrink-0 mt-0.5" />
                  {tool.error_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
