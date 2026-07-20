import * as React from "react";
import { Button } from "../button";
import { Input } from "../input";
import { sciparserApi, User } from "../../../api";
import { cn } from "../../../../lib/utils";
import { formatRelativeTime } from "./shared";
import { UserAnalyticsPanel } from "./user-analytics-panel";
import {
  Search,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Ban,
  RotateCcw,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Pencil,
  X,
  Save,
  BarChart3,
  Coins,
  Mail,
  Shield,
  Activity,
  Clock,
  Calendar,
  User as UserIcon,
  Settings,
  DollarSign,
  TrendingUp,
  Plus,
  ExternalLink,
  Users as UsersIcon,
} from "lucide-react";

const PAGE_SIZE = 10;

const getInitials = (name?: string) => {
  if (!name) return "?";
  const parts = name.split(/[._\s-]/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
};

const getAvatarColor = (name?: string) => {
  if (!name) return "bg-slate-500/10 text-slate-400 border-slate-500/20";
  const sum = name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const colors = [
    "bg-sky-500/10 text-sky-500 dark:text-sky-400 border-sky-500/20 dark:border-sky-500/10",
    "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400 border-emerald-500/20 dark:border-emerald-500/10",
    "bg-indigo-500/10 text-indigo-500 dark:text-indigo-400 border-indigo-500/20 dark:border-indigo-500/10",
    "bg-amber-500/10 text-amber-500 dark:text-amber-400 border-amber-500/20 dark:border-amber-500/10",
    "bg-rose-500/10 text-rose-500 dark:text-rose-400 border-rose-500/20 dark:border-rose-500/10",
    "bg-violet-500/10 text-violet-500 dark:text-violet-400 border-violet-500/20 dark:border-violet-500/10",
  ];
  return colors[sum % colors.length];
};

export const UsersTab: React.FC<{ currentUsername?: string }> = ({ currentUsername }) => {
  const [users, setUsers] = React.useState<User[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [busyUserId, setBusyUserId] = React.useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);
  const [editingUser, setEditingUser] = React.useState<User | null>(null);
  const [analyticsUser, setAnalyticsUser] = React.useState<User | null>(null);
  const [creditsUser, setCreditsUser] = React.useState<User | null>(null);
  const [showAddModal, setShowAddModal] = React.useState(false);

  // Filter Bar States
  const [filterRole, setFilterRole] = React.useState("all");
  const [filterStatus, setFilterStatus] = React.useState("all");
  const [filterTime, setFilterTime] = React.useState("all");

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadUsers = React.useCallback(async (pageArg: number, searchArg: string) => {
    setLoading(true);
    setError(null);
    try {
      // Fetch users (higher limit/page_size for administrative overview lists)
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
  }, [search, loadUsers]);

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

  // Local filtering (Role, Status, Time Joined)
  const filteredUsers = React.useMemo(() => {
    let result = [...users];

    if (filterRole !== "all") {
      result = result.filter((u) => u.role === filterRole);
    }

    if (filterStatus !== "all") {
      result = result.filter((u) => u.status === filterStatus);
    }

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
      result = result.filter((u) => u.created_at && new Date(u.created_at) >= cutOffDate);
    }

    return result;
  }, [users, filterRole, filterStatus, filterTime]);

  // Aggregate KPI summary stats
  const stats = React.useMemo(() => {
    const totalCount = total;
    const activeCount = users.filter((u) => u.status === "active").length;
    const activePercent = users.length > 0 ? Math.round((activeCount / users.length) * 100) : 100;
    const totalCostVal = users.reduce((acc, u) => acc + (u.total_cost ?? 0), 0);
    const totalCreditsIssued = users.reduce((acc, u) => acc + (u.credit_balance ?? 0), 0);
    
    // Average success rate across active run metrics
    const sum = users.reduce((acc, u) => acc + (u.success_rate ?? 0), 0);
    const avgSuccessRate = users.length > 0 ? sum / users.length : 0;

    return {
      totalCount,
      activeCount,
      activePercent,
      totalCostVal,
      totalCreditsIssued,
      avgSuccessRate,
    };
  }, [users, total]);

  // Export filtered list to CSV format
  const handleExportCSV = () => {
    const headers = ["Username", "Email", "Role", "Status", "Success Rate", "Total Cost", "Credits", "Joined"];
    const rows = filteredUsers.map((u: any) => [
      u.username || "",
      u.email || "",
      u.role || "",
      u.status || "",
      u.success_rate !== undefined ? `${u.success_rate}%` : "0%",
      u.total_cost !== undefined ? `$${u.total_cost.toFixed(4)}` : "$0.0000",
      u.credit_balance !== undefined ? String(u.credit_balance) : "5.00",
      u.created_at ? new Date(u.created_at).toLocaleDateString() : "",
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((r: any) => r.map((val: any) => `"${val}"`).join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sciparser_users_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 text-left">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800 dark:text-white">
            <UsersIcon className="h-5 w-5 text-indigo-500 shrink-0" />
            Users
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">Manage users, roles, credits and access permissions</p>
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
            <UsersIcon className="h-4.5 w-4.5" />
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
            <UsersIcon className="h-4.5 w-4.5" />
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

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[260px] max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by username or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-lg text-sm focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        {/* Roles Dropdown */}
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-indigo-500 cursor-pointer"
        >
          <option value="all">All Roles</option>
          <option value="admin">Admin</option>
          <option value="user">User</option>
        </select>

        {/* Status Dropdown */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-indigo-500 cursor-pointer"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>

        {/* Time Dropdown */}
        <select
          value={filterTime}
          onChange={(e) => setFilterTime(e.target.value)}
          className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg text-xs font-semibold focus:outline-none focus:border-indigo-500 cursor-pointer"
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
      </div>

      {actionError && (
        <div className="flex items-center gap-2.5 p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-sm shadow-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Main Users Table Container */}
      <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-950/40 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold uppercase">
                <th className="px-6 py-4.5">User</th>
                <th className="px-6 py-4.5">Email</th>
                <th className="px-6 py-4.5">Role</th>
                <th className="px-6 py-4.5">Status</th>
                <th className="px-6 py-4.5">Last Active</th>
                <th className="px-6 py-4.5">Success Rate</th>
                <th className="px-6 py-4.5">Total Cost</th>
                <th className="px-6 py-4.5">Credits</th>
                <th className="px-6 py-4.5">Joined</th>
                <th className="px-6 py-4.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-muted-foreground text-sm">
                    <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
                    Loading users...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-red-500 font-semibold text-sm">
                    {error}
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-muted-foreground text-sm">
                    No users found matching the selected filters.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const isSelf = u.username === currentUsername;
                  const isBusy = busyUserId === u.user_id;
                  return (
                    <tr key={u.user_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                      <td className="px-6 py-4 align-middle whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className={cn("w-8 h-8 rounded-full flex items-center justify-center font-bold text-[11px] uppercase tracking-wider shrink-0 border shadow-sm", getAvatarColor(u.username))}>
                            {getInitials(u.username)}
                          </div>
                          <div className="flex flex-col">
                            <span className="font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                              {u.username}
                              {isSelf && <span className="text-[9px] font-black uppercase tracking-wider text-sky-500 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded">You</span>}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 align-middle text-muted-foreground whitespace-nowrap text-[13px] font-medium">
                        {u.email}
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap">
                        <select
                          value={u.role}
                          disabled={isSelf || isBusy}
                          onChange={(e) =>
                            runAction(u.user_id, () =>
                              sciparserApi.adminUpdateUser(u.user_id, { role: e.target.value as "admin" | "user" })
                            )
                          }
                          className="bg-muted/50 hover:bg-muted dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-foreground focus:ring-2 focus:ring-primary/20 cursor-pointer transition-all disabled:opacity-50"
                        >
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm",
                            u.status === "active"
                              ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                              : "bg-amber-500/10 text-amber-500 border-amber-500/20"
                          )}
                        >
                          <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", u.status === "active" ? "bg-emerald-500 animate-pulse" : "bg-amber-50")} />
                          {u.status === "active" ? "Active" : "Suspended"}
                        </span>
                      </td>
                      <td className="px-6 py-4 align-middle text-muted-foreground whitespace-nowrap font-medium">
                        {formatRelativeTime(u.last_active)}
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap">
                        <div className="space-y-1 max-w-[100px]">
                          <span className="font-mono text-xs font-semibold">{u.success_rate !== undefined ? `${u.success_rate}%` : "0%"}</span>
                          <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                            <div 
                              style={{ width: `${u.success_rate ?? 0}%` }}
                              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap font-semibold font-mono text-slate-800 dark:text-slate-200">
                        {u.total_cost !== undefined ? `$${u.total_cost.toFixed(4)}` : "—"}
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap font-semibold font-mono text-blue-500 dark:text-blue-400">
                        <button onClick={() => setCreditsUser(u)} className="hover:underline text-left cursor-pointer">
                          {(u.credit_balance ?? 0).toFixed(2)}
                        </button>
                      </td>
                      <td className="px-6 py-4 align-middle text-muted-foreground whitespace-nowrap font-medium">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString("en-GB") : "—"}
                      </td>
                      <td className="px-6 py-4 align-middle whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-2">
                          {isBusy ? (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                          ) : (
                            <>
                              {/* Analytics Action */}
                              <button
                                onClick={() => setAnalyticsUser(u)}
                                title="View Analytics"
                                className="inline-flex items-center justify-center text-purple-500 hover:text-purple-650 hover:bg-purple-500/10 border border-purple-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <BarChart3 className="h-3.5 w-3.5" />
                              </button>

                              {/* Edit details Action */}
                              <button
                                onClick={() => setEditingUser(u)}
                                title="Edit User Details"
                                className="inline-flex items-center justify-center text-blue-500 hover:text-blue-600 hover:bg-blue-500/10 border border-blue-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>

                              {/* Credits Action */}
                              <button
                                onClick={() => setCreditsUser(u)}
                                title="Manage Credits"
                                className="inline-flex items-center justify-center text-amber-500 hover:text-amber-600 hover:bg-amber-500/10 border border-amber-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer"
                              >
                                <Coins className="h-3.5 w-3.5" />
                              </button>

                              {/* Suspend Action */}
                              {u.status === "active" ? (
                                <button
                                  onClick={() =>
                                    runAction(u.user_id, () =>
                                      sciparserApi.adminUpdateUser(u.user_id, { status: "suspended" })
                                    )
                                  }
                                  title="Suspend Account"
                                  disabled={isSelf}
                                  className="inline-flex items-center justify-center text-indigo-500 hover:text-indigo-600 hover:bg-indigo-500/10 border border-indigo-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer disabled:opacity-40"
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

                              {/* Delete Action */}
                              {confirmDeleteId === u.user_id ? (
                                <div className="flex items-center gap-1 shrink-0">
                                  <button
                                    onClick={() => runAction(u.user_id, () => sciparserApi.adminDeleteUser(u.user_id))}
                                    className="px-2 py-1 bg-red-650 hover:bg-red-700 text-white rounded text-[10px] font-bold shadow transition-all cursor-pointer animate-pulse"
                                  >
                                    Confirm
                                  </button>
                                  <button
                                    onClick={() => setConfirmDeleteId(null)}
                                    className="px-2 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded text-[10px] font-medium transition-all cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <button
                                  onClick={() => setConfirmDeleteId(u.user_id)}
                                  title="Delete Account"
                                  disabled={isSelf}
                                  className="inline-flex items-center justify-center text-red-500 hover:text-red-600 hover:bg-red-500/10 border border-red-500/20 p-1.5 rounded-lg text-xs transition-all shadow-sm cursor-pointer disabled:opacity-40"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
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
      </div>

      {/* Pagination Controls */}
      {!loading && total > 0 && (
        <div className="flex items-center justify-between px-2">
          <span className="text-xs text-muted-foreground font-medium">
            Showing <span className="text-foreground font-semibold">{(page - 1) * PAGE_SIZE + 1}</span> to{" "}
            <span className="text-foreground font-semibold">{Math.min(page * PAGE_SIZE, total)}</span> of{" "}
            <span className="text-foreground font-semibold">{total}</span> users
          </span>
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-8 w-8 p-0 rounded-xl cursor-pointer"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs font-semibold px-3 py-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg">
              {page}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="h-8 w-8 p-0 rounded-xl cursor-pointer"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Helper Tip bulb info section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 p-4 bg-indigo-500/[0.03] border border-indigo-500/10 rounded-2xl">
        <div className="flex items-center gap-2">
          <span className="h-8 w-8 rounded-full bg-indigo-500/10 text-indigo-500 flex items-center justify-center shrink-0">
            <Activity className="h-4 w-4" />
          </span>
          <p className="text-xs text-slate-650 dark:text-slate-350 font-medium">
            Tip: Click on a user to view detailed analytics, usage breakdown, and activity insights.
          </p>
        </div>
        <button className="flex items-center gap-1 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 text-xs font-semibold transition-colors cursor-pointer">
          View Documentation
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <AddUserModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false);
            setPage(1);
            loadUsers(1, search);
          }}
        />
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            setEditingUser(null);
            loadUsers(page, search);
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
            loadUsers(page, search);
          }}
        />
      )}

      {/* User Analytics Panel Drawer */}
      {analyticsUser && (
        <UserAnalyticsPanel user={analyticsUser} onClose={() => setAnalyticsUser(null)} />
      )}
    </div>
  );
};

/* --- Modals --- */

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

const CreditsModal: React.FC<{ user: User; onClose: () => void; onSaved: () => void }> = ({
  user,
  onClose,
  onSaved,
}) => {
  const [absoluteValue, setAbsoluteValue] = React.useState(String(user.credit_balance ?? 0));
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

const EditUserModal: React.FC<{ user: User; onClose: () => void; onSaved: () => void }> = ({
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
                <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", user.status === "active" ? "bg-emerald-500 animate-pulse" : "bg-amber-50")} />
                {user.status === "active" ? "Active" : "Suspended"}
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
