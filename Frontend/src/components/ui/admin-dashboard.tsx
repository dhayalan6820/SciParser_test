import * as React from "react";
import { Button } from "./button";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Users,
  Activity,
  LogOut,
  Sun,
  Moon,
  LayoutDashboard,
  Bot,
  Calendar,
  Globe,
  BarChart3,
  ShieldAlert,
  Coins,
  Menu,
  X,
  MessageSquare,
  ScrollText,
} from "lucide-react";
import { UsersTab } from "./admin/users-tab";
import { OperationsTab } from "./admin/operations-tab";
import { OverviewTab } from "./admin/overview-tab";
import { AnalyticsTab } from "./admin/analytics-tab";
import { AgentMonitoringTab } from "./admin/agent-monitoring-tab";
import { AutomationMonitoringTab } from "./admin/automation-monitoring-tab";
import { BrowserSessionsTab } from "./admin/browser-sessions-tab";
import { UsageTab } from "./admin/usage-tab";
import { SecurityTab } from "./admin/security-tab";
import { LogsTab } from "./admin/logs-tab";
import { ObservabilityTab } from "./admin/observability-tab";

interface AdminDashboardProps {
  currentUser: { username: string; email: string } | null;
  onLogout: () => void;
  onOpenUserView?: () => void;
}

type Tab =
  | "overview"
  | "users"
  | "operations"
  | "analytics"
  | "observability"
  | "agents"
  | "automations"
  | "browser-sessions"
  | "usage"
  | "security"
  | "logs";

const NAV_ITEMS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "users", label: "Users", icon: <Users className="h-4 w-4" /> },
  { id: "operations", label: "Operations", icon: <Activity className="h-4 w-4" /> },
  { id: "analytics", label: "Analytics", icon: <BarChart3 className="h-4 w-4" /> },
  { id: "observability", label: "Observability", icon: <Activity className="h-4 w-4" /> },
  { id: "agents", label: "Agent Monitoring", icon: <Bot className="h-4 w-4" /> },
  { id: "automations", label: "Automation Monitoring", icon: <Calendar className="h-4 w-4" /> },
  { id: "browser-sessions", label: "Browser Sessions", icon: <Globe className="h-4 w-4" /> },
  { id: "usage", label: "Usage", icon: <Coins className="h-4 w-4" /> },
  { id: "security", label: "Security", icon: <ShieldAlert className="h-4 w-4" /> },
  { id: "logs", label: "Logs", icon: <ScrollText className="h-4 w-4" /> },
];

const TAB_LABELS: Record<Tab, string> = NAV_ITEMS.reduce(
  (acc, item) => ({ ...acc, [item.id]: item.label }),
  {} as Record<Tab, string>
);

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ currentUser, onLogout, onOpenUserView }) => {
  const { theme, toggleTheme } = useTheme();
  const [tab, setTab] = React.useState<Tab>("overview");
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);

  const renderTab = () => {
    switch (tab) {
      case "overview":
        return <OverviewTab />;
      case "users":
        return <UsersTab currentUsername={currentUser?.username} />;
      case "operations":
        return <OperationsTab />;
      case "analytics":
        return <AnalyticsTab />;
      case "observability":
        return <ObservabilityTab />;
      case "agents":
        return <AgentMonitoringTab />;
      case "automations":
        return <AutomationMonitoringTab />;
      case "browser-sessions":
        return <BrowserSessionsTab />;
      case "usage":
        return <UsageTab />;
      case "security":
        return <SecurityTab />;
      case "logs":
        return <LogsTab />;
      default:
        return null;
    }
  };

  const NavList: React.FC<{ onNavigate?: () => void }> = ({ onNavigate }) => (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          onClick={() => {
            setTab(item.id);
            onNavigate?.();
          }}
          className={cn(
            "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left",
            tab === item.id
              ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
              : "text-muted-foreground hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-foreground"
          )}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );

  return (
    <div className="h-screen w-screen flex bg-slate-50 dark:bg-slate-950 text-foreground overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:flex-col w-64 shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 px-2 mb-6">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 dark:bg-black text-emerald-400 border border-emerald-500/30">
            <Shield className="h-4.5 w-4.5" />
          </span>
          <div>
            <h1 className="text-sm font-semibold leading-tight">Admin Dashboard</h1>
            <p className="text-[11px] text-muted-foreground">SciParser</p>
          </div>
        </div>
        <NavList />
        <div className="mt-auto pt-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
          {onOpenUserView && (
            <Button variant="outline" size="sm" onClick={onOpenUserView} className="gap-1.5 w-full justify-start">
              <MessageSquare className="h-4 w-4" />
              Chat &amp; Schedules
            </Button>
          )}
          {currentUser && (
            <div className="px-2 text-xs">
              <p className="font-medium truncate">{currentUser.username}</p>
              <p className="text-muted-foreground truncate">{currentUser.email}</p>
            </div>
          )}
          <div className="flex items-center gap-2 px-2">
            <Button variant="outline" size="sm" onClick={toggleTheme} className="h-8 w-8 p-0">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="sm" onClick={onLogout} className="gap-1.5 flex-1">
              <LogOut className="h-4 w-4" />
              Log out
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileNavOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40 md:hidden"
              onClick={() => setMobileNavOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "tween", duration: 0.2 }}
              className="fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-900 p-4 md:hidden flex flex-col"
            >
              <div className="flex items-center justify-between mb-6 px-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 dark:bg-black text-emerald-400 border border-emerald-500/30">
                    <Shield className="h-4.5 w-4.5" />
                  </span>
                  <h1 className="text-sm font-semibold">Admin Dashboard</h1>
                </div>
                <button onClick={() => setMobileNavOpen(false)}>
                  <X className="h-4 w-4" />
                </button>
              </div>
              <NavList onNavigate={() => setMobileNavOpen(false)} />
              {onOpenUserView && (
                <div className="mt-auto pt-4 border-t border-slate-200 dark:border-slate-800">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      onOpenUserView();
                      setMobileNavOpen(false);
                    }}
                    className="gap-1.5 w-full justify-start"
                  >
                    <MessageSquare className="h-4 w-4" />
                    Chat &amp; Schedules
                  </Button>
                </div>
              )}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center justify-between px-4 md:px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60">
          <div className="flex items-center gap-3">
            <button className="md:hidden" onClick={() => setMobileNavOpen(true)}>
              <Menu className="h-5 w-5" />
            </button>
            <h2 className="text-base font-semibold">{TAB_LABELS[tab]}</h2>
          </div>
          <div className="flex items-center gap-3 md:hidden">
            <Button variant="outline" size="sm" onClick={toggleTheme} className="h-8 w-8 p-0">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="sm" onClick={onLogout} className="h-8 w-8 p-0">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
            >
              {renderTab()}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
