import * as React from "react";
import { Panel } from "../shared";
import { Users, Search, ChevronRight, Coins } from "lucide-react";

interface UsersSubtabProps {
  data: any;
  onOpenUserDetail?: (userId: string) => void;
}

export const UsersSubtab: React.FC<UsersSubtabProps> = ({ data, onOpenUserDetail }) => {
  const [search, setSearch] = React.useState("");

  const filteredUsers = React.useMemo(() => {
    if (!search) return data.users || [];
    const lower = search.toLowerCase();
    return (data.users || []).filter((u: any) => 
      (u.username || "").toLowerCase().includes(lower) || 
      (u.email || "").toLowerCase().includes(lower) ||
      (u.user_id || "").toLowerCase().includes(lower)
    );
  }, [search, data]);

  return (
    <div className="space-y-4">
      {/* Filters & Search */}
      <div className="flex justify-between items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by username, email, or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-lg text-sm focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
        <div className="text-xs text-muted-foreground">
          Showing <span className="font-semibold text-foreground">{filteredUsers.length}</span> of {data.total} users
        </div>
      </div>

      {/* Users Observability Table */}
      <Panel title="User Cost & Credit Observability" subtitle="Detailed credit burn rates and token usage per user">
        {filteredUsers.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">No users match your filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase">
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Credits Remaining</th>
                  <th className="py-3 px-4">Tokens Processed</th>
                  <th className="py-3 px-4">Total Cost</th>
                  <th className="py-3 px-4">Daily Burn Rate</th>
                  <th className="py-3 px-4">Est. Exhaustion</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
                {filteredUsers.map((u: any) => (
                  <tr key={u.user_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                    <td className="py-3.5 px-4">
                      <div>
                        <p className="font-semibold text-slate-800 dark:text-slate-200">{u.username}</p>
                        <p className="text-[10px] text-muted-foreground">{u.email}</p>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 capitalize">
                      <span className={`px-2 py-0.5 rounded-full font-medium ${
                        u.role === "admin" ? "bg-purple-50 dark:bg-purple-950/20 text-purple-600 dark:text-purple-400 border border-purple-200/30" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold">
                      <span className={u.credit_balance <= 5 ? "text-red-500 font-bold" : "text-slate-700 dark:text-slate-300"}>
                        ${u.credit_balance.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">
                      {u.total_tokens.toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-800 dark:text-slate-200 font-semibold">
                      ${u.total_cost.toFixed(4)}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">
                      ${u.daily_burn_rate.toFixed(4)}/day
                    </td>
                    <td className="py-3.5 px-4">
                      {u.forecast_exhaustion === "Never" ? (
                        <span className="text-slate-400">Never</span>
                      ) : (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          new Date(u.forecast_exhaustion).getTime() - Date.now() < 3 * 24 * 3600 * 1000
                            ? "bg-red-50 dark:bg-red-950/20 text-red-500 border border-red-500/20"
                            : "bg-amber-50 dark:bg-amber-950/20 text-amber-500 border border-amber-500/20"
                        }`}>
                          {u.forecast_exhaustion}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {onOpenUserDetail && (
                        <button
                          onClick={() => onOpenUserDetail(u.user_id)}
                          className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 font-semibold transition-colors"
                        >
                          View Analytics
                          <ChevronRight className="h-4 w-4" />
                        </button>
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
