import * as React from "react";
import { Button } from "../button";
import { Input } from "../input";
import { sciparserApi, AppLogEntry, AppLogFilters } from "../../../api";
import { cn } from "../../../../lib/utils";
import {
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Filter,
  ScrollText,
} from "lucide-react";

const LOG_PAGE_SIZE = 50;

const LEVEL_STYLES: Record<string, string> = {
  ERROR: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400",
  CRITICAL: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400",
  WARNING: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
  INFO: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  DEBUG: "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
};

export const LogsTab: React.FC = () => {
  const [logs, setLogs] = React.useState<AppLogEntry[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [level, setLevel] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");

  const totalPages = Math.max(1, Math.ceil(total / LOG_PAGE_SIZE));

  const buildFilters = React.useCallback(
    (
      pageArg: number,
      overrides?: Partial<{ level: string; search: string; startDate: string; endDate: string }>
    ): AppLogFilters => {
      const merged = { level, search, startDate, endDate, ...overrides };
      return {
        page: pageArg,
        pageSize: LOG_PAGE_SIZE,
        level: merged.level || undefined,
        search: merged.search || undefined,
        startDate: merged.startDate || undefined,
        endDate: merged.endDate || undefined,
      };
    },
    [level, search, startDate, endDate]
  );

  const loadLogs = React.useCallback(
    async (
      pageArg: number,
      overrides?: Partial<{ level: string; search: string; startDate: string; endDate: string }>
    ) => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetAppLogs(buildFilters(pageArg, overrides));
        setLogs(res.logs);
        setTotal(res.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load application logs");
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
    setLevel("");
    setSearch("");
    setStartDate("");
    setEndDate("");
    setPage(1);
    loadLogs(1, { level: "", search: "", startDate: "", endDate: "" });
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold flex items-center gap-1.5">
          <ScrollText className="h-4 w-4" /> Application Logs
        </h2>
      </div>

      <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-medium flex items-center gap-1.5">
            <Filter className="h-4 w-4" /> Recent Log Lines
          </h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
          >
            <option value="">Any level</option>
            <option value="DEBUG">Debug</option>
            <option value="INFO">Info</option>
            <option value="WARNING">Warning</option>
            <option value="ERROR">Error</option>
            <option value="CRITICAL">Critical</option>
          </select>
          <Input
            placeholder="Search message"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm md:col-span-2"
          />
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-sm" />
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="text-sm" />
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={applyFilters}>Apply Filters</Button>
          <Button size="sm" variant="outline" onClick={clearFilters}>Clear</Button>
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
          <p className="text-xs text-muted-foreground py-6 text-center">No log lines match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-slate-200 dark:border-slate-800">
                  <th className="py-2 pr-3 font-medium">Time</th>
                  <th className="py-2 pr-3 font-medium">Level</th>
                  <th className="py-2 pr-3 font-medium">Logger</th>
                  <th className="py-2 pr-3 font-medium">Message</th>
                  <th className="py-2 pr-3 font-medium">Location</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-slate-100 dark:border-slate-900/60 align-top">
                    <td className="py-2 pr-3 whitespace-nowrap text-xs text-muted-foreground">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={cn(
                          "px-1.5 py-0.5 rounded text-xs font-medium",
                          LEVEL_STYLES[log.level?.toUpperCase()] || LEVEL_STYLES.INFO
                        )}
                      >
                        {log.level}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap">{log.logger_name}</td>
                    <td className="py-2 pr-3 max-w-[420px] break-words">{log.message}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap">
                      {log.module ? `${log.module}${log.func_name ? `:${log.func_name}` : ""}${log.line_no ? `:${log.line_no}` : ""}` : "—"}
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
    </div>
  );
};
