import * as React from "react";
import { KPICard, Panel, EmptyState } from "../shared";
import { Activity, Coins, Layers, Gauge, ShieldAlert, Cpu } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useTheme } from "../../../../contexts/ThemeContext";

interface OverviewSubtabProps {
  data: any;
}

export const OverviewSubtab: React.FC<OverviewSubtabProps> = ({ data }) => {
  const { theme } = useTheme();

  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const textColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    background: theme === "dark" ? "#0f172a" : "#fff",
    border: `1px solid ${gridColor}`,
    borderRadius: 8,
    fontSize: 12,
  };

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Activity className="h-4 w-4" />} label="Total Agent Runs" value={data.total_runs.toLocaleString()} />
        <KPICard index={1} icon={<Cpu className="h-4 w-4" />} label="Total Tool Calls" value={data.total_tool_calls.toLocaleString()} />
        <KPICard index={2} icon={<Coins className="h-4 w-4" />} label="Total API Cost" value={`$${data.total_cost.toFixed(4)}`} />
        <KPICard index={3} icon={<Gauge className="h-4 w-4" />} label="Success Rate" value={`${data.overall_success_rate}%`} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        <KPICard index={4} icon={<Layers className="h-4 w-4" />} label="Prompt Tokens" value={data.total_prompt_tokens.toLocaleString()} />
        <KPICard index={5} icon={<Layers className="h-4 w-4 text-blue-500" />} label="Completion Tokens" value={data.total_completion_tokens.toLocaleString()} />
        <KPICard index={6} icon={<Layers className="h-4 w-4 text-emerald-500" />} label="Cached Tokens Saved" value={data.total_cached_tokens.toLocaleString()} />
        <KPICard index={7} icon={<Activity className="h-4 w-4 text-purple-500" />} label="Avg Response Time" value={`${data.avg_latency_ms}ms`} />
      </div>

      {/* Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Daily Cost & Usage Trends" subtitle="Cost consumption and run frequency per day">
          {data.daily_trends.length === 0 ? (
            <EmptyState label="No usage trends recorded in this period." />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.daily_trends}>
                  <defs>
                    <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="cost" name="Cost ($)" stroke="#10b981" fill="url(#costGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Daily Token Consumption" subtitle="Tokens processed across all model requests">
          {data.daily_trends.length === 0 ? (
            <EmptyState label="No token trends recorded in this period." />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.daily_trends}>
                  <defs>
                    <linearGradient id="tokensGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: textColor }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#6366f1" fill="url(#tokensGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      {/* Alert Feed */}
      <Panel title="Recent Observability Alerts" subtitle="Automatically detected anomalies, loop storms, and token spikes">
        {data.active_alerts.length === 0 ? (
          <div className="text-xs text-muted-foreground text-center py-6">All systems nominal. No alerts detected.</div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {data.active_alerts.map((alert: any) => (
              <div key={alert.id} className="flex gap-3 py-3 items-start">
                <span className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                  alert.severity === "critical" 
                    ? "bg-red-50 dark:bg-red-950/20 text-red-500 border border-red-500/20" 
                    : "bg-amber-50 dark:bg-amber-950/20 text-amber-500 border border-amber-500/20"
                }`}>
                  <ShieldAlert className="h-4 w-4" />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold">{alert.title}</span>
                    <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded font-bold ${
                      alert.severity === "critical" ? "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400" : "bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400"
                    }`}>
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{alert.message}</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-1">{new Date(alert.created_at).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
};
