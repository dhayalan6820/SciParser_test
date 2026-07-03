import * as React from "react";
import { Button } from "./button";
import { Input } from "./input";
import { sciparserApi, User, OperationsMetrics } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import {
  Shield,
  Users,
  Activity,
  Search,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Ban,
  RotateCcw,
  Trash2,
  LogOut,
  DollarSign,
  Cpu,
  TrendingUp,
  TrendingDown,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
} from "lucide-react";

interface AdminDashboardProps {
  currentUser: { username: string; email: string } | null;
  onLogout: () => void;
}

type Tab = "users" | "operations";

const PAGE_SIZE = 10;

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ currentUser, onLogout }) => {
  const { theme, toggleTheme } = useTheme();
  const [tab, setTab] = React.useState<Tab>("users");

  return (
    <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-indigo-500" />
          <h1 className="text-lg font-semibold">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          {currentUser && (
            <span className="text-sm text-muted-foreground hidden sm:inline">
              {currentUser.username}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={toggleTheme}
            className="h-8 w-8 p-0"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="sm" onClick={onLogout} className="gap-1.5">
            <LogOut className="h-4 w-4" />
            Log out
          </Button>
        </div>
      </header>

      <nav className="flex items-center gap-1 px-6 pt-3 border-b border-slate-200 dark:border-slate-800">
        <TabButton active={tab === "users"} onClick={() => setTab("users")} icon={<Users className="h-4 w-4" />}>
          User Management
        </TabButton>
        <TabButton active={tab === "operations"} onClick={() => setTab("operations")} icon={<Activity className="h-4 w-4" />}>
          Operations
        </TabButton>
      </nav>

      <div className="flex-1 overflow-y-auto p-6">
        {tab === "users" ? <UsersTab currentUsername={currentUser?.username} /> : <OperationsTab />}
      </div>
    </div>
  );
};

const TabButton: React.FC<{ active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }> = ({
  active,
  onClick,
  icon,
  children,
}) => (
  <button
    onClick={onClick}
    className={cn(
      "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
      active
        ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
        : "border-transparent text-muted-foreground hover:text-foreground"
    )}
  >
    {icon}
    {children}
  </button>
);

const UsersTab: React.FC<{ currentUsername?: string }> = ({ currentUsername }) => {
  const [users, setUsers] = React.useState<User[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [busyUserId, setBusyUserId] = React.useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadUsers = React.useCallback(async (pageArg: number, searchArg: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.adminListUsers(pageArg, PAGE_SIZE, searchArg || undefined);
      setUsers(res.users);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadUsers(page, search);
  }, [page, loadUsers]);

  React.useEffect(() => {
    const handle = setTimeout(() => {
      setPage(1);
      loadUsers(1, search);
    }, 350);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const runAction = async (userId: string, fn: () => Promise<any>) => {
    setBusyUserId(userId);
    setActionError(null);
    try {
      await fn();
      await loadUsers(page, search);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyUserId(null);
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by username or email"
            className="pl-9"
          />
        </div>
        <span className="text-sm text-muted-foreground">{total} user{total === 1 ? "" : "s"}</span>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/40 rounded-lg text-red-600 dark:text-red-400 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Username</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Joined</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
                  Loading users...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-red-500">
                  {error}
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  No users found.
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const isSelf = u.username === currentUsername;
                const isBusy = busyUserId === u.user_id;
                return (
                  <tr key={u.user_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-4 py-3 font-medium">
                      {u.username} {isSelf && <span className="text-xs text-muted-foreground">(you)</span>}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        disabled={isSelf || isBusy}
                        onChange={(e) =>
                          runAction(u.user_id, () =>
                            sciparserApi.adminUpdateUser(u.user_id, { role: e.target.value as "admin" | "user" })
                          )
                        }
                        className="bg-transparent border border-slate-200 dark:border-slate-700 rounded px-2 py-1 text-xs disabled:opacity-50"
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                          u.status === "active"
                            ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400"
                            : "bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400"
                        )}
                      >
                        {u.status === "active" ? <CheckCircle2 className="h-3 w-3" /> : <Ban className="h-3 w-3" />}
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        {isBusy ? (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : (
                          <>
                            {u.status === "active" ? (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isSelf}
                                onClick={() =>
                                  runAction(u.user_id, () =>
                                    sciparserApi.adminUpdateUser(u.user_id, { status: "suspended" })
                                  )
                                }
                                className="h-7 px-2 text-xs gap-1"
                              >
                                <Ban className="h-3 w-3" />
                                Suspend
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  runAction(u.user_id, () =>
                                    sciparserApi.adminUpdateUser(u.user_id, { status: "active" })
                                  )
                                }
                                className="h-7 px-2 text-xs gap-1"
                              >
                                <RotateCcw className="h-3 w-3" />
                                Reactivate
                              </Button>
                            )}
                            {confirmDeleteId === u.user_id ? (
                              <div className="flex items-center gap-1">
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={() => runAction(u.user_id, () => sciparserApi.adminDeleteUser(u.user_id))}
                                  className="h-7 px-2 text-xs"
                                >
                                  Confirm
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="h-7 px-2 text-xs"
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isSelf}
                                onClick={() => setConfirmDeleteId(u.user_id)}
                                className="h-7 px-2 text-xs gap-1 text-red-500 hover:text-red-600"
                              >
                                <Trash2 className="h-3 w-3" />
                                Delete
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {!loading && total > 0 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-8 px-2"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="h-8 px-2"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

const OperationsTab: React.FC = () => {
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
