import * as React from "react";
import { sciparserApi, OperationsMetrics } from "../../../api";
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
        <StatCard icon={<Cpu className="h-4 w-4 text-indigo-500" />} label="Total Tokens" value={metrics.total_tokens.toLocaleString()} />
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
