import * as React from "react";
import { Button } from "../button";
import { Input } from "../input";
import {
  sciparserApi,
  OperationsMetrics,
  OperationsLogEntry,
  OperationsLogFilters,
} from "../../../api";
import { cn } from "../../../../lib/utils";
import {
  Loader2,
  AlertCircle,
  Activity,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  Cpu,
  DollarSign,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
} from "lucide-react";

export const OperationsTab: React.FC = () => {
  const [metrics, setMetrics] = React.useState<OperationsMetrics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [days, setDays] = React.useState(30);

  React.useEffect(() => {
    setLoading(true);
    setError(null);
    sciparserApi
      .adminGetOperationsMetrics(days)
      .then(setMetrics)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load metrics"))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading operations data...
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/40 rounded-lg text-red-600 dark:text-red-400 text-sm max-w-lg mx-auto">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {error || "No data available"}
      </div>
    );
  }

  const maxDailyRuns = Math.max(1, ...metrics.daily_trends.map((d) => d.runs));

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Execution Overview</h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={<Activity className="h-4 w-4" />} label="Total Runs" value={metrics.total_runs.toLocaleString()} />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          label="Success Rate"
          value={`${metrics.success_rate}%`}
        />
        <StatCard icon={<Cpu className="h-4 w-4 text-emerald-500" />} label="Total Tokens" value={metrics.total_tokens.toLocaleString()} />
        <StatCard icon={<DollarSign className="h-4 w-4 text-amber-500" />} label="Total Cost" value={`$${metrics.total_cost.toFixed(2)}`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium flex items-center gap-1.5">
              <TrendingUp className="h-4 w-4 text-emerald-500" /> {metrics.success_count} succeeded
            </h3>
            <h3 className="text-sm font-medium flex items-center gap-1.5">
              <TrendingDown className="h-4 w-4 text-red-500" /> {metrics.failure_count} failed
            </h3>
          </div>
          <div className="flex items-end gap-1 h-32">
            {metrics.daily_trends.length === 0 ? (
              <div className="w-full text-center text-xs text-muted-foreground self-center">No runs in this period</div>
            ) : (
              metrics.daily_trends.map((d) => (
                <div key={d.date} className="flex-1 flex flex-col justify-end items-center gap-0.5 group relative">
                  <div className="w-full flex flex-col-reverse rounded overflow-hidden" style={{ height: `${(d.runs / maxDailyRuns) * 100}%`, minHeight: d.runs > 0 ? "4px" : 0 }}>
                    {d.failure > 0 && (
                      <div className="bg-red-400 dark:bg-red-500 w-full" style={{ height: `${(d.failure / d.runs) * 100}%` }} />
                    )}
                    {d.success > 0 && (
                      <div className="bg-emerald-400 dark:bg-emerald-500 w-full" style={{ height: `${(d.success / d.runs) * 100}%` }} />
                    )}
                  </div>
                  <span className="absolute -top-6 hidden group-hover:block text-[10px] bg-slate-900 text-white px-1.5 py-0.5 rounded whitespace-nowrap">
                    {d.date}: {d.runs} runs
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4">
          <h3 className="text-sm font-medium mb-3">Status Breakdown</h3>
          <div className="space-y-2">
            {metrics.status_breakdown.length === 0 ? (
              <p className="text-xs text-muted-foreground">No status data available</p>
            ) : (
              metrics.status_breakdown.map((s) => (
                <div key={s.status} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{s.status}</span>
                  <span className="font-medium">{s.count}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4">
        <h3 className="text-sm font-medium mb-3 flex items-center gap-1.5">
          <XCircle className="h-4 w-4 text-red-500" /> Top Failure Reasons
        </h3>
        {metrics.top_errors.length === 0 ? (
          <p className="text-xs text-muted-foreground">No failures recorded in this period.</p>
        ) : (
          <ul className="space-y-2">
            {metrics.top_errors.map((e, idx) => (
              <li key={idx} className="flex items-center justify-between text-sm gap-4">
                <span className="text-muted-foreground truncate">{e.error}</span>
                <span className="shrink-0 font-medium">{e.count}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <OperationsLogTable />
    </div>
  );
};

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => (
  <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4">
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
      {icon}
      {label}
    </div>
    <div className="text-2xl font-semibold">{value}</div>
  </div>
);

const LOG_PAGE_SIZE = 20;

const OperationsLogTable: React.FC = () => {
  const [logs, setLogs] = React.useState<OperationsLogEntry[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [exporting, setExporting] = React.useState<"csv" | "json" | null>(null);
  const [exportError, setExportError] = React.useState<string | null>(null);

  const [username, setUsername] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [agentStage, setAgentStage] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");

  const totalPages = Math.max(1, Math.ceil(total / LOG_PAGE_SIZE));

  const buildFilters = React.useCallback(
    (
      pageArg: number,
      overrides?: Partial<{ username: string; status: string; agentStage: string; startDate: string; endDate: string }>
    ): OperationsLogFilters => {
      const merged = {
        username,
        status,
        agentStage,
        startDate,
        endDate,
        ...overrides,
      };
      return {
        page: pageArg,
        pageSize: LOG_PAGE_SIZE,
        username: merged.username || undefined,
        status: merged.status || undefined,
        agentStage: merged.agentStage || undefined,
        startDate: merged.startDate || undefined,
        endDate: merged.endDate || undefined,
      };
    },
    [username, status, agentStage, startDate, endDate]
  );

  const loadLogs = React.useCallback(
    async (
      pageArg: number,
      overrides?: Partial<{ username: string; status: string; agentStage: string; startDate: string; endDate: string }>
    ) => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetOperationsLogs(buildFilters(pageArg, overrides));
        setLogs(res.logs);
        setTotal(res.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load operations log");
      } finally {
        setLoading(false);
      }
    },
    [buildFilters]
  );

  React.useEffect(() => {
    loadLogs(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const applyFilters = () => {
    setPage(1);
    loadLogs(1);
  };

  const clearFilters = () => {
    setUsername("");
    setStatus("");
    setAgentStage("");
    setStartDate("");
    setEndDate("");
    setPage(1);
    loadLogs(1, { username: "", status: "", agentStage: "", startDate: "", endDate: "" });
  };

  const handleExport = async (format: "csv" | "json") => {
    setExporting(format);
    setExportError(null);
    try {
      await sciparserApi.adminExportOperationsLogs(buildFilters(1), format);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <Filter className="h-4 w-4" /> Execution Log
        </h3>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            disabled={exporting !== null}
            onClick={() => handleExport("csv")}
          >
            {exporting === "csv" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            disabled={exporting !== null}
            onClick={() => handleExport("json")}
          >
            {exporting === "json" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Export JSON
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <Input
          placeholder="User (username/email)"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="text-sm"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
        >
          <option value="">Any status</option>
          <option value="SUCCESS">Success</option>
          <option value="FAILED">Failed</option>
          <option value="PENDING">Pending</option>
        </select>
        <Input
          placeholder="Stage (e.g. Agent 1)"
          value={agentStage}
          onChange={(e) => setAgentStage(e.target.value)}
          className="text-sm"
        />
        <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-sm" />
        <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="text-sm" />
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={applyFilters}>Apply Filters</Button>
        <Button size="sm" variant="outline" onClick={clearFilters}>Clear</Button>
        {exportError && <span className="text-xs text-red-500">{exportError}</span>}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading logs...
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/40 rounded-lg text-red-600 dark:text-red-400 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      ) : logs.length === 0 ? (
        <p className="text-xs text-muted-foreground py-6 text-center">No runs match these filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground border-b border-slate-200 dark:border-slate-800">
                <th className="py-2 pr-3 font-medium">Time</th>
                <th className="py-2 pr-3 font-medium">User</th>
                <th className="py-2 pr-3 font-medium">Stage</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Tokens</th>
                <th className="py-2 pr-3 font-medium">Cost</th>
                <th className="py-2 pr-3 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-slate-100 dark:border-slate-900/60">
                  <td className="py-2 pr-3 whitespace-nowrap text-xs text-muted-foreground">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-3">{log.username || log.user_id}</td>
                  <td className="py-2 pr-3">{log.stage_name}</td>
                  <td className="py-2 pr-3">
                    <span
                      className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-medium",
                        log.status === "SUCCESS"
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                          : log.status === "FAILED"
                          ? "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
                          : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      )}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="py-2 pr-3">{log.tokens.toLocaleString()}</td>
                  <td className="py-2 pr-3">${log.cost.toFixed(4)}</td>
                  <td className="py-2 pr-3 max-w-[220px] truncate text-xs text-muted-foreground" title={log.error_message || ""}>
                    {log.error_message || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && logs.length > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
          <span>
            Page {page} of {totalPages} ({total} total)
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
