import * as React from "react";
import { sciparserApi, AdminSecurity } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime } from "./shared";
import { ShieldAlert, UserPlus, ShieldCheck, LogIn, XOctagon } from "lucide-react";

export const SecurityTab: React.FC = () => {
  const [security, setSecurity] = React.useState<AdminSecurity | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetSecurity();
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
  }, []);

  if (loading) return <LoadingState />;
  if (error || !security) return <div className="text-sm text-red-500">{error || "No data"}</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
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
          <EmptyState label="No suspended accounts." />
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
          <EmptyState label="No accounts yet." />
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
            <EmptyState label="No successful logins recorded yet." />
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
            <EmptyState label="No failed login attempts recorded." />
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
