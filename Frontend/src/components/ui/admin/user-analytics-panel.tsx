import * as React from "react";
import { sciparserApi, AdminUserAnalytics, User } from "../../../api";
import { motion } from "framer-motion";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime } from "./shared";
import { X, DollarSign, Gauge, Activity, Zap, ListChecks, Coins } from "lucide-react";
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
} from "recharts";
import { useTheme } from "../../../contexts/ThemeContext";

const RANGE_OPTIONS = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

export const UserAnalyticsPanel: React.FC<{ user: User; onClose: () => void; isSelf?: boolean }> = ({ user, onClose, isSelf = false }) => {
  const { theme } = useTheme();
  const [days, setDays] = React.useState(30);
  const [data, setData] = React.useState<AdminUserAnalytics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = isSelf
          ? await sciparserApi.getMyUserAnalytics(days)
          : await sciparserApi.adminGetUserAnalytics(user.user_id, days);
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load analytics");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user.user_id, days, isSelf]);

  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";
  const textColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const tooltipStyle = {
    background: theme === "dark" ? "#0f172a" : "#fff",
    border: `1px solid ${gridColor}`,
    borderRadius: 8,
    fontSize: 12,
  };

  return (
    <div
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 15 }}
        transition={{ type: "spring", damping: 28, stiffness: 280 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-5xl max-h-[90vh] bg-background border border-slate-205 dark:border-slate-800 rounded-[24px] shadow-[0_24px_80px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden"
      >
        {/* Sticky Header */}
        <div className="sticky top-0 z-10 bg-background border-b border-slate-200 dark:border-slate-800 px-6 py-4.5 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-850 dark:text-white flex items-center gap-1.5">
              <Activity className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
              {user.username}'s Usage &amp; Analytics
            </h2>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-transparent border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-semibold focus:outline-none cursor-pointer focus:border-emerald-500"
            >
              {RANGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-all cursor-pointer"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-left">
          {loading ? (
            <LoadingState />
          ) : error || !data ? (
            <div className="text-sm text-red-500 py-6 text-center">{error || "No data available."}</div>
          ) : (
            <>
              {/* KPI Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <KPICard index={0} icon={<Zap className="h-4.5 w-4.5 text-emerald-500" />} label="Total Tokens" value={data.total_tokens.toLocaleString()} />
                <KPICard index={1} icon={<DollarSign className="h-4.5 w-4.5 text-blue-500" />} label="Total Cost" value={`$${data.total_cost.toFixed(4)}`} />
                <KPICard index={2} icon={<Gauge className="h-4.5 w-4.5 text-indigo-500" />} label="Success Rate" value={`${data.success_rate}%`} />
                <KPICard index={3} icon={<Activity className="h-4.5 w-4.5 text-purple-500" />} label="Total Runs" value={data.total_runs.toLocaleString()} />
                <KPICard index={4} icon={<Coins className="h-4.5 w-4.5 text-amber-500" />} label="Credit Balance" value={data.credit_balance.toFixed(2)} />
              </div>

              {/* Charts Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Panel title="Usage & Cost" subtitle={`Tokens and cost per day over the last ${data.days} days`}>
                  {data.daily_usage.length === 0 ? (
                    <EmptyState label="No usage recorded in this period." />
                  ) : (
                    <div className="h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.daily_usage}>
                          <defs>
                            <linearGradient id="userTokensGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                              <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                          <XAxis dataKey="date" tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} />
                          <Tooltip contentStyle={tooltipStyle} />
                          <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#10b981" fill="url(#userTokensGrad)" strokeWidth={2} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Panel>

                <Panel title="Run Outcomes" subtitle="Agent run status breakdown for this user">
                  {data.status_breakdown.length === 0 ? (
                    <EmptyState label="No runs recorded in this period." />
                  ) : (
                    <div className="h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data.status_breakdown}>
                          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                          <XAxis dataKey="status" tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: textColor }} axisLine={false} tickLine={false} allowDecimals={false} />
                          <Tooltip contentStyle={tooltipStyle} />
                          <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Panel>
              </div>

              {/* Activity & Conversations Tables */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Panel title="Activity" subtitle="Sessions, messages, and recent successful logins">
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="rounded-lg border border-slate-205 dark:border-slate-800 p-3">
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Last Active</div>
                      <div className="text-sm font-semibold mt-1">{formatRelativeTime(data.activity.last_active)}</div>
                    </div>
                    <div className="rounded-lg border border-slate-205 dark:border-slate-800 p-3">
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Sessions</div>
                      <div className="text-sm font-semibold mt-1">{data.activity.total_sessions.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg border border-slate-205 dark:border-slate-800 p-3">
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Messages</div>
                      <div className="text-sm font-semibold mt-1">{data.activity.total_messages.toLocaleString()}</div>
                    </div>
                  </div>
                  {data.activity.recent_logins.length === 0 ? (
                    <EmptyState label="No recent logins recorded." />
                  ) : (
                    <ul className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                      {data.activity.recent_logins.map((l, i) => (
                        <li key={i} className="flex items-center justify-between text-xs text-muted-foreground border-t border-slate-100 dark:border-slate-800 pt-1.5 first:border-t-0 first:pt-0">
                          <span>Login</span>
                          <span>{formatRelativeTime(l.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Panel>

                <Panel title="Conversations" subtitle="Per-conversation token usage and cost, most expensive first">
                  {data.conversations.length === 0 ? (
                    <EmptyState label="No conversations with recorded usage yet." />
                  ) : (
                    <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                      {[...data.conversations]
                        .sort((a, b) => b.total_cost - a.total_cost)
                        .map((c) => (
                          <div
                            key={c.chat_id}
                            className="flex items-center justify-between rounded-lg border border-slate-205 dark:border-slate-800 px-3 py-2 text-xs"
                          >
                            <div>
                              <div className="font-semibold text-slate-800 dark:text-slate-200">{c.chat_id.replace(/^thread-/, "").slice(0, 8)}</div>
                              <div className="text-muted-foreground mt-0.5">
                                {c.total_tokens.toLocaleString()} tokens ({c.input_tokens.toLocaleString()} in /{" "}
                                {c.output_tokens.toLocaleString()} out)
                              </div>
                            </div>
                            <span className="shrink-0 rounded-lg border border-slate-205 dark:border-slate-800 bg-card px-2.5 py-1 font-bold text-foreground">
                              ${c.total_cost.toFixed(4)}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </Panel>
              </div>

              {/* Automations */}
              <Panel
                title="Automations"
                subtitle={`${data.automations.total} scheduled task${data.automations.total === 1 ? "" : "s"} · ${data.automations.active} active`}
                action={
                  <div className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                    <ListChecks className="h-3.5 w-3.5 text-emerald-500" />
                    {data.automations.success_rate}% success
                  </div>
                }
              >
                {data.automations.items.length === 0 ? (
                  <EmptyState label="No automations for this user." />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[200px] overflow-y-auto pr-1">
                    {data.automations.items.map((a) => (
                      <div
                        key={a.schedule_id}
                        className="flex items-center justify-between rounded-lg border border-slate-205 dark:border-slate-800 px-3 py-2 text-xs"
                      >
                        <div>
                          <div className="font-semibold text-slate-800 dark:text-slate-200">{a.title || a.schedule_id.slice(0, 8)}</div>
                          <div className="text-muted-foreground mt-0.5">
                            {a.total_runs} runs · {a.success_rate}% success
                          </div>
                        </div>
                        <StatusBadge status={a.status} />
                      </div>
                    ))}
                  </div>
                )}
              </Panel>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
};
