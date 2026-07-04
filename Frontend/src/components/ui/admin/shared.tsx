import * as React from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react";
import { cn } from "../../../../lib/utils";

export function useDocumentVisible(): boolean {
  const [visible, setVisible] = React.useState(() => typeof document === "undefined" || document.visibilityState === "visible");

  React.useEffect(() => {
    const handler = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, []);

  return visible;
}

export function useAutoRefresh(callback: () => void, intervalMs: number, enabled: boolean = true) {
  const savedCallback = React.useRef(callback);
  const isVisible = useDocumentVisible();

  React.useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  React.useEffect(() => {
    if (!enabled || !isVisible) return;
    const interval = setInterval(() => savedCallback.current(), intervalMs);
    return () => clearInterval(interval);
  }, [enabled, isVisible, intervalMs]);
}

export const RefreshButton: React.FC<{ onClick: () => void; loading?: boolean; live?: boolean }> = ({ onClick, loading, live }) => (
  <button
    onClick={onClick}
    disabled={loading}
    title={live ? "Auto-refreshing — click to refresh now" : "Refresh now"}
    className="inline-flex items-center gap-1.5 text-xs font-medium rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/60 disabled:opacity-50"
  >
    <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
    {live && <span className="relative flex h-1.5 w-1.5">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
    </span>}
  </button>
);

export const fadeIn = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
};

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.round(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

export const Sparkline: React.FC<{ data: number[]; color?: string }> = ({ data, color = "#6366f1" }) => {
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <div className="h-10 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`spark-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#spark-${color.replace("#", "")})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export const KPICard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  change?: number;
  sparkline?: number[];
  sparklineColor?: string;
  index?: number;
}> = ({ icon, label, value, change, sparkline, sparklineColor = "#6366f1", index = 0 }) => {
  const isPositive = (change ?? 0) > 0;
  const isNeutral = change === undefined || change === 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-4 shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            {icon}
          </span>
          {label}
        </div>
        {sparkline && sparkline.length > 1 && <Sparkline data={sparkline} color={sparklineColor} />}
      </div>
      <div className="mt-3 flex items-end justify-between">
        <span className="text-2xl font-semibold tracking-tight">{value}</span>
        {!isNeutral && (
          <span
            className={cn(
              "flex items-center gap-0.5 text-xs font-medium rounded-full px-1.5 py-0.5",
              isPositive
                ? "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10"
                : "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10"
            )}
          >
            {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {Math.abs(change ?? 0).toFixed(1)}%
          </span>
        )}
        {isNeutral && (
          <span className="flex items-center gap-0.5 text-xs font-medium text-muted-foreground">
            <Minus className="h-3 w-3" />
          </span>
        )}
      </div>
    </motion.div>
  );
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const norm = (status || "").toUpperCase();
  const map: Record<string, string> = {
    SUCCESS: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    COMPLETED: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    DONE: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    FAILED: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    ERROR: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    FAILURE: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    IN_PROGRESS: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    RUNNING: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    PENDING: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    ACTIVE: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    SUSPENDED: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  };
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium", map[norm] || "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300")}>
      {status}
    </span>
  );
};

export const Panel: React.FC<{ title?: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode; className?: string }> = ({
  title,
  subtitle,
  action,
  children,
  className,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3 }}
    className={cn("rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-4 shadow-sm", className)}
  >
    {(title || action) && (
      <div className="flex items-center justify-between mb-3">
        <div>
          {title && <h3 className="text-sm font-semibold">{title}</h3>}
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
    )}
    {children}
  </motion.div>
);

export const EmptyState: React.FC<{ label: string }> = ({ label }) => (
  <div className="py-10 text-center text-sm text-muted-foreground">{label}</div>
);

export const LoadingState: React.FC = () => (
  <div className="py-10 text-center text-sm text-muted-foreground animate-pulse">Loading…</div>
);
