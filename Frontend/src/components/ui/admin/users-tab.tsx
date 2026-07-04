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
} from "lucide-react";

const PAGE_SIZE = 10;

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
    <div className="max-w-6xl mx-auto space-y-4">
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

      <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Username</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Email</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Role</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Status</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Last Active</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Success Rate</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Total Cost</th>
              <th className="px-4 py-3 font-medium whitespace-nowrap">Joined</th>
              <th className="px-4 py-3 font-medium text-right whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
                  Loading users...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-red-500">
                  {error}
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                  No users found.
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const isSelf = u.username === currentUsername;
                const isBusy = busyUserId === u.user_id;
                return (
                  <tr key={u.user_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-4 py-3 font-medium whitespace-nowrap">
                      {u.username} {isSelf && <span className="text-xs text-muted-foreground">(you)</span>}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{u.email}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
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
                    <td className="px-4 py-3 whitespace-nowrap">
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
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(u.last_active)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {u.success_rate !== undefined ? `${u.success_rate}%` : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {u.total_cost !== undefined ? `$${u.total_cost.toFixed(4)}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        {isBusy ? (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setAnalyticsUser(u)}
                              className="h-7 px-2 text-xs gap-1"
                            >
                              <BarChart3 className="h-3 w-3" />
                              View Analytics
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setEditingUser(u)}
                              className="h-7 px-2 text-xs gap-1"
                            >
                              <Pencil className="h-3 w-3" />
                              Edit
                            </Button>
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

      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={async () => {
            setEditingUser(null);
            await loadUsers(page, search);
          }}
        />
      )}

      {analyticsUser && (
        <UserAnalyticsPanel user={analyticsUser} onClose={() => setAnalyticsUser(null)} />
      )}
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-background p-5 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Edit user details</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-2.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/40 rounded-lg text-red-600 dark:text-red-400 text-xs">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Username</label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} disabled={saving} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Email</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={saving} />
          </div>
          <div className="grid grid-cols-2 gap-3 pt-1 text-xs text-muted-foreground">
            <div>
              <div className="uppercase tracking-wide text-[10px]">Role</div>
              <div className="font-medium text-foreground">{user.role}</div>
            </div>
            <div>
              <div className="uppercase tracking-wide text-[10px]">Status</div>
              <div className="font-medium text-foreground">{user.status}</div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving || !username.trim() || !email.trim()}
            className="gap-1.5"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save
          </Button>
        </div>
      </div>
    </div>
  );
};
