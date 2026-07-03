import * as React from "react";
import { sciparserApi, AdminBrowserSession } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge } from "./shared";
import { Globe, Wifi, Shield, MonitorPlay } from "lucide-react";

export const BrowserSessionsTab: React.FC = () => {
  const [sessions, setSessions] = React.useState<AdminBrowserSession[]>([]);
  const [activeCount, setActiveCount] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.adminGetBrowserSessions();
      setSessions(res.sessions);
      setActiveCount(res.active_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load browser sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const proxyCount = sessions.filter((s) => s.proxy_configured).length;

  if (loading && sessions.length === 0) return <LoadingState />;
  if (error) return <div className="text-sm text-red-500">{error}</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <KPICard index={0} icon={<MonitorPlay className="h-4 w-4" />} label="Active Browsers" value={activeCount.toLocaleString()} />
        <KPICard index={1} icon={<Globe className="h-4 w-4" />} label="Total Sessions" value={sessions.length.toLocaleString()} />
        <KPICard index={2} icon={<Shield className="h-4 w-4" />} label="Using Proxy" value={proxyCount.toLocaleString()} />
      </div>

      <Panel title="Live Browser Sessions" subtitle="Real-time in-memory session state — refreshes every 15s">
        {sessions.length === 0 ? (
          <EmptyState label="No active browser sessions right now." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">User</th>
                  <th className="px-3 py-2 font-medium">Browser</th>
                  <th className="px-3 py-2 font-medium">Engine</th>
                  <th className="px-3 py-2 font-medium">Active Chats</th>
                  <th className="px-3 py-2 font-medium">Proxy</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.user_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-medium">{s.username || s.user_id.slice(0, 8)}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={s.browser_active ? "ACTIVE" : "PENDING"} />
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{s.browser_engine || "default"}</td>
                    <td className="px-3 py-2">{s.active_chat_count}</td>
                    <td className="px-3 py-2">
                      {s.proxy_configured ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 text-xs">
                          <Wifi className="h-3 w-3" /> Configured
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
