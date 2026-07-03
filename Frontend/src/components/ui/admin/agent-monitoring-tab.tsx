import * as React from "react";
import { sciparserApi, AdminAgentRun } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime } from "./shared";
import { Bot, Loader2, ListChecks, XCircle, Clock, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 15;
const STATUS_OPTIONS = ["", "IN_PROGRESS", "PENDING", "COMPLETED", "FAILED"];

export const AgentMonitoringTab: React.FC = () => {
  const [runs, setRuns] = React.useState<AdminAgentRun[]>([]);
  const [total, setTotal] = React.useState(0);
  const [counts, setCounts] = React.useState({ running: 0, queued: 0, failed: 0, completed: 0, avgRuntime: 0 });
  const [page, setPage] = React.useState(1);
  const [statusFilter, setStatusFilter] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(async (pageArg: number, statusArg: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.adminGetAgentRuns(pageArg, PAGE_SIZE, statusArg || undefined);
      setRuns(res.runs);
      setTotal(res.total);
      setCounts({
        running: res.running_count,
        queued: res.queued_count,
        failed: res.failed_count,
        completed: res.completed_count,
        avgRuntime: res.avg_runtime_seconds,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent runs");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load(page, statusFilter);
  }, [page, statusFilter, load]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Loader2 className="h-4 w-4" />} label="Running" value={counts.running.toLocaleString()} />
        <KPICard index={1} icon={<Clock className="h-4 w-4" />} label="Queued" value={counts.queued.toLocaleString()} />
        <KPICard index={2} icon={<XCircle className="h-4 w-4" />} label="Failed" value={counts.failed.toLocaleString()} />
        <KPICard index={3} icon={<ListChecks className="h-4 w-4" />} label="Avg Runtime" value={`${counts.avgRuntime}s`} />
      </div>

      <Panel
        title="Agent Executions"
        subtitle="Real-time log of every agent stage execution recorded in the system"
        action={
          <select
            value={statusFilter}
            onChange={(e) => {
              setPage(1);
              setStatusFilter(e.target.value);
            }}
            className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        }
      >
        {loading ? (
          <LoadingState />
        ) : error ? (
          <div className="text-sm text-red-500 py-6 text-center">{error}</div>
        ) : runs.length === 0 ? (
          <EmptyState label="No agent runs recorded yet." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Stage</th>
                    <th className="px-3 py-2 font-medium">Chat</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Tokens</th>
                    <th className="px-3 py-2 font-medium">Cost</th>
                    <th className="px-3 py-2 font-medium">When</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-medium">
                        {r.stage_name}
                        {r.error_message && (
                          <p className="text-xs text-red-500 mt-0.5 line-clamp-1 max-w-xs">{r.error_message}</p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground font-mono text-xs">{r.chat_id.slice(0, 12)}…</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-3 py-2">{r.tokens.toLocaleString()}</td>
                      <td className="px-3 py-2">${r.cost.toFixed(4)}</td>
                      <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-4 text-xs text-muted-foreground">
              <span>
                Page {page} of {totalPages} · {total} total runs
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 rounded border border-slate-200 dark:border-slate-700 disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 rounded border border-slate-200 dark:border-slate-700 disabled:opacity-40"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
};
