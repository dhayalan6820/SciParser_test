import * as React from "react";
import { sciparserApi, AdminAutomation } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime, useAutoRefresh, RefreshButton } from "./shared";
import { Calendar, CheckCircle2, XCircle, Repeat, Search, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 15;
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "title", label: "Title" },
  { value: "status", label: "Status" },
  { value: "total_runs", label: "Runs" },
  { value: "success_rate", label: "Success Rate" },
  { value: "last_run", label: "Last Run" },
  { value: "next_run", label: "Next Run" },
];

export const AutomationMonitoringTab: React.FC = () => {
  const [automations, setAutomations] = React.useState<AdminAutomation[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [searchInput, setSearchInput] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [sortBy, setSortBy] = React.useState("last_run");
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [summary, setSummary] = React.useState({ totalRuns: 0, totalSuccess: 0, totalFailed: 0, active: 0 });

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(async (pageArg: number, searchArg: string, sortByArg: string, sortDirArg: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.adminGetAutomations(pageArg, PAGE_SIZE, searchArg || undefined, sortByArg, sortDirArg);
      setAutomations(res.automations);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load automations");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load(page, search, sortBy, sortDir);
  }, [page, search, sortBy, sortDir, load]);

  React.useEffect(() => {
    const handle = setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 350);
    return () => clearTimeout(handle);
  }, [searchInput]);

  const loadSummary = React.useCallback(async () => {
    try {
      const res = await sciparserApi.adminGetAutomations(1, 100);
      const all = res.automations;
      setSummary({
        totalRuns: all.reduce((sum, a) => sum + a.total_runs, 0),
        totalSuccess: all.reduce((sum, a) => sum + a.success_runs, 0),
        totalFailed: all.reduce((sum, a) => sum + a.failed_runs, 0),
        active: all.filter((a) => a.status === "active").length,
      });
    } catch {
      // summary is best-effort; ignore failures
    }
  }, []);

  React.useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const refreshAll = React.useCallback(() => {
    load(page, search, sortBy, sortDir);
    loadSummary();
  }, [load, loadSummary, page, search, sortBy, sortDir]);

  useAutoRefresh(refreshAll, 20000, true);

  const toggleSort = (value: string) => {
    if (sortBy === value) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(value);
      setSortDir("desc");
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Repeat className="h-4 w-4" />} label="Active Schedules" value={summary.active.toLocaleString()} />
        <KPICard index={1} icon={<Calendar className="h-4 w-4" />} label="Total Runs" value={summary.totalRuns.toLocaleString()} />
        <KPICard index={2} icon={<CheckCircle2 className="h-4 w-4" />} label="Successful Runs" value={summary.totalSuccess.toLocaleString()} />
        <KPICard index={3} icon={<XCircle className="h-4 w-4" />} label="Failed Runs" value={summary.totalFailed.toLocaleString()} />
      </div>

      <Panel
        title="Automations"
        subtitle="Every scheduled/automated job and its execution history"
        action={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search title…"
                className="bg-transparent border border-slate-200 dark:border-slate-700 rounded pl-7 pr-2 py-1.5 text-sm w-44"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  Sort: {opt.label}
                </option>
              ))}
            </select>
            <button
              onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
              className="p-1.5 rounded border border-slate-200 dark:border-slate-700"
              title="Toggle sort direction"
            >
              <ArrowUpDown className="h-3.5 w-3.5" />
            </button>
            <RefreshButton onClick={refreshAll} loading={loading} live />
          </div>
        }
      >
        {loading && automations.length === 0 ? (
          <LoadingState />
        ) : error ? (
          <div className="text-sm text-red-500 py-6 text-center">{error}</div>
        ) : automations.length === 0 ? (
          <EmptyState label="No automations have been created yet." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Title</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("status")}>
                        Status <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("total_runs")}>
                        Runs <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("success_rate")}>
                        Success Rate <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("last_run")}>
                        Last Run <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                    <th className="px-3 py-2 font-medium">
                      <button className="flex items-center gap-1" onClick={() => toggleSort("next_run")}>
                        Next Run <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {automations.map((a) => (
                    <tr key={a.schedule_id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-medium">{a.title || a.schedule_id.slice(0, 8)}</td>
                      <td className="px-3 py-2 text-muted-foreground">{a.schedule_type}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={a.status} />
                      </td>
                      <td className="px-3 py-2">
                        {a.total_runs} <span className="text-muted-foreground">({a.success_runs} ok / {a.failed_runs} failed)</span>
                      </td>
                      <td className="px-3 py-2">{a.success_rate}%</td>
                      <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(a.last_run)}</td>
                      <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(a.next_run)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-4 text-xs text-muted-foreground">
              <span>
                Page {page} of {totalPages} · {total} total automations
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
