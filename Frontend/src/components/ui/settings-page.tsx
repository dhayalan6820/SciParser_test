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
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface SettingsPageProps {
  onBack: () => void;
  userProfile: { username: string; email: string } | null;
}

const PROXY_PROVIDERS = [
  { name: "Brightdata", example: "http://user:pass@brd.superproxy.io:22225" },
  { name: "Oxylabs", example: "http://user:pass@pr.oxylabs.io:7777" },
  { name: "Smartproxy", example: "http://user:pass@gate.smartproxy.com:7000" },
  { name: "IPRoyal", example: "http://user:pass@geo.iproyal.com:12321" },
];

export const SettingsPage: React.FC<SettingsPageProps> = ({ onBack, userProfile }) => {
  const { theme } = useTheme();

  const [proxyActive, setProxyActive] = React.useState(false);
  const [proxyUrlMasked, setProxyUrlMasked] = React.useState<string | null>(null);
  const [proxyInput, setProxyInput] = React.useState("");
  const [proxyInputVisible, setProxyInputVisible] = React.useState(false);
  const [proxySaving, setProxySaving] = React.useState(false);
  const [proxyDeleting, setProxyDeleting] = React.useState(false);
  const [proxyError, setProxyError] = React.useState<string | null>(null);
  const [proxySaved, setProxySaved] = React.useState(false);
  const [proxyTesting, setProxyTesting] = React.useState(false);
  const [proxyTestResult, setProxyTestResult] = React.useState<{ ip: string } | null>(null);
  const [proxyTestError, setProxyTestError] = React.useState<string | null>(null);
  const [showProviderHint, setShowProviderHint] = React.useState(false);
  const [loadingStatus, setLoadingStatus] = React.useState(true);
  const [copiedProvider, setCopiedProvider] = React.useState<string | null>(null);

  const [browserEngine, setBrowserEngine] = React.useState<"camoufox" | "chrome">("camoufox");
  const [engineLoading, setEngineLoading] = React.useState(true);
  const [engineSaving, setEngineSaving] = React.useState(false);
  const [engineSaved, setEngineSaved] = React.useState(false);

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
  }, []);

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
      const res = await sciparserApi.testProxy(proxyInput.trim() || undefined);
      setProxyTestResult({ ip: res.exit_ip });
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
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Proxy URL</label>
                <div className="relative">
                  <input
                    type={proxyInputVisible ? "text" : "password"}
                    value={proxyInput}
                    onChange={(e) => { setProxyInput(e.target.value); setProxyError(null); }}
                    onKeyDown={(e) => e.key === "Enter" && handleSaveProxy()}
                    placeholder={proxyActive ? "Enter new URL to replace…" : "http://user:pass@proxy.host.com:port"}
                    className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 pr-10 font-mono transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setProxyInputVisible((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                  >
                    {proxyInputVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground/60">
                  Credentials are stored encrypted in the database and never logged.
                </p>
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
