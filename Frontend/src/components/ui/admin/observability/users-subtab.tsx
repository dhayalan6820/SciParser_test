import * as React from "react";
import { Panel } from "../shared";
import { Button } from "../../button";
import { Input } from "../../input";
import { sciparserApi } from "../../../../api";
import { cn } from "../../../../../lib/utils";
import {
  Users,
  Search,
  ChevronRight,
  ChevronLeft,
  Coins,
  Pencil,
  Loader2,
  X,
  AlertCircle,
  Save,
  BarChart3,
  Trash2,
  Ban,
  RotateCcw,
  Plus,
  TrendingUp,
} from "lucide-react";

interface UsersSubtabProps {
  data: any;
  onOpenUserDetail?: (userId: string) => void;
  onRefresh?: () => void;
}

export const UsersSubtab: React.FC<UsersSubtabProps> = ({ data, onOpenUserDetail, onRefresh }) => {
  const [search, setSearch] = React.useState("");
  const [busyUserId, setBusyUserId] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  
  const [editingUser, setEditingUser] = React.useState<any | null>(null);
  const [creditsUser, setCreditsUser] = React.useState<any | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);
  const [showAddModal, setShowAddModal] = React.useState(false);

  // Filter Bar States
  const [filterRole, setFilterRole] = React.useState("all");
  const [filterStatus, setFilterStatus] = React.useState("all");
  const [filterTime, setFilterTime] = React.useState("all");

  // Local filtering (Role, Status, Time Joined)
  const filteredUsers = React.useMemo(() => {
    let result = data?.users || [];

    // Search filter
    if (search) {
      const lower = search.toLowerCase();
      result = result.filter((u: any) => 
        (u.username || "").toLowerCase().includes(lower) || 
        (u.email || "").toLowerCase().includes(lower) ||
        (u.user_id || "").toLowerCase().includes(lower)
      );
    }

    // Role filter
    if (filterRole !== "all") {
      result = result.filter((u: any) => u.role === filterRole);
    }

    // Status filter
    if (filterStatus !== "all") {
      result = result.filter((u: any) => u.status === filterStatus);
    }

    // Time filter
    if (filterTime !== "all") {
      const now = new Date();
      let cutOffDate = new Date();
      if (filterTime === "week") {
        cutOffDate.setDate(now.getDate() - 7);
      } else if (filterTime === "month") {
        cutOffDate.setMonth(now.getMonth() - 1);
      } else if (filterTime === "year") {
        cutOffDate.setFullYear(now.getFullYear() - 1);
      }
      result = result.filter((u: any) => u.created_at && new Date(u.created_at) >= cutOffDate);
    }

    return result;
  }, [search, data, filterRole, filterStatus, filterTime]);

  // Aggregate KPI summary stats
  const stats = React.useMemo(() => {
    const usersList = data?.users || [];
    const totalCount = data?.total ?? usersList.length;
    const activeCount = usersList.filter((u: any) => u.status === "active").length;
    const activePercent = usersList.length > 0 ? Math.round((activeCount / usersList.length) * 100) : 100;
    const totalCostVal = usersList.reduce((acc: number, u: any) => acc + (u.total_cost ?? 0), 0);
    const totalCreditsIssued = usersList.reduce((acc: number, u: any) => acc + (u.credit_balance ?? 0), 0);
    
    // Average success rate across active run metrics
    const sum = usersList.reduce((acc: number, u: any) => acc + (u.success_rate ?? 0), 0);
    const avgSuccessRate = usersList.length > 0 ? sum / usersList.length : 0;

    return {
      totalCount,
      activeCount,
      activePercent,
      totalCostVal,
      totalCreditsIssued,
      avgSuccessRate,
    };
  }, [data]);

  const runAction = async (userId: string, fn: () => Promise<any>) => {
    setBusyUserId(userId);
    setActionError(null);
    try {
      await fn();
      setConfirmDeleteId(null);
      onRefresh?.();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyUserId(null);
    }
  };

  // Export filtered list to CSV format
  const handleExportCSV = () => {
    const headers = [
      "Username",
      "Email",
      "Role",
      "Status",
      "Credits Remaining",
      "Tokens Processed",
      "Total Cost",
      "Daily Burn Rate",
      "Est. Exhaustion",
    ];
    const rows = filteredUsers.map((u: any) => [
      u.username || "",
      u.email || "",
      u.role || "",
      u.status || "",
      u.credit_balance !== undefined ? `$${u.credit_balance.toFixed(2)}` : "$0.00",
      u.total_tokens !== undefined ? String(u.total_tokens) : "0",
      u.total_cost !== undefined ? `$${u.total_cost.toFixed(4)}` : "$0.0000",
      u.daily_burn_rate !== undefined ? `$${u.daily_burn_rate.toFixed(4)}/day` : "$0.0000/day",
      u.forecast_exhaustion || "—",
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((r: any) => r.map((val: any) => `"${val}"`).join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sciparser_observability_users_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 text-left">
      {/* Subtab Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h3 className="text-base font-bold flex items-center gap-2 text-slate-800 dark:text-white">
            <Users className="h-5 w-5 text-indigo-500 shrink-0" />
            Users
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">Observe and manage user API usage, credit balance, and burn rates</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => handleExportCSV()}
            variant="outline"
            size="sm"
            className="rounded-xl font-semibold px-4 border-slate-200 dark:border-slate-800 flex items-center gap-1.5 cursor-pointer text-xs"
          >
            Export
            <ChevronRight className="h-3.5 w-3.5 rotate-90" />
          </Button>
          <Button
            onClick={() => setShowAddModal(true)}
            size="sm"
            className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold px-4 flex items-center gap-1.5 cursor-pointer shadow-md text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            Add User
          </Button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Total Users */}
        <div className="border border-slate-200 dark:border-slate-800 p-4.5 rounded-2xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Total Users</p>
            <p className="text-2xl font-bold text-slate-850 dark:text-white">{stats.totalCount}</p>
            <p className="text-[10px] text-emerald-500 font-semibold flex items-center gap-0.5">
              <span>+1 this month</span>
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
            <Users className="h-4.5 w-4.5" />
          </div>
        </div>

        {/* Active Users */}
        <div className="border border-slate-200 dark:border-slate-800 p-4.5 rounded-2xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Active Users</p>
            <p className="text-2xl font-bold text-slate-850 dark:text-white">{stats.activeCount}</p>
            <p className="text-[10px] text-slate-400 font-medium">{stats.activePercent}% of total</p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
            <Users className="h-4.5 w-4.5" />
          </div>
        </div>

        {/* Total Cost (All) */}
        <div className="border border-slate-200 dark:border-slate-800 p-4.5 rounded-2xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Total Cost (All)</p>
            <p className="text-2xl font-bold text-slate-850 dark:text-white">${stats.totalCostVal.toFixed(4)}</p>
            <p className="text-[10px] text-slate-400 font-medium">This month</p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
            <Coins className="h-4.5 w-4.5" />
          </div>
        </div>

        {/* Credits Issued */}
        <div className="border border-slate-200 dark:border-slate-800 p-4.5 rounded-2xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Credits Issued</p>
            <p className="text-2xl font-bold text-slate-850 dark:text-white">{stats.totalCreditsIssued.toFixed(2)}</p>
            <p className="text-[10px] text-slate-400 font-medium">Total credits</p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
            <Coins className="h-4.5 w-4.5" />
          </div>
        </div>

        {/* Success Rate (Avg) */}
        <div className="border border-slate-200 dark:border-slate-800 p-4.5 rounded-2xl bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Success Rate (Avg)</p>
            <p className="text-2xl font-bold text-slate-850 dark:text-white">{stats.avgSuccessRate.toFixed(2)}%</p>
            <p className="text-[10px] text-slate-400 font-medium">This month</p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
            <TrendingUp className="h-4.5 w-4.5" />
          </div>
        </div>
      </div>

      {/* Action Error Banner */}
      {actionError && (
        <div className="flex items-center gap-2.5 p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-sm shadow-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Filters & Search Row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[260px] max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by username, email, or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-lg text-sm focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>

        {/* Roles Dropdown */}
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-emerald-500 cursor-pointer"
        >
          <option value="all">All Roles</option>
          <option value="admin">Admin</option>
          <option value="user">User</option>
        </select>

        {/* Status Dropdown */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-emerald-500 cursor-pointer"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>

        {/* Time Dropdown */}
        <select
          value={filterTime}
          onChange={(e) => setFilterTime(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-emerald-500 cursor-pointer"
        >
          <option value="all">All Time</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
          <option value="year">This Year</option>
        </select>

        {/* Reset Button */}
        <button
          onClick={() => {
            setSearch("");
            setFilterRole("all");
            setFilterStatus("all");
            setFilterTime("all");
          }}
          className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
        >
          <RotateCcw className="h-3.5 w-3.5 text-muted-foreground" />
          Reset
        </button>

        <div className="ml-auto text-xs text-muted-foreground">
          Showing <span className="font-semibold text-foreground">{filteredUsers.length}</span> of {data?.total ?? 0} users
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
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                {filteredUsers.map((u: any) => (
                  <tr key={u.user_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <span className={cn("w-2 h-2 rounded-full shrink-0", u.status === "active" ? "bg-emerald-500 animate-pulse" : "bg-amber-500")} title={u.status} />
                        <div>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">{u.username}</p>
                          <p className="text-[10px] text-muted-foreground">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <select
                        value={u.role}
                        disabled={busyUserId === u.user_id}
                        onChange={(e) =>
                          runAction(u.user_id, () =>
                            sciparserApi.adminUpdateUser(u.user_id, { role: e.target.value as "admin" | "user" })
                          )
                        }
                        className="bg-muted/50 hover:bg-muted dark:bg-slate-900 border border-slate-205 dark:border-slate-800 rounded-lg px-2 py-1 text-xs font-semibold text-foreground focus:ring-2 focus:ring-primary/20 cursor-pointer transition-all disabled:opacity-50"
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold">
                      <span className={(u.credit_balance ?? 0) <= 5 ? "text-red-500 font-bold" : "text-slate-700 dark:text-slate-300"}>
                        ${(u.credit_balance ?? 0).toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">
                      {(u.total_tokens ?? 0).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-800 dark:text-slate-200 font-semibold">
                      ${(u.total_cost ?? 0).toFixed(4)}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">
                      ${(u.daily_burn_rate ?? 0).toFixed(4)}/day
                    </td>
                    <td className="py-3.5 px-4">
                      {u.forecast_exhaustion === "Never" ? (
                        <span className="text-slate-400">Never</span>
                      ) : (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          u.forecast_exhaustion && new Date(u.forecast_exhaustion).getTime() - Date.now() < 3 * 24 * 3600 * 1000
                            ? "bg-red-50 dark:bg-red-950/20 text-red-500 border border-red-500/20"
                            : "bg-amber-50 dark:bg-amber-950/20 text-amber-500 border border-amber-500/20"
                        }`}>
                          {u.forecast_exhaustion || "—"}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {busyUserId === u.user_id ? (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : (
                          <>
                            {onOpenUserDetail && (
                              <button
                                onClick={() => onOpenUserDetail(u.user_id)}
                                title="View Analytics"
                                className="inline-flex items-center justify-center text-sky-500 hover:text-sky-600 hover:bg-sky-500/10 border border-sky-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <BarChart3 className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              onClick={() => setEditingUser(u)}
                              title="Edit User Details"
                              className="inline-flex items-center justify-center text-indigo-500 hover:text-indigo-600 hover:bg-indigo-500/10 border border-indigo-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => setCreditsUser(u)}
                              title="Manage Credits"
                              className="inline-flex items-center justify-center text-amber-500 hover:text-amber-600 hover:bg-amber-500/10 border border-amber-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                            >
                              <Coins className="h-3.5 w-3.5" />
                            </button>
                            {u.status === "active" ? (
                              <button
                                onClick={() =>
                                  runAction(u.user_id, () =>
                                    sciparserApi.adminUpdateUser(u.user_id, { status: "suspended" })
                                  )
                                }
                                title="Suspend Account"
                                className="inline-flex items-center justify-center text-red-500 hover:text-red-650 hover:bg-red-500/10 border border-red-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <Ban className="h-3.5 w-3.5" />
                              </button>
                            ) : (
                              <button
                                onClick={() =>
                                  runAction(u.user_id, () =>
                                    sciparserApi.adminUpdateUser(u.user_id, { status: "active" })
                                  )
                                }
                                title="Reactivate Account"
                                className="inline-flex items-center justify-center text-emerald-500 hover:text-emerald-600 hover:bg-emerald-500/10 border border-emerald-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <RotateCcw className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {confirmDeleteId === u.user_id ? (
                              <div className="flex items-center gap-1 shrink-0">
                                <button
                                  onClick={() => runAction(u.user_id, () => sciparserApi.adminDeleteUser(u.user_id))}
                                  className="px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-[10px] font-bold shadow transition-all cursor-pointer"
                                >
                                  Confirm
                                </button>
                                <button
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="px-2 py-1 bg-slate-105 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded text-[10px] font-medium transition-all cursor-pointer"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDeleteId(u.user_id)}
                                title="Delete Account"
                                className="inline-flex items-center justify-center text-red-500 hover:text-red-650 hover:bg-red-500/10 border border-red-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Edit User Modal */}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            setEditingUser(null);
            onRefresh?.();
          }}
        />
      )}

      {/* Credits Modal */}
      {creditsUser && (
        <CreditsModal
          user={creditsUser}
          onClose={() => setCreditsUser(null)}
          onSaved={() => {
            setCreditsUser(null);
            onRefresh?.();
          }}
        />
      )}
      {/* Add User Modal */}
      {showAddModal && (
        <AddUserModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false);
            onRefresh?.();
          }}
        />
      )}
    </div>
  );
};

const CreditsModal: React.FC<{ user: any; onClose: () => void; onSaved: () => void }> = ({
  user,
  onClose,
  onSaved,
}) => {
  const [absoluteValue, setAbsoluteValue] = React.useState(
    user.credit_balance !== undefined ? String(user.credit_balance) : "0"
  );
  const [deltaValue, setDeltaValue] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSetAbsolute = async () => {
    const num = parseFloat(absoluteValue);
    if (Number.isNaN(num) || num < 0) {
      setError("Enter a valid credit balance");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await sciparserApi.adminSetUserCredits(user.user_id, { credits: num });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update credits");
    } finally {
      setSaving(false);
    }
  };

  const handleApplyDelta = async (sign: 1 | -1) => {
    const num = parseFloat(deltaValue);
    if (Number.isNaN(num) || num <= 0) {
      setError("Enter a positive amount to add or deduct");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await sciparserApi.adminSetUserCredits(user.user_id, { delta: sign * num });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update credits");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 space-y-5 shadow-2xl animate-in zoom-in-95 duration-200 text-left">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Coins className="w-4.5 h-4.5 text-amber-500 shrink-0" />
            Manage Credits — {user.username}
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground hover:bg-muted p-1.5 rounded-lg transition-colors cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
          Current Balance:{" "}
          <span className="text-indigo-500 dark:text-indigo-400 font-mono text-sm">
            {(user.credit_balance ?? 0).toFixed(2)}
          </span>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-xs shadow-sm">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Set Exact Balance</label>
            <div className="flex gap-2">
              <Input
                type="number"
                step="0.01"
                value={absoluteValue}
                onChange={(e) => setAbsoluteValue(e.target.value)}
                disabled={saving}
                className="bg-card/50 border-border/80 rounded-xl"
              />
              <Button size="sm" onClick={handleSetAbsolute} disabled={saving} className="shrink-0 rounded-xl px-4 font-bold shadow-md cursor-pointer">
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Set"}
              </Button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Add or Deduct Credits</label>
            <div className="flex gap-2">
              <Input
                type="number"
                step="0.01"
                min="0"
                placeholder="Amount"
                value={deltaValue}
                onChange={(e) => setDeltaValue(e.target.value)}
                disabled={saving}
                className="bg-card/50 border-border/80 rounded-xl"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleApplyDelta(1)}
                disabled={saving}
                className="shrink-0 text-emerald-500 hover:bg-emerald-500/10 border-emerald-500/20 hover:border-emerald-500/40 rounded-xl font-bold px-3 transition-all cursor-pointer"
              >
                + Add
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleApplyDelta(-1)}
                disabled={saving}
                className="shrink-0 text-red-500 hover:bg-red-500/10 border-red-500/20 hover:border-red-500/40 rounded-xl font-bold px-3 transition-all cursor-pointer"
              >
                − Deduct
              </Button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end pt-1">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving} className="rounded-xl font-semibold px-4 cursor-pointer">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

const EditUserModal: React.FC<{ user: any; onClose: () => void; onSaved: () => void }> = ({
  user,
  onClose,
  onSaved,
}) => {
  const [username, setUsername] = React.useState(user.username);
  const [email, setEmail] = React.useState(user.email);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes: Partial<{ username: string; email: string }> = {};
      if (username !== user.username) changes.username = username;
      if (email !== user.email) changes.email = email;

      if (Object.keys(changes).length > 0) {
        await sciparserApi.adminUpdateUser(user.user_id, changes);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 space-y-5 shadow-2xl animate-in zoom-in-95 duration-200 text-left">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Pencil className="w-4 h-4 text-indigo-500 shrink-0" />
            Edit User Details
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground hover:bg-muted p-1.5 rounded-lg transition-colors cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-xs shadow-sm">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Username</label>
            <Input 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              disabled={saving} 
              className="bg-card/50 border-border/80 rounded-xl"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Email</label>
            <Input 
              type="email" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              disabled={saving} 
              className="bg-card/50 border-border/80 rounded-xl"
            />
          </div>
          <div className="grid grid-cols-2 gap-4 pt-1.5 text-xs text-muted-foreground border-t border-border/30">
            <div>
              <div className="uppercase tracking-widest text-[9px] font-bold">Role</div>
              <div className="font-semibold text-foreground mt-0.5 capitalize">{user.role}</div>
            </div>
            <div>
              <div className="uppercase tracking-widest text-[9px] font-bold">Status</div>
              <div className="font-semibold text-foreground mt-0.5 capitalize flex items-center gap-1">
                <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", user.status === "active" ? "bg-emerald-500 animate-pulse" : "bg-amber-500")} />
                {user.status}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving} className="rounded-xl font-semibold px-4 cursor-pointer">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving || !username.trim() || !email.trim()}
            className="gap-1.5 rounded-xl font-bold px-4 shadow-md cursor-pointer"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
};

const AddUserModal: React.FC<{ onClose: () => void; onSaved: () => void }> = ({ onClose, onSaved }) => {
  const [username, setUsername] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !email.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await sciparserApi.signup(username.trim(), email.trim(), password);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <form onSubmit={handleSave} className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 space-y-5 shadow-2xl animate-in zoom-in-95 duration-200 text-left">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Plus className="w-4 h-4 text-emerald-500 shrink-0" />
            Add New User Account
          </h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground hover:bg-muted p-1.5 rounded-lg transition-colors cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-xs shadow-sm">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Username</label>
            <Input 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              disabled={saving} 
              placeholder="e.g. johndoe"
              className="bg-card/50 border-border/80 rounded-xl"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Email</label>
            <Input 
              type="email" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              disabled={saving} 
              placeholder="e.g. john@example.com"
              className="bg-card/50 border-border/80 rounded-xl"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Temporary Password</label>
            <Input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              disabled={saving} 
              placeholder="••••••••"
              className="bg-card/50 border-border/80 rounded-xl"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving} className="rounded-xl font-semibold px-4 cursor-pointer">
            Cancel
          </Button>
          <Button
            type="submit"
            size="sm"
            disabled={saving || !username.trim() || !email.trim() || !password.trim()}
            className="gap-1.5 rounded-xl font-bold px-4 shadow-md bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Create User
          </Button>
        </div>
      </form>
    </div>
  );
};
