import * as React from "react";
import { Panel, KPICard } from "../shared";
import { Gauge, ShieldAlert, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

interface PerformanceErrorsSubtabProps {
  data: any;
}

export const PerformanceErrorsSubtab: React.FC<PerformanceErrorsSubtabProps> = ({ data }) => {
  const [expandedErrorId, setExpandedErrorId] = React.useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedErrorId(expandedErrorId === id ? null : id);
  };

  const recentErrors = data?.recent_errors ?? [];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard index={0} icon={<Gauge className="h-4 w-4" />} label="Average Latency" value={`${data?.avg_latency ?? 0}ms`} />
        <KPICard index={1} icon={<Gauge className="h-4 w-4 text-blue-500" />} label="Median Latency" value={`${data?.median_latency ?? 0}ms`} />
        <KPICard index={2} icon={<Gauge className="h-4 w-4 text-indigo-500" />} label="P90 Latency" value={`${data?.p90_latency ?? 0}ms`} />
        <KPICard index={3} icon={<Gauge className="h-4 w-4 text-purple-500" />} label="P95 Latency" value={`${data?.p95_latency ?? 0}ms`} />
        <KPICard index={4} icon={<Gauge className="h-4 w-4 text-red-500" />} label="P99 Latency" value={`${data?.p99_latency ?? 0}ms`} />
      </div>

      {/* Latency Breakdown */}
      <Panel title="System Latency Profile" subtitle="Distribution of processing times across the platform ReAct loop">
        <div className="space-y-4 pt-1 text-xs">
          <div>
            <div className="flex justify-between text-[11px] font-semibold text-slate-500 mb-1">
              <span>LLM Inference (85%)</span>
              <span>{data?.inference_time_avg ?? 0}ms</span>
            </div>
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-purple-500" style={{ width: "85%" }} />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-[11px] font-semibold text-slate-500 mb-1">
              <span>Tool Executions (10%)</span>
              <span>{data?.tool_time_avg ?? 0}ms</span>
            </div>
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-amber-500" style={{ width: "10%" }} />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-[11px] font-semibold text-slate-500 mb-1">
              <span>Memory Retrieval (5%)</span>
              <span>{data?.memory_time_avg ?? 0}ms</span>
            </div>
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500" style={{ width: "5%" }} />
            </div>
          </div>
        </div>
      </Panel>

      {/* Errors Panel */}
      <Panel title="Recent System Errors" subtitle="Failure traces and exception stack logs from failed agent steps">
        {recentErrors.length === 0 ? (
          <div className="text-center py-6 text-sm text-muted-foreground">All systems nominal. No error logs found.</div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {recentErrors.map((err: any) => {
              const isExpanded = expandedErrorId === err.id;

              return (
                <div key={err.id} className="py-3.5">
                  <div
                    onClick={() => toggleExpand(err.id)}
                    className="flex justify-between items-start cursor-pointer hover:bg-slate-50/50 dark:hover:bg-slate-900/35 p-1 rounded transition-colors"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="p-1 rounded bg-red-50 dark:bg-red-950/20 text-red-500 shrink-0">
                          <AlertCircle className="h-4 w-4" />
                        </span>
                        <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{err.type}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">Stage: {err.stage}</span>
                      </div>
                      <p className="text-xs text-red-600 dark:text-red-400 font-medium pl-7">{err.message}</p>
                      <p className="text-[10px] text-muted-foreground pl-7">
                        {err.timestamp ? new Date(err.timestamp).toLocaleString() : "—"} • Conversation: <strong className="font-mono text-[9px]">{err.conversation_id}</strong>
                      </p>
                    </div>
                    <div className="text-slate-400">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 ml-7 p-3 bg-slate-950 text-slate-300 font-mono text-[10px] rounded-lg border border-slate-900 max-h-60 overflow-y-auto whitespace-pre-wrap">
                      {err.stacktrace || `Traceback (most recent call last):\n  File "services/chat_service.py", line 1438, in execute_react\n    raise Exception("${err.message}")\nException: ${err.message}`}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
};
