import * as React from "react";
import { Button } from "./button";
import { sciparserApi } from "../../api";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../../lib/utils";
import {
  Shield,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Globe,
  Link,
  Trash2,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
  Info,
  Wifi,
  WifiOff,
  Server,
  Zap,
  RefreshCw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface SettingsPageProps {
  onBack: () => void;
  userProfile: { username: string; email: string } | null;
  activeThreadId?: string | null;
  onResetSession?: () => Promise<void> | void;
}

const PROXY_PROVIDERS = [
  { name: "Brightdata", example: "http://user:pass@brd.superproxy.io:22225" },
  { name: "Oxylabs", example: "http://user:pass@pr.oxylabs.io:7777" },
  { name: "Smartproxy", example: "http://user:pass@gate.smartproxy.com:7000" },
  { name: "IPRoyal", example: "http://user:pass@geo.iproyal.com:12321" },
  { name: "FloppyData", example: "http://user-...-rotation-15:pass@geo.g-w.info:10080" },
];

export const SettingsPage: React.FC<SettingsPageProps> = ({ onBack, userProfile, activeThreadId, onResetSession }) => {
  const { theme } = useTheme();

  const [resettingSession, setResettingSession] = React.useState(false);
  const [sessionReset, setSessionReset] = React.useState(false);

  const [proxyActive, setProxyActive] = React.useState(false);
  const [proxyUrlMasked, setProxyUrlMasked] = React.useState<string | null>(null);
  const [proxyInput, setProxyInput] = React.useState("");
  const [proxyInputVisible, setProxyInputVisible] = React.useState(false);
  const [proxySaving, setProxySaving] = React.useState(false);
  const [proxyDeleting, setProxyDeleting] = React.useState(false);
  const [proxyError, setProxyError] = React.useState<string | null>(null);
  const [proxySaved, setProxySaved] = React.useState(false);
  const [proxyTesting, setProxyTesting] = React.useState(false);
  const [proxyTestResult, setProxyTestResult] = React.useState<{ ip: string; testedUrl?: string } | null>(null);
  const [proxyTestUrl, setProxyTestUrl] = React.useState("");
  const [showTestUrlInput, setShowTestUrlInput] = React.useState(false);
  const [proxyTestError, setProxyTestError] = React.useState<string | null>(null);
  const [showProviderHint, setShowProviderHint] = React.useState(false);
  const [loadingStatus, setLoadingStatus] = React.useState(true);
  const [copiedProvider, setCopiedProvider] = React.useState<string | null>(null);

  const [browserEngine, setBrowserEngine] = React.useState<"camoufox" | "chrome">("camoufox");
  const [engineLoading, setEngineLoading] = React.useState(true);
  const [engineSaving, setEngineSaving] = React.useState(false);
  const [engineSaved, setEngineSaved] = React.useState(false);

  const [fdActive, setFdActive] = React.useState(false);
  const [fdKeyMasked, setFdKeyMasked] = React.useState<string | null>(null);
  const [fdInput, setFdInput] = React.useState("");
  const [fdInputVisible, setFdInputVisible] = React.useState(false);
  const [fdSaving, setFdSaving] = React.useState(false);
  const [fdDeleting, setFdDeleting] = React.useState(false);
  const [fdError, setFdError] = React.useState<string | null>(null);
  const [fdSaved, setFdSaved] = React.useState(false);
  const [fdLoadingStatus, setFdLoadingStatus] = React.useState(true);
  const [fdBalance, setFdBalance] = React.useState<any | null>(null);
  const [fdBalanceLoading, setFdBalanceLoading] = React.useState(false);
  const [fdBalanceError, setFdBalanceError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setLoadingStatus(true);
    sciparserApi.getProxyStatus()
      .then((s) => {
        setProxyActive(s.active);
        setProxyUrlMasked(s.proxy_url_masked);
      })
      .catch(() => {})
      .finally(() => setLoadingStatus(false));

    sciparserApi.getBrowserEngine()
      .then((r) => setBrowserEngine((r.engine as "camoufox" | "chrome") || "camoufox"))
      .catch(() => {})
      .finally(() => setEngineLoading(false));

    setFdLoadingStatus(true);
    sciparserApi.getFloppyDataKeyStatus()
      .then((s) => {
        setFdActive(s.active);
        setFdKeyMasked(s.api_key_masked);
        if (s.active) handleFetchFdBalance();
      })
      .catch(() => {})
      .finally(() => setFdLoadingStatus(false));
  }, []);

  const handleFetchFdBalance = async () => {
    setFdBalanceLoading(true);
    setFdBalanceError(null);
    try {
      const res = await sciparserApi.getFloppyDataBalance();
      setFdBalance(res);
    } catch (err: any) {
      setFdBalanceError(err.message || "Failed to fetch balance");
    } finally {
      setFdBalanceLoading(false);
    }
  };

  const handleSaveFdKey = async () => {
    if (!fdInput.trim()) return;
    setFdSaving(true);
    setFdError(null);
    setFdSaved(false);
    try {
      const res = await sciparserApi.setFloppyDataKey(fdInput.trim());
      setFdActive(true);
      setFdKeyMasked((res as any).api_key_masked ?? null);
      setFdInput("");
      setFdSaved(true);
      setTimeout(() => setFdSaved(false), 3000);
      handleFetchFdBalance();
    } catch (err: any) {
      setFdError(err.message || "Failed to save API key");
    } finally {
      setFdSaving(false);
    }
  };

  const handleDeleteFdKey = async () => {
    setFdDeleting(true);
    setFdError(null);
    try {
      await sciparserApi.deleteFloppyDataKey();
      setFdActive(false);
      setFdKeyMasked(null);
      setFdInput("");
      setFdBalance(null);
      setFdBalanceError(null);
    } catch (err: any) {
      setFdError(err.message || "Failed to remove API key");
    } finally {
      setFdDeleting(false);
    }
  };

  const handleSetEngine = async (engine: "camoufox" | "chrome") => {
    if (engine === browserEngine) return;
    setEngineSaving(true);
    try {
      await sciparserApi.setBrowserEngine(engine);
      setBrowserEngine(engine);
      setEngineSaved(true);
      setTimeout(() => setEngineSaved(false), 3000);
    } catch {
      // silently ignore — engine stays unchanged
    } finally {
      setEngineSaving(false);
    }
  };

  const handleSaveProxy = async () => {
    if (!proxyInput.trim()) return;
    setProxySaving(true);
    setProxyError(null);
    setProxySaved(false);
    setProxyTestResult(null);
    setProxyTestError(null);
    try {
      const res = await sciparserApi.setProxy(proxyInput.trim());
      setProxyActive(true);
      setProxyUrlMasked((res as any).proxy_url_masked ?? proxyInput.trim());
      setProxyInput("");
      setProxySaved(true);
      setTimeout(() => setProxySaved(false), 3000);
    } catch (err: any) {
      setProxyError(err.message || "Failed to save proxy");
    } finally {
      setProxySaving(false);
    }
  };

  const handleDeleteProxy = async () => {
    setProxyDeleting(true);
    setProxyError(null);
    setProxyTestResult(null);
    setProxyTestError(null);
    try {
      await sciparserApi.deleteProxy();
      setProxyActive(false);
      setProxyUrlMasked(null);
      setProxyInput("");
    } catch (err: any) {
      setProxyError(err.message || "Failed to remove proxy");
    } finally {
      setProxyDeleting(false);
    }
  };

  const handleTestProxy = async () => {
    setProxyTesting(true);
    setProxyTestResult(null);
    setProxyTestError(null);
    try {
      const res = await sciparserApi.testProxy(proxyInput.trim() || undefined, proxyTestUrl.trim() || undefined);
      setProxyTestResult({ ip: res.exit_ip, testedUrl: res.tested_url });
    } catch (err: any) {
      setProxyTestError(err.message || "Proxy test failed");
    } finally {
      setProxyTesting(false);
    }
  };

  const handleCopyExample = (example: string, name: string) => {
    navigator.clipboard.writeText(example).then(() => {
      setCopiedProvider(name);
      setTimeout(() => setCopiedProvider(null), 1500);
    });
  };

  const handleResetSession = async () => {
    if (!onResetSession || resettingSession) return;
    setResettingSession(true);
    setSessionReset(false);
    try {
      await onResetSession();
      setSessionReset(true);
      setTimeout(() => setSessionReset(false), 3000);
    } finally {
      setResettingSession(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background overflow-hidden">
      {/* Page header */}
      <div className="relative z-10 flex items-center gap-3 px-6 py-4 border-b border-border">
        <button
          onClick={onBack}
          className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-border bg-muted/50 text-muted-foreground hover:border-violet-500/30 hover:text-foreground transition-all"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-base font-bold text-foreground tracking-tight">Settings</h1>
          <p className="text-xs text-muted-foreground">Configure your browser and proxy preferences</p>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* ── Session Section ───────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <RefreshCw className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-bold text-foreground uppercase tracking-widest">Session</h2>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
                <Info className="h-3.5 w-3.5 text-amber-400" />
              </div>
              <div className="flex-1">
                <p className="text-xs font-semibold text-foreground mb-1">Reset Session</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Clears the saved browser state (cookies, login, current page) for your open chat, so the
                  next message starts from a completely fresh browser instead of continuing where the last
                  run left off. Use this if a chat gets stuck on a broken page or logged-in state.
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs font-semibold text-amber-500 border-amber-200 hover:bg-amber-50 dark:border-amber-900/30 dark:hover:bg-amber-900/10 disabled:opacity-40"
                onClick={handleResetSession}
                disabled={!activeThreadId || resettingSession}
                title={!activeThreadId ? "Open a chat first to reset its session" : "Clear the saved browser session so the next message starts from scratch"}
              >
                {resettingSession
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <RefreshCw className="h-3.5 w-3.5" />}
                {resettingSession ? "Resetting…" : "Reset Session"}
              </Button>
              {!activeThreadId && (
                <span className="text-[11px] text-muted-foreground/70">Open a chat to enable this.</span>
              )}
              {sessionReset && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Session reset
                </span>
              )}
            </div>
          </div>
        </section>

        {/* ── Proxy Section ─────────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-4 w-4 text-violet-400" />
            <h2 className="text-sm font-bold text-foreground uppercase tracking-widest">Residential Proxy</h2>
          </div>

          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            {/* Status bar */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
              <div className="flex items-center gap-2.5">
                {loadingStatus ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                ) : proxyActive ? (
                  <span className="flex h-2 w-2 rounded-full bg-violet-400 shadow-[0_0_6px_rgba(167,139,250,0.7)]" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
                )}
                <span className={cn("text-sm font-semibold", proxyActive ? "text-violet-300" : "text-muted-foreground")}>
                  {loadingStatus ? "Loading…" : proxyActive ? "Proxy Active" : "No Proxy Configured"}
                </span>
              </div>
              {proxyActive && !loadingStatus && (
                <span className="text-[10px] font-mono text-muted-foreground bg-muted border border-border rounded px-2 py-0.5 max-w-[240px] truncate">
                  {proxyUrlMasked}
                </span>
              )}
            </div>

            {/* Why use a proxy */}
            <div className="px-5 py-4 border-b border-border">
              <div className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 border border-violet-500/20">
                  <Info className="h-3.5 w-3.5 text-violet-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground mb-1">Why use a residential proxy?</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Replit runs on datacenter IPs that are blocked by telecom &amp; financial sites (Verizon, Frontier, AT&T, Cloudflare). A residential proxy routes browser traffic through a real home ISP so requests look like they come from a regular user.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {["Verizon", "AT&T", "Frontier", "Cloudflare", "Ticketmaster"].map((site) => (
                      <span key={site} className="text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">{site}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Input area */}
            <div className="px-5 py-4 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Proxy URL or curl command</label>
                <div className="relative">
                  {proxyInputVisible ? (
                    <textarea
                      value={proxyInput}
                      onChange={(e) => { setProxyInput(e.target.value); setProxyError(null); }}
                      placeholder={proxyActive ? "Enter new URL or curl command to replace…" : "http://user:pass@proxy.host.com:port\nor: curl -x http://user:pass@host:port https://ipinfo.io"}
                      rows={proxyInput.trim().toLowerCase().startsWith("curl") ? 3 : 1}
                      className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 pr-10 font-mono transition-colors resize-none"
                    />
                  ) : (
                    <input
                      type="password"
                      value={proxyInput}
                      onChange={(e) => { setProxyInput(e.target.value); setProxyError(null); }}
                      onKeyDown={(e) => e.key === "Enter" && handleSaveProxy()}
                      placeholder={proxyActive ? "Enter new URL to replace…" : "http://user:pass@proxy.host.com:port"}
                      className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 pr-10 font-mono transition-colors"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => setProxyInputVisible((v) => !v)}
                    className="absolute right-3 top-3 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                  >
                    {proxyInputVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground/60">
                  Paste a proxy URL (<code className="text-violet-400/80">http://user:pass@host:port</code>) or a full <code className="text-violet-400/80">curl -x ...</code> command — we'll extract the proxy automatically. Credentials are stored encrypted in the database and never logged.
                </p>
              </div>

              {/* Dynamic test target */}
              <div className="border-t border-border pt-3.5">
                <button
                  type="button"
                  onClick={() => setShowTestUrlInput((v) => !v)}
                  className="flex items-center justify-between w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <FlaskConical className="h-3.5 w-3.5" />
                    Test against a specific site (optional)
                  </span>
                  <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", showTestUrlInput && "rotate-90")} />
                </button>
                <AnimatePresence>
                  {showTestUrlInput && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pt-2.5 space-y-1.5">
                        <input
                          type="text"
                          value={proxyTestUrl}
                          onChange={(e) => setProxyTestUrl(e.target.value)}
                          placeholder="https://target-site.com (defaults to an IP-check service)"
                          className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 font-mono transition-colors"
                        />
                        <p className="text-[11px] text-muted-foreground/60">
                          By default the test tries a chain of IP-check services (not tied to one site). Enter a URL here to verify reachability against the actual target you plan to scrape instead.
                        </p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Error / success */}
              <AnimatePresence>
                {proxyError && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-start gap-2 rounded-xl bg-red-900/20 border border-red-500/20 px-3.5 py-2.5"
                  >
                    <AlertCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-xs text-red-300">{proxyError}</p>
                  </motion.div>
                )}
                {proxySaved && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-center gap-2 rounded-xl bg-emerald-900/20 border border-emerald-500/20 px-3.5 py-2.5"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <p className="text-xs text-emerald-300">Proxy saved and will persist across server restarts.</p>
                  </motion.div>
                )}
                {proxyTestResult && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-center gap-2.5 rounded-xl bg-violet-900/20 border border-violet-500/20 px-3.5 py-2.5"
                  >
                    <Wifi className="h-3.5 w-3.5 text-violet-400 shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-violet-300">Proxy working</p>
                      <p className="text-[11px] text-muted-foreground font-mono mt-0.5">Exit IP: {proxyTestResult.ip}</p>
                      {proxyTestResult.testedUrl && (
                        <p className="text-[10px] text-muted-foreground/60 font-mono mt-0.5 truncate">via {proxyTestResult.testedUrl}</p>
                      )}
                    </div>
                  </motion.div>
                )}
                {proxyTestError && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-start gap-2 rounded-xl bg-red-900/20 border border-red-500/20 px-3.5 py-2.5"
                  >
                    <WifiOff className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-xs text-red-300">{proxyTestError}</p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Action buttons */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 text-xs border-border text-muted-foreground hover:text-foreground hover:border-violet-500/40 disabled:opacity-40"
                  onClick={handleTestProxy}
                  disabled={proxyTesting || (!proxyInput.trim() && !proxyActive)}
                >
                  {proxyTesting
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <FlaskConical className="h-3.5 w-3.5" />}
                  {proxyTesting ? "Testing…" : "Test"}
                </Button>
                <Button
                  size="sm"
                  className="flex-1 gap-1.5 text-xs bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-40"
                  onClick={handleSaveProxy}
                  disabled={proxySaving || !proxyInput.trim()}
                >
                  {proxySaving
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <Shield className="h-3.5 w-3.5" />}
                  {proxySaving ? "Saving…" : proxyActive ? "Update Proxy" : "Save Proxy"}
                </Button>
                {proxyActive && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-xs border-red-900/40 text-red-400 hover:bg-red-900/10 hover:border-red-500/40 disabled:opacity-40"
                    onClick={handleDeleteProxy}
                    disabled={proxyDeleting}
                  >
                    {proxyDeleting
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Trash2 className="h-3.5 w-3.5" />}
                    {proxyDeleting ? "Removing…" : "Remove"}
                  </Button>
                )}
              </div>
            </div>

            {/* Provider examples */}
            <div className="border-t border-border">
              <button
                onClick={() => setShowProviderHint((v) => !v)}
                className="flex items-center justify-between w-full px-5 py-3 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Server className="h-3.5 w-3.5" />
                  Supported providers &amp; example URLs
                </span>
                <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", showProviderHint && "rotate-90")} />
              </button>
              <AnimatePresence>
                {showProviderHint && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-4 space-y-2">
                      {PROXY_PROVIDERS.map((p) => (
                        <div
                          key={p.name}
                          className="flex items-center justify-between rounded-xl bg-background border border-border px-3.5 py-2.5"
                        >
                          <div>
                            <p className="text-xs font-semibold text-foreground">{p.name}</p>
                            <p className="text-[10px] font-mono text-muted-foreground mt-0.5">{p.example}</p>
                          </div>
                          <button
                            onClick={() => handleCopyExample(p.example, p.name)}
                            className="ml-3 shrink-0 text-muted-foreground hover:text-violet-400 transition-colors"
                            title="Copy example URL"
                          >
                            {copiedProvider === p.name
                              ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                              : <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            }
                          </button>
                        </div>
                      ))}
                      <p className="text-[10px] text-muted-foreground pt-1">
                        Any HTTP/HTTPS proxy in the format <code className="text-violet-400/80">http://user:pass@host:port</code> is supported. SOCKS5 is not yet supported.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </section>

        {/* ── FloppyData Section ────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Zap className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-bold text-foreground uppercase tracking-widest">FloppyData</h2>
          </div>

          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            {/* Status bar */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
              <div className="flex items-center gap-2.5">
                {fdLoadingStatus ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                ) : fdActive ? (
                  <span className="flex h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.7)]" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
                )}
                <span className={cn("text-sm font-semibold", fdActive ? "text-amber-300" : "text-muted-foreground")}>
                  {fdLoadingStatus ? "Loading…" : fdActive ? "API Key Connected" : "No API Key Configured"}
                </span>
              </div>
              {fdActive && !fdLoadingStatus && (
                <span className="text-[10px] font-mono text-muted-foreground bg-muted border border-border rounded px-2 py-0.5 max-w-[240px] truncate">
                  {fdKeyMasked}
                </span>
              )}
            </div>

            {/* Info */}
            <div className="px-5 py-4 border-b border-border">
              <div className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <Info className="h-3.5 w-3.5 text-amber-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground mb-1">What is this for?</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Save your FloppyData API key here to check your account balance directly in the app. Get a key from{" "}
                    <span className="text-foreground font-semibold">app.floppydata.com/api-keys</span>.
                  </p>
                </div>
              </div>
            </div>

            {/* Balance display */}
            {fdActive && (
              <div className="px-5 py-4 border-b border-border">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Account Balance</label>
                  <button
                    onClick={handleFetchFdBalance}
                    disabled={fdBalanceLoading}
                    className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
                  >
                    <RefreshCw className={cn("h-3 w-3", fdBalanceLoading && "animate-spin")} />
                    Refresh
                  </button>
                </div>
                {fdBalanceLoading && !fdBalance && (
                  <p className="text-xs text-muted-foreground">Loading balance…</p>
                )}
                {fdBalanceError && (
                  <p className="text-xs text-red-300">{fdBalanceError}</p>
                )}
                {fdBalance && (
                  <pre className="text-[11px] font-mono text-foreground bg-background border border-border rounded-xl p-3 overflow-x-auto">
                    {JSON.stringify(fdBalance, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {/* Input area */}
            <div className="px-5 py-4 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">API Key</label>
                <div className="relative">
                  <input
                    type={fdInputVisible ? "text" : "password"}
                    value={fdInput}
                    onChange={(e) => { setFdInput(e.target.value); setFdError(null); }}
                    onKeyDown={(e) => e.key === "Enter" && handleSaveFdKey()}
                    placeholder={fdActive ? "Enter new API key to replace…" : "Paste your FloppyData API key…"}
                    className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/20 pr-10 font-mono transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setFdInputVisible((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                  >
                    {fdInputVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground/60">
                  Stored in your account only — never shared or logged.
                </p>
              </div>

              <AnimatePresence>
                {fdError && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-start gap-2 rounded-xl bg-red-900/20 border border-red-500/20 px-3.5 py-2.5"
                  >
                    <AlertCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-xs text-red-300">{fdError}</p>
                  </motion.div>
                )}
                {fdSaved && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    className="flex items-center gap-2 rounded-xl bg-emerald-900/20 border border-emerald-500/20 px-3.5 py-2.5"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <p className="text-xs text-emerald-300">API key saved.</p>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="flex-1 gap-1.5 text-xs bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-40"
                  onClick={handleSaveFdKey}
                  disabled={fdSaving || !fdInput.trim()}
                >
                  {fdSaving
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <Zap className="h-3.5 w-3.5" />}
                  {fdSaving ? "Saving…" : fdActive ? "Update Key" : "Save Key"}
                </Button>
                {fdActive && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-xs border-red-900/40 text-red-400 hover:bg-red-900/10 hover:border-red-500/40 disabled:opacity-40"
                    onClick={handleDeleteFdKey}
                    disabled={fdDeleting}
                  >
                    {fdDeleting
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Trash2 className="h-3.5 w-3.5" />}
                    {fdDeleting ? "Removing…" : "Remove"}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ── Connect Your Browser Section ─────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Link className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-bold text-foreground uppercase tracking-widest">Connect Your Browser</h2>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Connect your local Chrome browser via CDP to use your residential IP directly — no proxy needed. Use the{" "}
              <span className="text-foreground font-semibold">Connect Browser</span> button in the chat toolbar to set it up.
            </p>
          </div>
        </section>

        {/* ── Browser Engine Section ─────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Globe className="h-4 w-4 text-[#22D3EE]" />
            <h2 className="text-sm font-bold text-foreground uppercase tracking-widest">Browser Engine</h2>
          </div>
          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            {/* Info banner */}
            <div className="px-5 py-4 border-b border-border">
              <div className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#22D3EE]/10 border border-[#22D3EE]/20">
                  <Zap className="h-3.5 w-3.5 text-[#22D3EE]" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground mb-1">Why does this matter?</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Headless Chrome is the #1 bot-detection signal. Camoufox spoofs over 10 fingerprint vectors (GPU, fonts, canvas, WebGL) and runs as Firefox — nearly indistinguishable from a real desktop browser.
                  </p>
                </div>
              </div>
            </div>

            {/* Engine options */}
            <div className="px-5 py-4 space-y-3">
              {engineLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span className="text-xs">Loading…</span>
                </div>
              ) : (
                <>
                  {/* Camoufox option */}
                  <button
                    onClick={() => handleSetEngine("camoufox")}
                    disabled={engineSaving}
                    className={cn(
                      "w-full flex items-center justify-between rounded-xl border px-4 py-3 transition-all text-left",
                      browserEngine === "camoufox"
                        ? "border-[#22D3EE]/40 bg-[#22D3EE]/5"
                        : "border-border bg-background hover:border-[#22D3EE]/20 hover:bg-[#22D3EE]/5"
                    )}
                  >
                    <div>
                      <p className="text-xs font-semibold text-foreground">Camoufox – stealth Firefox</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Deep fingerprint spoofing, recommended for most sites</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {browserEngine === "camoufox" && (
                        <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-lg bg-[#22D3EE]/10 border border-[#22D3EE]/20 text-[#22D3EE]">Active</span>
                      )}
                      <div className={cn(
                        "h-4 w-4 rounded-full border-2 flex items-center justify-center shrink-0",
                        browserEngine === "camoufox" ? "border-[#22D3EE]" : "border-border"
                      )}>
                        {browserEngine === "camoufox" && <div className="h-2 w-2 rounded-full bg-[#22D3EE]" />}
                      </div>
                    </div>
                  </button>

                  {/* Chrome option */}
                  <button
                    onClick={() => handleSetEngine("chrome")}
                    disabled={engineSaving}
                    className={cn(
                      "w-full flex items-center justify-between rounded-xl border px-4 py-3 transition-all text-left",
                      browserEngine === "chrome"
                        ? "border-[#F59E0B]/40 bg-[#F59E0B]/5"
                        : "border-border bg-background hover:border-muted-foreground/30"
                    )}
                  >
                    <div>
                      <p className="text-xs font-semibold text-foreground">Chrome – headless Chromium</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Standard browser with stealth patches — more likely to be detected</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {browserEngine === "chrome" && (
                        <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-lg bg-[#F59E0B]/10 border border-[#F59E0B]/20 text-[#F59E0B]">Active</span>
                      )}
                      <div className={cn(
                        "h-4 w-4 rounded-full border-2 flex items-center justify-center shrink-0",
                        browserEngine === "chrome" ? "border-[#F59E0B]" : "border-border"
                      )}>
                        {browserEngine === "chrome" && <div className="h-2 w-2 rounded-full bg-[#F59E0B]" />}
                      </div>
                    </div>
                  </button>

                  <AnimatePresence>
                    {engineSaving && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                        className="flex items-center gap-2 text-muted-foreground"
                      >
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span className="text-xs">Switching engine… browser will restart on next run.</span>
                      </motion.div>
                    )}
                    {engineSaved && !engineSaving && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                        className="flex items-center gap-2 rounded-xl bg-emerald-900/20 border border-emerald-500/20 px-3.5 py-2.5"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                        <p className="text-xs text-emerald-300">Engine saved — takes effect on the next automation run.</p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </>
              )}
            </div>
          </div>
        </section>

      </div>
    </div>
  );
};
