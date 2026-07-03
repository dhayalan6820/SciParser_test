import * as React from "react";
import { sciparserApi, AdminAutomation } from "../../../api";
import { KPICard, Panel, EmptyState, LoadingState, StatusBadge, formatRelativeTime } from "./shared";
import { Calendar, CheckCircle2, XCircle, Repeat } from "lucide-react";

export const AutomationMonitoringTab: React.FC = () => {
  const [automations, setAutomations] = React.useState<AdminAutomation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.adminGetAutomations();
        if (!cancelled) setAutomations(res.automations);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load automations");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalRuns = automations.reduce((sum, a) => sum + a.total_runs, 0);
  const totalSuccess = automations.reduce((sum, a) => sum + a.success_runs, 0);
  const totalFailed = automations.reduce((sum, a) => sum + a.failed_runs, 0);
  const active = automations.filter((a) => a.status === "active").length;

  if (loading) return <LoadingState />;
  if (error) return <div className="text-sm text-red-500">{error}</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Repeat className="h-4 w-4" />} label="Active Schedules" value={active.toLocaleString()} />
        <KPICard index={1} icon={<Calendar className="h-4 w-4" />} label="Total Runs" value={totalRuns.toLocaleString()} />
        <KPICard index={2} icon={<CheckCircle2 className="h-4 w-4" />} label="Successful Runs" value={totalSuccess.toLocaleString()} />
        <KPICard index={3} icon={<XCircle className="h-4 w-4" />} label="Failed Runs" value={totalFailed.toLocaleString()} />
      </div>

      <Panel title="Automations" subtitle="Every scheduled/automated job and its execution history">
        {automations.length === 0 ? (
          <EmptyState label="No automations have been created yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Title</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Runs</th>
                  <th className="px-3 py-2 font-medium">Success Rate</th>
                  <th className="px-3 py-2 font-medium">Last Run</th>
                  <th className="px-3 py-2 font-medium">Next Run</th>
                </tr>
              </thead>
              <tbody>
                {automations.map((a) => (
                  <tr key={a.schedule_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-medium">{a.title || a.schedule_id.slice(0, 8)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{a.schedule_type}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="px-3 py-2">
                      {a.total_runs} <span className="text-muted-foreground">({a.success_runs} ok / {a.failed_runs} failed)</span>
                    </td>
                    <td className="px-3 py-2">{a.success_rate}%</td>
                    <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(a.last_run)}</td>
                    <td className="px-3 py-2 text-muted-foreground text-xs whitespace-nowrap">{formatRelativeTime(a.next_run)}</td>
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
