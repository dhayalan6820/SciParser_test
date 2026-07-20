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
  const [costData, setCostData] = React.useState<any>(null);
  const [modelData, setModelData] = React.useState<any>(null);
  const [contextData, setContextData] = React.useState<any>(null);
  const [retrievalData, setRetrievalData] = React.useState<any>(null);
  const [days, setDays] = React.useState(30);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [an, cd, md, ctx, ret] = await Promise.all([
          sciparserApi.adminGetAnalytics(days),
          sciparserApi.adminGetCostAnalytics(days),
          sciparserApi.adminGetModelAnalytics(days),
          sciparserApi.adminGetContextAnalytics(days),
          sciparserApi.adminGetRetrievalAnalytics(days),
        ]);
        if (!cancelled) {
          setAnalytics(an);
          setCostData(cd);
          setModelData(md);
          setContextData(ctx);
          setRetrievalData(ret);
        }
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

      {/* Model Performance & Cost breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Active Model Performance" subtitle="Requests, latency, and success rates by model name">
          <div className="space-y-3">
            {modelData?.models?.length === 0 ? (
              <EmptyState label="No active model requests logged." />
            ) : (
              modelData?.models?.map((m: any) => (
                <div key={m.model_name} className="flex flex-col border border-slate-200 dark:border-slate-800 p-3 rounded-lg bg-white dark:bg-slate-900">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">{m.model_name}</span>
                    <span className="text-xs font-medium px-2 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">{m.requests} runs</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-center text-xs">
                    <div>
                      <p className="text-muted-foreground">Success</p>
                      <p className="font-semibold text-emerald-500">{m.success_rate}%</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Latency</p>
                      <p className="font-semibold">{m.avg_latency_ms}ms</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Cost/Run</p>
                      <p className="font-semibold">${m.avg_cost.toFixed(4)}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>

        <Panel title="Cost Breakdown by Category" subtitle="Feature cost distribution for the platform">
          <div className="space-y-3">
            {costData?.breakdown?.map((c: any) => (
              <div key={c.category} className="flex justify-between items-center p-2.5 border-b border-slate-100 dark:border-slate-800">
                <span className="text-xs capitalize font-medium">{c.category}</span>
                <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">${c.cost.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Context Window & Retrieval Analytics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Context Analytics" subtitle="Context sizes and summarization stats">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Avg Prompt Size</span>
              <span className="text-xs font-semibold">{contextData?.avg_prompt_size_tokens?.toLocaleString()} tokens</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Avg Memory Size</span>
              <span className="text-xs font-semibold">{contextData?.avg_memory_size_tokens?.toLocaleString()} tokens</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Context Window Utilization</span>
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">{contextData?.window_utilization_percent}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Memory Pruning Events</span>
              <span className="text-xs font-semibold">{contextData?.summarization_events} times</span>
            </div>
          </div>
        </Panel>

        <Panel title="Retrieval & Vector Search" subtitle="Embeddings, recall/precision rates">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Embedding API Calls</span>
              <span className="text-xs font-semibold">{retrievalData?.embedding_calls} calls</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Vector Searches Run</span>
              <span className="text-xs font-semibold">{retrievalData?.vector_searches} searches</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Estimated Precision</span>
              <span className="text-xs font-semibold text-blue-500">{((retrievalData?.avg_precision ?? 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium">Estimated Recall</span>
              <span className="text-xs font-semibold text-emerald-500">{((retrievalData?.avg_recall ?? 0) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Token Consumption Over Time" subtitle="Total tokens used per day across all agent runs">
        {analytics.daily_tokens.length === 0 ? (
          <EmptyState label="No token usage recorded in this period." />
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.daily_tokens}>
                <defs>
                  <linearGradient id="analyticsTokensGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#10b981" fill="url(#analyticsTokensGrad)" strokeWidth={2} />
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
