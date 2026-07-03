import * as React from "react";
import { sciparserApi, AdminAgentRun, AdminAgentRunTimeline } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime, useAutoRefresh, RefreshButton } from "./shared";
import {
  Bot,
  Loader2,
  ListChecks,
  XCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
  Search,
  ArrowUpDown,
  X,
  Ban,
} from "lucide-react";

const PAGE_SIZE = 15;
const STATUS_OPTIONS = ["", "IN_PROGRESS", "PENDING", "COMPLETED", "FAILED"];
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "created_at", label: "Time" },
  { value: "tokens", label: "Tokens" },
  { value: "cost", label: "Cost" },
  { value: "status", label: "Status" },
];

export const AgentMonitoringTab: React.FC = () => {
  const [runs, setRuns] = React.useState<AdminAgentRun[]>([]);
  const [total, setTotal] = React.useState(0);
  const [counts, setCounts] = React.useState({ running: 0, queued: 0, failed: 0, completed: 0, avgRuntime: 0 });
  const [page, setPage] = React.useState(1);
  const [statusFilter, setStatusFilter] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [sortBy, setSortBy] = React.useState("created_at");
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [selectedChatId, setSelectedChatId] = React.useState<string | null>(null);
  const [timeline, setTimeline] = React.useState<AdminAgentRunTimeline | null>(null);
  const [timelineLoading, setTimelineLoading] = React.useState(false);
  const [timelineError, setTimelineError] = React.useState<string | null>(null);
  const [cancelling, setCancelling] = React.useState(false);
  const [cancelResult, setCancelResult] = React.useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(
    async (pageArg: number, statusArg: string, searchArg: string, sortByArg: string, sortDirArg: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetAgentRuns(pageArg, PAGE_SIZE, statusArg || undefined, searchArg || undefined, sortByArg, sortDirArg);
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
    },
    []
  );

  React.useEffect(() => {
    load(page, statusFilter, search, sortBy, sortDir);
  }, [page, statusFilter, search, sortBy, sortDir, load]);

  const isLiveFilter = statusFilter === "" || statusFilter === "IN_PROGRESS" || statusFilter === "PENDING";

  useAutoRefresh(
    () => load(page, statusFilter, search, sortBy, sortDir),
    15000,
    isLiveFilter
  );

  React.useEffect(() => {
    const handle = setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 350);
    return () => clearTimeout(handle);
  }, [searchInput]);

  const toggleSort = (value: string) => {
    if (sortBy === value) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(value);
      setSortDir("desc");
    }
  };

  const openTimeline = async (chatId: string) => {
    setSelectedChatId(chatId);
    setTimeline(null);
    setTimelineError(null);
    setCancelResult(null);
    setTimelineLoading(true);
    try {
      const res = await sciparserApi.adminGetAgentRunTimeline(chatId);
      setTimeline(res);
    } catch (err) {
      setTimelineError(err instanceof Error ? err.message : "Failed to load timeline");
    } finally {
      setTimelineLoading(false);
    }
  };

  const closeTimeline = () => {
    setSelectedChatId(null);
    setTimeline(null);
    setTimelineError(null);
    setCancelResult(null);
  };

  const handleCancel = async () => {
    if (!selectedChatId) return;
    setCancelling(true);
    setCancelResult(null);
    try {
      const res = await sciparserApi.adminCancelAgentRun(selectedChatId);
      setCancelResult(res.detail || (res.success ? "Run cancelled." : "Nothing to cancel."));
      await openTimeline(selectedChatId);
      load(page, statusFilter, search, sortBy, sortDir);
    } catch (err) {
      setCancelResult(err instanceof Error ? err.message : "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  };

  const isCancellable = (r: AdminAgentRun) => r.status === "IN_PROGRESS" || r.status === "PENDING";
  const selectedRunCancellable = timeline?.stages.some((s) => s.status === "IN_PROGRESS" || s.status === "PENDING");

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
        subtitle="Real-time log of every agent stage execution recorded in the system — click a row to view its timeline"
        action={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search stage or chat id…"
                className="bg-transparent border border-slate-200 dark:border-slate-700 rounded pl-7 pr-2 py-1.5 text-sm w-48"
              />
            </div>
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
            <RefreshButton
              onClick={() => load(page, statusFilter, search, sortBy, sortDir)}
              loading={loading}
              live={isLiveFilter}
            />
          </div>
        }
      >
        {loading && runs.length === 0 ? (
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
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("status")}>
                        Status <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("tokens")}>
                        Tokens <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("cost")}>
                        Cost <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("created_at")}>
                        When <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr
                      key={r.id}
                      className="border-t border-slate-100 dark:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                      onClick={() => openTimeline(r.chat_id)}
                    >
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
                      <td className="px-3 py-2">
                        {isCancellable(r) && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openTimeline(r.chat_id);
                            }}
                            className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:underline"
                          >
                            <Ban className="h-3 w-3" /> Manage
                          </button>
                        )}
                      </td>
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

      {selectedChatId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={closeTimeline}>
          <div
            className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold">Run Timeline</h3>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">{selectedChatId}</p>
              </div>
              <button onClick={closeTimeline} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800">
                <X className="h-4 w-4" />
              </button>
            </div>

            {timelineLoading ? (
              <LoadingState />
            ) : timelineError ? (
              <div className="text-sm text-red-500 py-4 text-center">{timelineError}</div>
            ) : timeline && timeline.stages.length > 0 ? (
              <div className="space-y-4">
                {selectedRunCancellable && (
                  <div className="flex items-center justify-between rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-500/10 px-3 py-2">
                    <span className="text-xs text-amber-700 dark:text-amber-400">This run is still active.</span>
                    <button
                      onClick={handleCancel}
                      disabled={cancelling}
                      className="inline-flex items-center gap-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-md px-2.5 py-1.5 disabled:opacity-50"
                    >
                      <Ban className="h-3 w-3" /> {cancelling ? "Cancelling…" : "Cancel run"}
                    </button>
                  </div>
                )}
                {cancelResult && <p className="text-xs text-muted-foreground">{cancelResult}</p>}
                <ol className="relative border-l border-slate-200 dark:border-slate-700 ml-2 space-y-4">
                  {timeline.stages.map((s) => (
                    <li key={s.id} className="ml-4">
                      <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-indigo-500" />
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{s.stage_name}</span>
                        <StatusBadge status={s.status} />
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {formatRelativeTime(s.created_at)} · {s.tokens.toLocaleString()} tokens · ${s.cost.toFixed(4)}
                      </p>
                      {s.error_message && <p className="text-xs text-red-500 mt-1">{s.error_message}</p>}
                    </li>
                  ))}
                </ol>
              </div>
            ) : (
              <EmptyState label="No stages recorded for this run." />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
