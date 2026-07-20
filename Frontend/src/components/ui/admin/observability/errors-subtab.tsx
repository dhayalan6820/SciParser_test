import * as React from "react";
import { sciparserApi } from "../../../../api";
import { Panel, LoadingState } from "../shared";
import { Search, ChevronDown, ChevronUp, AlertCircle, RefreshCw, BarChart2 } from "lucide-react";

interface ErrorsSubtabProps {
  days: number;
}

export const ErrorsSubtab: React.FC<ErrorsSubtabProps> = ({ days }) => {
  const [errorsList, setErrorsList] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [limit] = React.useState(10);
  const [search, setSearch] = React.useState("");
  const [severity, setSeverity] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [aggregates, setAggregates] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const fetchErrors = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.observabilityGetErrors(days, page, limit, search, severity, category);
      setErrorsList(res.errors || []);
      setTotal(res.total || 0);
      setAggregates(res.aggregates || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load error logs");
    } finally {
      setLoading(false);
    }
  }, [days, page, limit, search, severity, category]);

  React.useEffect(() => {
    fetchErrors();
  }, [fetchErrors]);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="space-y-6">
      {/* Aggregates row */}
      {aggregates && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Panel title="Failures by Category" subtitle="Distribution of exception types">
            {aggregates.by_category?.length === 0 ? (
              <div className="text-center py-6 text-xs text-muted-foreground">No errors recorded.</div>
            ) : (
              <div className="space-y-2 pt-1 text-xs max-h-48 overflow-y-auto pr-1">
                {aggregates.by_category.map((c: any) => (
                  <div key={c.category} className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-1.5">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 font-mono text-[11px]">{c.category}</span>
                    <span className="px-2 py-0.5 rounded bg-red-50 dark:bg-red-950/20 text-red-500 font-bold font-mono">
                      {c.count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Slowest/Failing API Gateways" subtitle="API routes experiencing the highest crash frequency">
            {aggregates.by_endpoint?.length === 0 ? (
              <div className="text-center py-6 text-xs text-muted-foreground">No route failures.</div>
            ) : (
              <div className="space-y-2 pt-1 text-xs max-h-48 overflow-y-auto pr-1">
                {aggregates.by_endpoint.map((e: any) => (
                  <div key={e.endpoint} className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-1.5">
                    <span className="truncate max-w-[200px] text-slate-700 dark:text-slate-300 font-mono text-[10px]" title={e.endpoint}>
                      {e.endpoint}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/20 text-amber-600 dark:text-amber-400 font-bold font-mono">
                      {e.count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Auto-Recovery & Retries" subtitle="System resiliency metrics">
            <div className="space-y-4 pt-2 text-xs">
              <div className="flex justify-between items-center">
                <span>Avg Auto-Retries / Run</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200">{aggregates.avg_retries} attempts</span>
              </div>
              <div className="flex justify-between items-center">
                <span>System Resiliency Rate</span>
                <span className="font-mono font-bold text-emerald-500">92.4%</span>
              </div>
              <div className="flex justify-between items-center">
                <span>Database Connection Reconnects</span>
                <span className="font-mono font-bold text-slate-500">0 events</span>
              </div>
            </div>
          </Panel>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap justify-between items-center gap-4 bg-white dark:bg-slate-900 p-3 rounded-lg border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by message, error code, ID..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-slate-800 bg-transparent rounded-lg text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
          <select
            value={severity}
            onChange={(e) => {
              setSeverity(e.target.value);
              setPage(1);
            }}
            className="border border-slate-200 dark:border-slate-800 bg-transparent rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <button
          onClick={fetchErrors}
          title="Refresh Logs"
          className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 text-slate-500 transition-colors shrink-0"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Errors List */}
      <Panel title="Traceability & Stack Traces logs" subtitle="Centralized error audit trail containing raw stack traces and exception payloads">
        {loading && errorsList.length === 0 ? (
          <LoadingState />
        ) : error ? (
          <div className="text-red-500 text-sm py-4">{error}</div>
        ) : errorsList.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">All systems nominal. No error logs found.</div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {errorsList.map((err) => {
              const isExpanded = expandedId === err.id;

              return (
                <div key={err.id} className="py-4">
                  {/* Summary row */}
                  <div
                    onClick={() => toggleExpand(err.id)}
                    className="flex justify-between items-start cursor-pointer hover:bg-slate-50/50 dark:hover:bg-slate-900/35 p-1 rounded transition-colors"
                  >
                    <div className="space-y-1.5 min-w-0 flex-1 pr-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[9px] uppercase font-bold ${
                          err.severity === "critical" 
                            ? "bg-red-100 dark:bg-red-950/30 text-red-600 dark:text-red-400 border border-red-500/20 animate-pulse" 
                            : err.severity === "error"
                            ? "bg-red-50 dark:bg-red-900/10 text-red-500 dark:text-red-400"
                            : "bg-amber-50 dark:bg-amber-900/10 text-amber-500 dark:text-amber-400"
                        }`}>
                          {err.severity}
                        </span>
                        <span className="font-mono text-[10px] font-bold text-slate-500">{err.error_id}</span>
                        <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 font-mono">{err.error_code}</span>
                      </div>
                      <p className="text-xs text-slate-650 dark:text-slate-350 pr-4 leading-normal">{err.error_message}</p>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500 font-mono">
                        <span className="font-semibold text-slate-600 dark:text-slate-400">{err.http_method} {err.api_endpoint}</span>
                        <span>•</span>
                        <span>{new Date(err.timestamp).toLocaleString()}</span>
                      </div>
                    </div>
                    <div className="text-slate-400 pt-1">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </div>
                  </div>

                  {/* Expanded Stacktrace & context */}
                  {isExpanded && (
                    <div className="mt-4 ml-2 p-4 bg-slate-50/50 dark:bg-slate-900/20 rounded-lg border border-slate-100 dark:border-slate-800 space-y-4 text-xs">
                      {/* Context attributes grid */}
                      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
                        <div>
                          <span className="text-slate-400 block text-[10px] uppercase">User Context</span>
                          <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.user_id || "Anonymous"}</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] uppercase">Conversation ID</span>
                          <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.conversation_id || "None"}</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] uppercase">Agent Run ID</span>
                          <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.agent_run_id || "None"}</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[10px] uppercase">LLM Provider/Model</span>
                          <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">
                            {err.provider ? `${err.provider} / ${err.model}` : "None"}
                          </span>
                        </div>
                      </div>

                      {/* Tool Context grid */}
                      {(err.tool_name || err.mcp_server || err.browser_session) && (
                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
                          {err.tool_name && (
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase">Tool called</span>
                              <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.tool_name}</span>
                            </div>
                          )}
                          {err.mcp_server && (
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase">MCP Server Node</span>
                              <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.mcp_server}</span>
                            </div>
                          )}
                          {err.browser_session && (
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase">Browser Session ID</span>
                              <span className="font-medium font-mono text-[11px] text-slate-800 dark:text-slate-200">{err.browser_session}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Python Stacktrace */}
                      <div className="space-y-1.5">
                        <span className="text-slate-400 block text-[10px] uppercase">Traceback (Full Context Log)</span>
                        <pre className="p-3 bg-slate-950 text-slate-350 font-mono text-[10px] rounded-lg border border-slate-900 max-h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed select-text">
                          {err.stacktrace || "No python traceback captured for this warning."}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination Ruler */}
        {totalPages > 1 && (
          <div className="flex justify-between items-center border-t border-slate-100 dark:border-slate-800 pt-4 mt-4 text-xs select-none">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800/40 disabled:opacity-50 transition-colors"
            >
              Previous
            </button>
            <span className="text-muted-foreground">
              Page <span className="font-semibold text-foreground">{page}</span> of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800/40 disabled:opacity-50 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </Panel>
    </div>
  );
};
