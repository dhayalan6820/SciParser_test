import * as React from "react";
import { sciparserApi, AdminAnalytics } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState } from "./shared";
import { Activity, CheckCircle2, XCircle, Gauge } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { useTheme } from "../../../contexts/ThemeContext";

const RANGE_OPTIONS = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
  { value: 365, label: "Last 1 year" },
];

export const AnalyticsTab: React.FC = () => {
  const { theme } = useTheme();
  const [analytics, setAnalytics] = React.useState<AdminAnalytics | null>(null);
  const [days, setDays] = React.useState(30);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetAnalytics(days);
        if (!cancelled) setAnalytics(res);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load analytics");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days]);

  if (loading) return <LoadingState />;
  if (error || !analytics) return <div className="text-sm text-red-500">{error || "No data"}</div>;

  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const textColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    background: theme === "dark" ? "#0f172a" : "#fff",
    border: `1px solid ${gridColor}`,
    borderRadius: 8,
    fontSize: 12,
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Analytics</h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1.5 text-sm"
        >
          {RANGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Activity className="h-4 w-4" />} label="Total Runs" value={analytics.total_runs.toLocaleString()} />
        <KPICard index={1} icon={<CheckCircle2 className="h-4 w-4" />} label="Successful" value={analytics.total_success.toLocaleString()} />
        <KPICard index={2} icon={<XCircle className="h-4 w-4" />} label="Failed" value={analytics.total_failed.toLocaleString()} />
        <KPICard index={3} icon={<Gauge className="h-4 w-4" />} label="Success Rate" value={`${analytics.overall_success_rate}%`} />
      </div>

      <Panel title="Runs Over Time" subtitle="Total agent runs per day, broken down by success vs failure">
        {analytics.daily_runs.length === 0 ? (
          <EmptyState label="No runs recorded in this period." />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.daily_runs}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="success" name="Success" stackId="runs" fill="#22c55e" radius={[0, 0, 0, 0]} />
                <Bar dataKey="failed" name="Failed" stackId="runs" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      <Panel title="Token Consumption Over Time" subtitle="Total tokens used per day across all agent runs">
        {analytics.daily_tokens.length === 0 ? (
          <EmptyState label="No token usage recorded in this period." />
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.daily_tokens}>
                <defs>
                  <linearGradient id="analyticsTokensGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#6366f1" fill="url(#analyticsTokensGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      <Panel title="Browser Session Volume Over Time" subtitle="Distinct agent-driven sessions (chats) started per day">
        {analytics.daily_sessions.length === 0 ? (
          <EmptyState label="No browser sessions recorded in this period." />
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.daily_sessions}>
                <defs>
                  <linearGradient id="analyticsSessionsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="sessions" name="Sessions" stroke="#f59e0b" fill="url(#analyticsSessionsGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
    </div>
  );
};
