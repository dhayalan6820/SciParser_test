import * as React from "react";
import { sciparserApi, AdminUsage } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState } from "./shared";
import { Coins, Cpu, Sparkles, Trophy } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useTheme } from "../../../contexts/ThemeContext";

export const UsageTab: React.FC = () => {
  const { theme } = useTheme();
  const [usage, setUsage] = React.useState<AdminUsage | null>(null);
  const [days, setDays] = React.useState(30);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetUsage(days);
        if (!cancelled) setUsage(res);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load usage");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days]);

  if (loading) return <LoadingState />;
  if (error || !usage) return <div className="text-sm text-red-500">{error || "No data"}</div>;

  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const textColor = theme === "dark" ? "#94a3b8" : "#64748b";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Usage Dashboard</h2>
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

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <KPICard index={0} icon={<Cpu className="h-4 w-4" />} label="Prompt Tokens" value={usage.total_prompt_tokens.toLocaleString()} />
        <KPICard index={1} icon={<Sparkles className="h-4 w-4" />} label="Completion Tokens" value={usage.total_completion_tokens.toLocaleString()} />
        <KPICard
          index={2}
          icon={<Coins className="h-4 w-4" />}
          label="Total Tokens"
          value={(usage.total_prompt_tokens + usage.total_completion_tokens).toLocaleString()}
        />
      </div>

      <Panel title="Token Usage Over Time" subtitle="Prompt vs completion tokens per day">
        {usage.daily_usage.length === 0 ? (
          <EmptyState label="No usage recorded in this period." />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usage.daily_usage}>
                <defs>
                  <linearGradient id="promptGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="completionGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: theme === "dark" ? "#0f172a" : "#fff",
                    border: `1px solid ${gridColor}`,
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Area type="monotone" dataKey="prompt_tokens" name="Prompt" stroke="#6366f1" fill="url(#promptGrad)" strokeWidth={2} />
                <Area type="monotone" dataKey="completion_tokens" name="Completion" stroke="#22c55e" fill="url(#completionGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      <Panel title="Top Users by Usage" subtitle="Highest token consumption in the selected period">
        {usage.top_users.length === 0 ? (
          <EmptyState label="No usage recorded in this period." />
        ) : (
          <div className="space-y-2">
            {usage.top_users.map((u, idx) => (
              <div key={u.user_id} className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
                <div className="flex items-center gap-2">
                  {idx === 0 && <Trophy className="h-3.5 w-3.5 text-amber-500" />}
                  <span className="font-medium">{u.username}</span>
                  <span className="text-xs text-muted-foreground">{u.runs} runs</span>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-muted-foreground">{u.tokens.toLocaleString()} tokens</span>
                  <span className="font-medium">${u.cost.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
};
