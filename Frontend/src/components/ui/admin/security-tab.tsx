import * as React from "react";
import { sciparserApi, AdminSecurity } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime } from "./shared";
import { ShieldAlert, UserPlus, ShieldCheck, LogIn, XOctagon, Search, X } from "lucide-react";

export const SecurityTab: React.FC = () => {
  const [security, setSecurity] = React.useState<AdminSecurity | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [userInput, setUserInput] = React.useState("");
  const [userFilter, setUserFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");

  React.useEffect(() => {
    const handle = setTimeout(() => setUserFilter(userInput.trim()), 350);
    return () => clearTimeout(handle);
  }, [userInput]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetSecurity({
          startDate: startDate || undefined,
          endDate: endDate || undefined,
          user: userFilter || undefined,
          status: statusFilter || undefined,
        });
        if (!cancelled) setSecurity(res);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load security overview");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [startDate, endDate, userFilter, statusFilter]);

  const hasActiveFilters = !!(startDate || endDate || userFilter || statusFilter);
  const clearFilters = () => {
    setStartDate("");
    setEndDate("");
    setUserInput("");
    setUserFilter("");
    setStatusFilter("");
  };

  if (loading) return <LoadingState />;
  if (error || !security) return <div className="text-sm text-red-500">{error || "No data"}</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filter by user..."
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent w-44 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
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
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm rounded-md border border-slate-200 dark:border-slate-800 bg-transparent px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Section filter"
        >
          <option value="">All sections</option>
          <option value="suspended">Suspended accounts</option>
          <option value="signup">Recent signups</option>
          <option value="login">Recent logins</option>
          <option value="login_failed">Failed logins</option>
        </select>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <KPICard index={0} icon={<ShieldAlert className="h-4 w-4" />} label="Suspended Accounts" value={security.suspended_users.length.toLocaleString()} />
        <KPICard index={1} icon={<UserPlus className="h-4 w-4" />} label="Recent Signups" value={security.recent_signups.length.toLocaleString()} />
        <KPICard
          index={2}
          icon={<ShieldCheck className="h-4 w-4" />}
          label="Admins"
          value={security.recent_signups.filter((u) => u.role === "admin").length.toLocaleString()}
        />
      </div>

      <Panel title="Suspended Accounts" subtitle="Users currently blocked from signing in">
        {security.suspended_users.length === 0 ? (
          <EmptyState label={hasActiveFilters ? "No suspended accounts match these filters." : "No suspended accounts."} />
        ) : (
          <div className="space-y-2">
            {security.suspended_users.map((u) => (
              <div key={u.user_id} className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
                <div>
                  <span className="font-medium">{u.username}</span>
                  <span className="text-xs text-muted-foreground ml-2">{u.email}</span>
                </div>
                <span className="text-xs text-muted-foreground">Suspended {formatRelativeTime(u.updated_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Recent Account Activity" subtitle="Most recently created accounts">
        {security.recent_signups.length === 0 ? (
          <EmptyState label={hasActiveFilters ? "No accounts match these filters." : "No accounts yet."} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Username</th>
                  <th className="px-3 py-2 font-medium">Email</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {security.recent_signups.map((u) => (
                  <tr key={u.user_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-medium">{u.username}</td>
                    <td className="px-3 py-2 text-muted-foreground">{u.email}</td>
                    <td className="px-3 py-2 text-muted-foreground">{u.role}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={u.status} />
                    </td>
                    <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(u.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Recent Logins" subtitle="Most recent successful sign-ins">
          {security.recent_logins.length === 0 ? (
            <EmptyState label={hasActiveFilters ? "No logins match these filters." : "No successful logins recorded yet."} />
          ) : (
            <div className="space-y-2">
              {security.recent_logins.map((l, idx) => (
                <div
                  key={`${l.user_id || l.username}-${l.created_at}-${idx}`}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <LogIn className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="font-medium">{l.username}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{formatRelativeTime(l.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Failed Login Attempts" subtitle="Most recent unsuccessful sign-in attempts">
          {security.failed_logins.length === 0 ? (
            <EmptyState label={hasActiveFilters ? "No failed attempts match these filters." : "No failed login attempts recorded."} />
          ) : (
            <div className="space-y-2">
              {security.failed_logins.map((l, idx) => (
                <div
                  key={`${l.username}-${l.created_at}-${idx}`}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <XOctagon className="h-3.5 w-3.5 text-red-500" />
                    <span className="font-medium">{l.username}</span>
                    {l.reason && <span className="text-xs text-muted-foreground">({l.reason})</span>}
                  </div>
                  <span className="text-xs text-muted-foreground">{formatRelativeTime(l.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
};
