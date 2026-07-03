import * as React from "react";
import { sciparserApi, AdminOverview, AdminActivityItem } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime, fadeIn } from "./shared";
import { motion } from "framer-motion";
import {
  Users,
  Activity,
  Bot,
  Calendar,
  Coins,
  DollarSign,
  UserPlus,
  Clock,
  AlertTriangle,
} from "lucide-react";

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  user_signup: <UserPlus className="h-3.5 w-3.5" />,
  automation_run: <Calendar className="h-3.5 w-3.5" />,
  agent_failure: <AlertTriangle className="h-3.5 w-3.5" />,
};

export const OverviewTab: React.FC = () => {
  const [overview, setOverview] = React.useState<AdminOverview | null>(null);
  const [activity, setActivity] = React.useState<AdminActivityItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [ov, act] = await Promise.all([
          sciparserApi.adminGetOverviewMetrics(30),
          sciparserApi.adminGetActivity(15),
        ]);
        if (!cancelled) {
          setOverview(ov);
          setActivity(act.items);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load overview");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <LoadingState />;
  if (error || !overview) return <div className="text-sm text-red-500">{error || "No data"}</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <motion.div {...fadeIn} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          index={0}
          icon={<Users className="h-4 w-4" />}
          label="Total Users"
          value={overview.total_users.toLocaleString()}
        />
        <KPICard
          index={1}
          icon={<Activity className="h-4 w-4" />}
          label="Total Runs (30d)"
          value={overview.total_runs.toLocaleString()}
          change={overview.total_runs_change}
          sparkline={overview.runs_sparkline}
          sparklineColor="#6366f1"
        />
        <KPICard
          index={2}
          icon={<Coins className="h-4 w-4" />}
          label="Tokens Used (30d)"
          value={overview.total_tokens.toLocaleString()}
          change={overview.total_tokens_change}
          sparkline={overview.tokens_sparkline}
          sparklineColor="#8b5cf6"
        />
        <KPICard
          index={3}
          icon={<DollarSign className="h-4 w-4" />}
          label="Cost (30d)"
          value={`$${overview.total_cost.toFixed(2)}`}
          change={overview.total_cost_change}
        />
        <KPICard
          index={4}
          icon={<Bot className="h-4 w-4" />}
          label="Agents Running Now"
          value={overview.running_agents.toLocaleString()}
        />
        <KPICard
          index={5}
          icon={<Calendar className="h-4 w-4" />}
          label="Automations Completed (30d)"
          value={overview.completed_automations.toLocaleString()}
        />
        <KPICard
          index={6}
          icon={<Users className="h-4 w-4" />}
          label="Active Users"
          value={overview.active_users.toLocaleString()}
        />
        <KPICard
          index={7}
          icon={<Activity className="h-4 w-4" />}
          label="Success Rate (30d)"
          value={`${overview.success_rate}%`}
          change={overview.success_rate_change}
        />
      </motion.div>

      <Panel title="Recent Activity" subtitle="Live feed of signups, automation runs, and agent failures">
        {activity.length === 0 ? (
          <EmptyState label="No recent activity." />
        ) : (
          <ol className="relative border-l border-slate-200 dark:border-slate-800 ml-2 space-y-4">
            {activity.map((item, idx) => (
              <motion.li
                key={idx}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.03 }}
                className="ml-4"
              >
                <span className="absolute -left-[7px] flex h-3.5 w-3.5 items-center justify-center rounded-full bg-indigo-500 ring-4 ring-white dark:ring-slate-900" />
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground mt-0.5">{ACTIVITY_ICONS[item.type] || <Clock className="h-3.5 w-3.5" />}</span>
                    <div>
                      <p className="text-sm font-medium">{item.title}</p>
                      {item.detail && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{item.detail}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {item.status && <StatusBadge status={item.status} />}
                    <span className="text-xs text-muted-foreground whitespace-nowrap">{formatRelativeTime(item.timestamp)}</span>
                  </div>
                </div>
              </motion.li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
};
