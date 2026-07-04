import * as React from "react";
import { sciparserApi, AdminOverview, AdminActivityItem, User } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime, fadeIn } from "./shared";
import { UserAnalyticsPanel } from "./user-analytics-panel";
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
  LogIn,
  ShieldAlert,
  PlayCircle,
  CheckCircle2,
  Search,
  X,
  BarChart3,
} from "lucide-react";

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  user_signup: <UserPlus className="h-3.5 w-3.5" />,
  automation_run: <Calendar className="h-3.5 w-3.5" />,
  agent_failure: <AlertTriangle className="h-3.5 w-3.5" />,
  login: <LogIn className="h-3.5 w-3.5" />,
  login_failed: <ShieldAlert className="h-3.5 w-3.5" />,
  agent_run_started: <PlayCircle className="h-3.5 w-3.5" />,
  agent_run_completed: <CheckCircle2 className="h-3.5 w-3.5" />,
};

const ACTIVITY_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All activity" },
  { value: "user_signup", label: "Signups" },
  { value: "login", label: "Logins" },
  { value: "login_failed", label: "Failed logins" },
  { value: "automation_run", label: "Automation runs" },
  { value: "agent_run_started", label: "Agent started" },
  { value: "agent_run_completed", label: "Agent completed" },
  { value: "agent_failure", label: "Agent failures" },
];

export const OverviewTab: React.FC = () => {
  const [overview, setOverview] = React.useState<AdminOverview | null>(null);
  const [activity, setActivity] = React.useState<AdminActivityItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [activityLoading, setActivityLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [typeFilter, setTypeFilter] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [userInput, setUserInput] = React.useState("");
  const [userFilter, setUserFilter] = React.useState("");
  const [userSuggestions, setUserSuggestions] = React.useState<User[]>([]);
  const [showUserSuggestions, setShowUserSuggestions] = React.useState(false);
  const [selectedUser, setSelectedUser] = React.useState<User | null>(null);
  const [analyticsUser, setAnalyticsUser] = React.useState<User | null>(null);

  React.useEffect(() => {
    const handle = setTimeout(() => setUserFilter(userInput.trim()), 350);
    return () => clearTimeout(handle);
  }, [userInput]);

  React.useEffect(() => {
    if (selectedUser && userInput.trim() !== selectedUser.username) {
      setSelectedUser(null);
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await sciparserApi.adminListUsers(1, 8, userInput.trim() || undefined);
        if (!cancelled) setUserSuggestions(res.users);
      } catch {
        if (!cancelled) setUserSuggestions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userFilter]);

  const pickUser = (u: User) => {
    setUserInput(u.username);
    setUserFilter(u.username);
    setSelectedUser(u);
    setShowUserSuggestions(false);
  };

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const ov = await sciparserApi.adminGetOverviewMetrics(30);
        if (!cancelled) setOverview(ov);
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

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setActivityLoading(true);
      try {
        const act = await sciparserApi.adminGetActivity(15, {
          startDate: startDate || undefined,
          endDate: endDate || undefined,
          type: typeFilter || undefined,
          user: userFilter || undefined,
        });
        if (!cancelled) setActivity(act.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load activity");
      } finally {
        if (!cancelled) setActivityLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [startDate, endDate, typeFilter, userFilter]);

  const hasActiveFilters = !!(startDate || endDate || typeFilter || userFilter);
  const clearFilters = () => {
    setTypeFilter("");
    setStartDate("");
    setEndDate("");
    setUserInput("");
    setUserFilter("");
    setSelectedUser(null);
    setShowUserSuggestions(false);
  };

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

      <Panel title="Recent Activity" subtitle="Live feed of signups, logins, automation runs, and agent lifecycle events">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Filter by user..."
              value={userInput}
              onChange={(e) => {
                setUserInput(e.target.value);
                setShowUserSuggestions(true);
              }}
              onFocus={() => setShowUserSuggestions(true)}
              onBlur={() => setTimeout(() => setShowUserSuggestions(false), 150)}
              className="pl-8 pr-3 py-1.5 text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent w-52 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              aria-label="Filter by user"
            />
            {showUserSuggestions && userSuggestions.length > 0 && (
              <div className="absolute z-20 mt-1 w-64 max-h-56 overflow-y-auto rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg">
                {userSuggestions.map((u) => (
                  <button
                    key={u.user_id}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => pickUser(u)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800/60 flex flex-col"
                  >
                    <span className="font-medium">{u.username}</span>
                    <span className="text-xs text-muted-foreground">{u.email}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedUser && (
            <button
              onClick={() => setAnalyticsUser(selectedUser)}
              className="flex items-center gap-1.5 text-xs font-medium rounded-md border border-indigo-200 dark:border-indigo-900 text-indigo-600 dark:text-indigo-400 px-2 py-1.5 hover:bg-indigo-50 dark:hover:bg-indigo-500/10"
            >
              <BarChart3 className="h-3.5 w-3.5" /> View analytics for {selectedUser.username}
            </button>
          )}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {ACTIVITY_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="Start date"
          />
          <span className="text-xs text-muted-foreground">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="End date"
          />
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
            >
              <X className="h-3 w-3" /> Clear
            </button>
          )}
        </div>

        {activityLoading ? (
          <LoadingState />
        ) : activity.length === 0 ? (
          <EmptyState label={hasActiveFilters ? "No activity matches these filters." : "No recent activity."} />
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

      {analyticsUser && <UserAnalyticsPanel user={analyticsUser} onClose={() => setAnalyticsUser(null)} />}
    </div>
  );
};
