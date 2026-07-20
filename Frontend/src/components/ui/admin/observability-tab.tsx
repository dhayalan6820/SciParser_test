import * as React from "react";
import { sciparserApi, User } from "../../../api";
import { LoadingState } from "./shared";
import { OverviewSubtab } from "./observability/overview-subtab";
import { UsersSubtab } from "./observability/users-subtab";
import { ConversationsSubtab } from "./observability/conversations-subtab";
import { ModelsSubtab } from "./observability/models-subtab";
import { AgentsToolsSubtab } from "./observability/agents-tools-subtab";
import { CacheMemorySubtab } from "./observability/cache-memory-subtab";
import { PerformanceErrorsSubtab } from "./observability/performance-errors-subtab";
import { ErrorsSubtab } from "./observability/errors-subtab";
import { UserAnalyticsPanel } from "./user-analytics-panel";
import { LayoutDashboard, Users, MessageSquare, Brain, Cpu, Zap, Activity, RefreshCw, ShieldAlert } from "lucide-react";

type SubTab = "overview" | "users" | "conversations" | "models" | "agents-tools" | "cache-memory" | "performance-errors" | "errors";

const RANGE_OPTIONS = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

export const ObservabilityTab: React.FC = () => {
  const [subTab, setSubTab] = React.useState<SubTab>("overview");
  const [days, setDays] = React.useState(30);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [data, setData] = React.useState<any>(null);
  
  // Drill down detailed user state
  const [selectedUser, setSelectedUser] = React.useState<User | null>(null);

  const fetchObservabilityData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let res: any = null;
      if (subTab === "overview") {
        res = await sciparserApi.observabilityGetOverview(days);
      } else if (subTab === "users") {
        res = await sciparserApi.observabilityGetUsers(days);
      } else if (subTab === "models") {
        res = await sciparserApi.observabilityGetLLM(days);
      } else if (subTab === "agents-tools") {
        res = await sciparserApi.observabilityGetAgentsTools(days);
      } else if (subTab === "cache-memory") {
        res = await sciparserApi.observabilityGetCacheMemory(days);
      } else if (subTab === "performance-errors") {
        res = await sciparserApi.observabilityGetPerformanceErrors(days);
      }
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load observability logs");
    } finally {
      setLoading(false);
    }
  }, [subTab, days]);

  React.useEffect(() => {
    // Conversations and errors subtabs have their own paginated fetching, so skip global loading
    if (subTab !== "conversations" && subTab !== "errors") {
      fetchObservabilityData();
    }
  }, [subTab, days, fetchObservabilityData]);

  const handleOpenUserDetail = (userId: string) => {
    const userObj = data?.users?.find((u: any) => u.user_id === userId);
    if (userObj) {
      setSelectedUser(userObj);
    }
  };

  const renderSubTabContent = () => {
    if (subTab === "conversations") {
      return <ConversationsSubtab days={days} />;
    }
    if (subTab === "errors") {
      return <ErrorsSubtab days={days} />;
    }

    if (loading) return <LoadingState />;
    if (error || !data) return <div className="text-sm text-red-500 py-6">{error || "No observability data found."}</div>;

    switch (subTab) {
      case "overview":
        return <OverviewSubtab data={data} />;
      case "users":
        return <UsersSubtab data={data} onOpenUserDetail={handleOpenUserDetail} onRefresh={fetchObservabilityData} />;
      case "models":
        return <ModelsSubtab data={data} />;
      case "agents-tools":
        return <AgentsToolsSubtab data={data} />;
      case "cache-memory":
        return <CacheMemorySubtab data={data} />;
      case "performance-errors":
        return <PerformanceErrorsSubtab data={data} />;
      default:
        return null;
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Header & Range Select */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Activity className="h-5 w-5 text-emerald-500 animate-pulse" />
            AI Observability &amp; Analytics
          </h2>
          <p className="text-xs text-muted-foreground">Monitor real-time token usage, costs, agents execution, and tools</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-transparent border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs font-medium focus:outline-none focus:border-emerald-500"
          >
            {RANGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={fetchObservabilityData}
            title="Refresh Data"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 text-slate-500 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Sub Navigation Tabs */}
      <div className="flex gap-1 border-b border-slate-100 dark:border-slate-800 overflow-x-auto pb-px">
        <button
          onClick={() => setSubTab("overview")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "overview"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <LayoutDashboard className="h-4 w-4" />
          Overview
        </button>
        <button
          onClick={() => setSubTab("users")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "users"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Users className="h-4 w-4" />
          Users
        </button>
        <button
          onClick={() => setSubTab("conversations")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "conversations"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          Conversations
        </button>
        <button
          onClick={() => setSubTab("models")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "models"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Brain className="h-4 w-4" />
          LLM &amp; Providers
        </button>
        <button
          onClick={() => setSubTab("agents-tools")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "agents-tools"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Cpu className="h-4 w-4" />
          Agents &amp; Tools
        </button>
        <button
          onClick={() => setSubTab("cache-memory")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "cache-memory"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Zap className="h-4 w-4" />
          Cache &amp; Memory
        </button>
        <button
          onClick={() => setSubTab("performance-errors")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "performance-errors"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Activity className="h-4 w-4" />
          Performance &amp; Errors
        </button>
        <button
          onClick={() => setSubTab("errors")}
          className={`flex items-center gap-1.5 px-4 py-2 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
            subTab === "errors"
              ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <ShieldAlert className="h-4 w-4" />
          Errors Log
        </button>
      </div>

      {/* Render subtab details */}
      <div className="pt-2">{renderSubTabContent()}</div>

      {/* User drill-down panel */}
      {selectedUser && (
        <UserAnalyticsPanel
          user={selectedUser as any}
          onClose={() => setSelectedUser(null)}
        />
      )}
    </div>
  );
};
