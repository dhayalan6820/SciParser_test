import React, { useState, useEffect, useRef } from 'react';
import { 
  Globe, RefreshCw,
  Maximize2, Minimize2, X, Terminal, Code, Check,
  Search, Trash2, ZoomIn, ZoomOut, Grid3X3,
  Loader2, AlertCircle, ShieldCheck, Wifi, WifiOff, CheckCircle2,
  ChevronUp, ChevronDown, PowerOff
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../../lib/utils';
import { Button } from './button';

interface MousePos {
  x: number;
  y: number;
  event: string;
  vpW: number;
  vpH: number;
}

// Maps raw MCP tool names to short, friendly phrases for the live activity
// notification. Matched by substring (not exact) since tool names vary
// slightly between MCP servers (e.g. `browser_navigate` vs `navigate_to`).
// Order matters — more specific patterns are checked before generic ones.
const TOOL_LABEL_PATTERNS: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /navigate|goto|open_url/i, label: 'Browser navigated' },
  { pattern: /screenshot|snapshot|capture/i, label: 'Capturing screenshot' },
  { pattern: /key_press|press_key|keyboard/i, label: 'Pressing key' },
  { pattern: /hover/i, label: 'Hovering element' },
  { pattern: /scroll/i, label: 'Scrolling page' },
  { pattern: /select|dropdown|option/i, label: 'Selecting option' },
  { pattern: /type|fill|input_text|input/i, label: 'Typing text' },
  { pattern: /click|tap|button/i, label: 'Button clicked' },
  { pattern: /wait/i, label: 'Waiting for page' },
  { pattern: /extract|read_text|get_text|content/i, label: 'Reading page content' },
  { pattern: /find|locate|check_element|query|inspect/i, label: 'Checking element' },
  { pattern: /close|quit|shutdown/i, label: 'Closing browser' },
  { pattern: /back|forward|history/i, label: 'Changing page' },
];

/** Turn `browser_navigate` / `browser-navigate` into "Browser navigate" as a last-resort fallback. */
function humanizeToolName(toolName: string): string {
  const words = toolName.replace(/^browser[_-]/i, '').split(/[_-]/).filter(Boolean);
  if (words.length === 0) return 'Working';
  return words
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(' ');
}

function getFriendlyToolLabel(toolName?: string | null): string {
  if (!toolName) return 'Working…';
  const match = TOOL_LABEL_PATTERNS.find(({ pattern }) => pattern.test(toolName));
  return match ? match.label : humanizeToolName(toolName);
}

// Pulls a short, human-readable target snippet (e.g. a button's text, a
// field's label, or the URL being navigated to) out of a tool call's raw
// arguments. Different MCP servers name these fields differently, so we try
// a prioritized list of common keys rather than a single fixed shape.
// Typing/selecting actions prioritize the *field* identifier over the typed
// value, since the value itself (e.g. a password) isn't a useful "target".
function getToolTargetDetail(toolName?: string | null, toolInput?: unknown): string | null {
  if (!toolInput || typeof toolInput !== 'object') return null;
  const input = toolInput as Record<string, unknown>;

  const isTypingOrSelecting = !!toolName && /type|fill|input_text|input|select|dropdown|option/i.test(toolName);
  const keysByPriority = isTypingOrSelecting
    ? ['label', 'field', 'field_name', 'placeholder', 'name', 'aria_label', 'element_text', 'selector', 'element']
    : ['text', 'button_text', 'label', 'element_text', 'aria_label', 'name', 'placeholder', 'selector', 'element', 'url'];

  for (const key of keysByPriority) {
    const value = input[key];
    if (typeof value === 'string' && value.trim()) {
      const trimmed = value.trim();
      return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed;
    }
  }
  return null;
}

interface BrowserPreviewProps {
  frame: string | null;
  isActive: boolean;
  onClose: () => void;
  toolLogs: any[];
  isAiTyping: boolean;
  activeThreadId?: string;
  isSelectionMode?: boolean;
  selectedTools?: string[];
  mousePos?: MousePos | null;
  onToggleToolSelection?: (id: string) => void;
  onClearLogs?: () => void;
  browserEngine?: "camoufox" | "chrome" | null;
  onCloseBrowser?: () => void;
  onCancelStep?: () => void;
  isCancellingStep?: boolean;
}

export function BrowserPreview({ 
  frame, 
  isActive, 
  onClose,
  toolLogs,
  isAiTyping,
  activeThreadId,
  isSelectionMode,
  selectedTools = [],
  mousePos,
  onToggleToolSelection,
  onClearLogs,
  browserEngine,
  onCloseBrowser,
  onCancelStep,
  isCancellingStep = false,
}: BrowserPreviewProps) {
  const [isFullSize, setIsFullSize]       = useState(false);
  const [zoom, setZoom]                   = useState(100);
  const [showGrid, setShowGrid]           = useState(false);
  const [showToolLog, setShowToolLog]     = useState(false);
  const [searchQuery, setSearchQuery]     = useState('');
  const [logFilter, setLogFilter]         = useState<'all' | 'success' | 'error'>('all');
  const [autoScroll, setAutoScroll]       = useState(true);
  const [clickPulse, setClickPulse]       = useState(false);
  const [cursorPx, setCursorPx]           = useState<{ x: number; y: number } | null>(null);
  const [nowTick, setNowTick]             = useState(() => Date.now());
  const logsEndRef    = useRef<HTMLDivElement>(null);
  const popupRef      = useRef<HTMLDivElement>(null);
  const viewportRef   = useRef<HTMLDivElement>(null);

  // Latest tool activity for the friendly notification strip below the
  // preview image. New entries are always pushed to the end of `toolLogs`
  // (see chat_page.tsx's tool_start/tool_output handling), so the last item
  // is always the most recent action — whether still running or finished.
  const latestToolLog = toolLogs.length > 0 ? toolLogs[toolLogs.length - 1] : null;
  const latestActivityLabel = getFriendlyToolLabel(latestToolLog?.tool_name);
  const latestActivityTarget = getToolTargetDetail(latestToolLog?.tool_name, latestToolLog?.tool_input);

  // Threshold beyond which an IN_PROGRESS step is considered "taking longer
  // than usual" and should surface elapsed time / stuck messaging instead of
  // looking identical to a fast, normal in-progress state.
  const SLOW_STEP_THRESHOLD_MS = 8000;

  // Threshold beyond which an IN_PROGRESS step is treated as hard-stalled
  // rather than merely slow — at this point the timer alone isn't enough
  // feedback, so the notification also offers a way to cancel the run
  // instead of leaving the user only able to watch or abandon it entirely.
  const HARD_STALL_THRESHOLD_MS = 30000;

  // Tick every second while the latest step is still running so the elapsed
  // timer stays live. Only runs while there's an actual IN_PROGRESS entry to
  // avoid a background interval when the panel is idle/finished.
  useEffect(() => {
    if (latestToolLog?.status !== 'IN_PROGRESS') return;
    setNowTick(Date.now());
    const interval = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [latestToolLog?.id, latestToolLog?.status]);

  const latestStepElapsedMs = (() => {
    if (latestToolLog?.status !== 'IN_PROGRESS' || !latestToolLog?.created_at) return 0;
    const started = new Date(latestToolLog.created_at).getTime();
    if (Number.isNaN(started)) return 0;
    return Math.max(0, nowTick - started);
  })();
  const isLatestStepSlow = latestStepElapsedMs >= SLOW_STEP_THRESHOLD_MS;
  const isLatestStepStalled = latestStepElapsedMs >= HARD_STALL_THRESHOLD_MS;
  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes > 0 ? `${minutes}:${String(seconds).padStart(2, '0')}` : `${seconds}s`;
  };

  // Recompute cursor pixel position whenever mousePos, zoom, or viewport size changes
  useEffect(() => {
    if (!mousePos || !viewportRef.current) { setCursorPx(null); return; }
    const el = viewportRef.current;
    const cw = el.clientWidth;
    const ch = el.clientHeight;
    const vpW = mousePos.vpW || 1280;
    const vpH = mousePos.vpH || 800;
    // CSS transform:scale(zoom/100) shrinks/grows the image around its centre
    // without changing layout dimensions, so we factor zoom into display size.
    const z = zoom / 100;
    const scale = Math.min(cw / vpW, ch / vpH);
    const displayW = vpW * scale * z;
    const displayH = vpH * scale * z;
    const offsetX = (cw - displayW) / 2;
    const offsetY = (ch - displayH) / 2;
    setCursorPx({
      x: mousePos.x * scale * z + offsetX,
      y: mousePos.y * scale * z + offsetY,
    });
    if (mousePos.event === 'click') {
      setClickPulse(true);
      const t = setTimeout(() => setClickPulse(false), 350);
      return () => clearTimeout(t);
    }
  }, [mousePos, zoom]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current && showToolLog) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [toolLogs, autoScroll, showToolLog]);

  // Close popup on outside click
  useEffect(() => {
    if (!showToolLog) return;
    const handler = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setShowToolLog(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showToolLog]);

  if (!isActive) return null;

  const filteredLogs = toolLogs.filter(log => {
    const matchesSearch = log.tool_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          JSON.stringify(log.tool_input || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = logFilter === 'all' ||
                          (logFilter === 'success' && log.status === 'SUCCESS') ||
                          (logFilter === 'error'   && log.status === 'FAILED');
    return matchesSearch && matchesFilter;
  });

  const runningCount = toolLogs.filter(l => l.status === 'IN_PROGRESS').length;
  // Derive the current URL from the most-recent tool call that looks like a navigation.
  // browser-use names its navigate tool differently across versions (go_to_url,
  // browser_navigate_to, navigate_to, browser_navigate, etc.) so we do a broad
  // name-substring check and also fall back to any tool that carried a "url" arg.
  const currentUrl = (() => {
    const reversed = [...toolLogs].reverse();
    const navLog = reversed.find(l => {
      const n = (l.tool_name || '').toLowerCase();
      return n.includes('navigate') || n.includes('go_to') || n.includes('goto') || n.includes('open_url') || n.includes('open_tab');
    });
    const fromNav = navLog?.tool_input?.url || navLog?.tool_input?.URL || navLog?.tool_input?.href;
    if (fromNav) return fromNav;
    // Fallback: any tool that received a URL argument
    const anyUrl = reversed.find(l => l.tool_input?.url)?.tool_input?.url;
    return anyUrl || 'about:blank';
  })();

  const formatTime = (iso?: string) => {
    if (!iso) return '';
    try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }); }
    catch { return ''; }
  };

  const wrapCls = isFullSize
    ? "fixed inset-0 z-[300] flex flex-col bg-background"
    : "flex flex-col h-full w-full bg-background";

  return (
    <div className={cn(wrapCls, "text-foreground overflow-hidden")}>
      <div className="flex flex-col h-full w-full overflow-hidden">

        {/* ── Toolbar ───────────────────────────────────────────────────── */}
        <div className="shrink-0 flex items-center gap-2 px-3 py-2.5 border-b border-border bg-card">

          {/* Brand */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-400/10">
              <Globe className="h-3.5 w-3.5 text-sky-400" />
            </div>
            <div className="hidden sm:block leading-none">
              <div className="text-[11px] font-black uppercase tracking-widest text-foreground">Live Browser</div>
              <div className="flex items-center gap-1 mt-0.5">
                <div className={cn("h-1.5 w-1.5 rounded-full", frame ? "bg-emerald-400 animate-pulse" : "bg-amber-400")} />
                <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">{frame ? "Connected" : "Connecting"}</span>
              </div>
            </div>
          </div>

          {/* Engine badge */}
          {browserEngine && (
            <div className={cn(
              "hidden sm:flex items-center gap-1 px-2 py-0.5 rounded-md border text-[9px] font-bold uppercase tracking-wider shrink-0",
              browserEngine === "camoufox"
                ? "bg-sky-400/10 border-sky-400/20 text-sky-400"
                : "bg-muted border-border text-muted-foreground"
            )}>
              {browserEngine === "camoufox" ? "Firefox · Camoufox" : "Chrome · Headless"}
            </div>
          )}

          {/* URL bar */}
          <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/40 border border-border min-w-0">
            <ShieldCheck className="h-3 w-3 text-emerald-400/70 shrink-0" />
            <span className="flex-1 truncate text-[12px] text-muted-foreground select-all font-mono">{currentUrl}</span>
          </div>

          {/* Tool Log button — full-width pill with count badge */}
          <div className="relative shrink-0" ref={popupRef}>
            <button
              onClick={() => setShowToolLog((v) => !v)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider border transition-all",
                showToolLog
                  ? "bg-sky-500/15 border-sky-500/40 text-sky-400"
                  : "bg-muted border-border text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              <Terminal className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Tool Log</span>
              {toolLogs.length > 0 && (
                <span className={cn(
                  "ml-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-black tabular-nums",
                  runningCount > 0 ? "bg-sky-500/30 text-sky-400" : "bg-muted-foreground/20 text-muted-foreground"
                )}>
                  {toolLogs.length}
                </span>
              )}
              {showToolLog ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>

            {/* ── Tool Log Popup ─────────────────────────────────────────── */}
            <AnimatePresence>
              {showToolLog && (
                <motion.div
                  initial={{ opacity: 0, y: -8, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.97 }}
                  transition={{ duration: 0.15 }}
                  className="fixed right-4 top-16 w-[min(520px,90vw)] z-[500] rounded-2xl border border-border bg-popover shadow-[0_24px_64px_rgba(0,0,0,0.4)] overflow-hidden"
                >
                  {/* Popup header */}
                  <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/20">
                    <div className="flex items-center gap-2">
                      <Terminal className="h-3.5 w-3.5 text-sky-400" />
                      <span className="text-[11px] font-black uppercase tracking-[0.2em] text-foreground">Tool Execution Log</span>
                      <span className="text-[10px] text-muted-foreground font-medium">({toolLogs.length} calls)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => { onClearLogs?.(); }}
                        className="text-[10px] font-bold text-muted-foreground hover:text-destructive transition-colors uppercase tracking-wider"
                      >
                        Clear
                      </button>
                      <button onClick={() => setShowToolLog(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {/* Search + filter */}
                  <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                    <div className="relative flex-1">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search logs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-7 pr-3 py-1.5 rounded-lg bg-muted/40 border border-border text-[11px] text-foreground outline-none placeholder:text-muted-foreground focus:border-sky-500/30"
                      />
                    </div>
                    <div className="flex gap-1">
                      {(['all', 'success', 'error'] as const).map((f) => (
                        <button
                          key={f}
                          onClick={() => setLogFilter(f)}
                          className={cn(
                            "px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-wider transition-all",
                            logFilter === f ? "bg-sky-500 text-white" : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Log list */}
                  <div className="max-h-[420px] overflow-y-auto p-3 space-y-2 font-mono">
                    {filteredLogs.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-10 gap-2 text-muted-foreground">
                        <Code className="h-8 w-8 opacity-30" />
                        <span className="text-[10px] font-bold uppercase tracking-widest">No activity</span>
                      </div>
                    ) : (
                      filteredLogs.map((log, idx) => {
                        const st = log.status;
                        const isSelected = selectedTools.includes(log.id || String(idx));
                        return (
                          <motion.div
                            key={log.id || idx}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={cn(
                              "group relative flex flex-col gap-2 p-3 rounded-xl border transition-all",
                              st === 'IN_PROGRESS' ? "border-sky-500/25 bg-sky-500/[0.04]" :
                              st === 'SUCCESS'     ? "border-emerald-500/15 bg-emerald-500/[0.03]" :
                                                     "border-red-500/15 bg-red-500/[0.03]",
                              isSelectionMode && isSelected && "ring-1 ring-sky-500"
                            )}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="text-[9px] font-bold text-muted-foreground tabular-nums">{String(idx + 1).padStart(2,'0')}</span>
                                <span className={cn(
                                  "text-[11px] font-bold truncate",
                                  st === 'IN_PROGRESS' ? "text-sky-400" :
                                  st === 'SUCCESS'     ? "text-emerald-500" : "text-red-400"
                                )}>
                                  {log.tool_name}
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span className={cn(
                                  "px-1.5 py-0.5 rounded text-[9px] font-black uppercase",
                                  st === 'IN_PROGRESS' ? "bg-sky-500/20 text-sky-400" :
                                  st === 'SUCCESS'     ? "bg-emerald-500/20 text-emerald-500" : "bg-red-500/20 text-red-400"
                                )}>
                                  {st}
                                </span>
                                {formatTime(log.created_at) && (
                                  <span className="text-[9px] text-muted-foreground">{formatTime(log.created_at)}</span>
                                )}
                              </div>
                            </div>
                            <div className="space-y-1.5">
                              <div>
                                <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest block mb-1">Input</span>
                                <div className="text-[10px] text-foreground bg-muted/40 px-2 py-1.5 rounded-lg border border-border break-all leading-relaxed">
                                  {typeof log.tool_input === 'string' ? log.tool_input : JSON.stringify(log.tool_input)}
                                </div>
                              </div>
                              {log.tool_output && (
                                <div>
                                  <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest block mb-1">Output</span>
                                  <div className="text-[10px] text-muted-foreground bg-muted/20 px-2 py-1.5 rounded-lg border border-border break-words leading-relaxed line-clamp-3">
                                    {String(log.tool_output)}
                                  </div>
                                </div>
                              )}
                            </div>
                            {isSelectionMode && (
                              <div className={cn(
                                "absolute top-2 right-2 h-4 w-4 rounded-full border flex items-center justify-center",
                                isSelected ? "bg-sky-500 border-sky-500" : "bg-muted/40 border-border"
                              )}>
                                {isSelected && <Check className="h-2.5 w-2.5 text-white" />}
                              </div>
                            )}
                          </motion.div>
                        );
                      })
                    )}
                    <div ref={logsEndRef} />
                  </div>

                  {/* Popup footer */}
                  <div className="px-4 py-2.5 border-t border-border bg-muted/10 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={cn("h-1.5 w-1.5 rounded-full", isAiTyping ? "bg-sky-400 animate-pulse" : "bg-muted-foreground/30")} />
                      <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest">
                        {isAiTyping ? 'Agent running' : 'Idle'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-muted-foreground">Auto-scroll</span>
                      <button
                        onClick={() => setAutoScroll(!autoScroll)}
                        className={cn(
                          "w-7 h-3.5 rounded-full relative transition-all",
                          autoScroll ? "bg-emerald-500" : "bg-muted"
                        )}
                      >
                        <div className={cn(
                          "absolute top-0.5 h-2.5 w-2.5 rounded-full bg-white transition-all",
                          autoScroll ? "left-[14px]" : "left-0.5"
                        )} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

        </div>

        {/* ── Browser viewport — takes all remaining height ─────────────── */}
        <div className="flex-1 relative flex flex-col overflow-hidden bg-background">

          {/* Floating control bar — overlays the top of the live preview itself */}
          <div className="absolute top-3 right-3 z-40 flex items-center gap-1.5 px-1.5 py-1.5 rounded-xl bg-background/85 backdrop-blur-md border border-border shadow-lg">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsFullSize(!isFullSize)}
              className="h-7 px-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent gap-1.5 shrink-0"
            >
              {isFullSize ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              <span className="text-[10px] font-bold uppercase tracking-wider">
                {isFullSize ? 'Exit' : 'Full Size'}
              </span>
            </Button>

            {onCloseBrowser && (
              <Button
                variant="outline"
                size="sm"
                onClick={onCloseBrowser}
                className="h-7 px-2.5 rounded-lg gap-1.5 shrink-0 text-red-500 border-red-200 hover:bg-red-50 dark:border-red-900/30 dark:hover:bg-red-900/10"
              >
                <PowerOff className="h-3.5 w-3.5" />
                <span className="text-[10px] font-bold uppercase tracking-wider">Close Browser</span>
              </Button>
            )}

            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-7 w-7 rounded-lg text-destructive/70 hover:text-destructive hover:bg-destructive/10 shrink-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {frame ? (
            <div
              ref={viewportRef}
              className="flex-1 flex items-center justify-center overflow-hidden relative"
              style={{ cursor: 'default' }}
            >
              {showGrid && (
                <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(255,255,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[size:40px_40px]" />
              )}
              <motion.img
                key="frame"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                src={frame.startsWith('data:') ? frame : `data:image/jpeg;base64,${frame}`}
                alt="Live Browser"
                style={{ transform: `scale(${zoom / 100})` }}
                className="w-full h-full object-contain"
                draggable={false}
              />

              {/* ── Agent cursor overlay ────────────────────────────────── */}
              {cursorPx && isAiTyping && (
                <div
                  className="pointer-events-none absolute"
                  style={{
                    left: cursorPx.x,
                    top: cursorPx.y,
                    transform: 'translate(-50%, -50%)',
                    transition: 'left 0.12s ease-out, top 0.12s ease-out',
                    zIndex: 50,
                  }}
                >
                  {/* Click pulse ring */}
                  {clickPulse && (
                    <div
                      className="absolute rounded-full border-2 border-red-400"
                      style={{
                        width: 36,
                        height: 36,
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        animation: 'cursorPulse 0.35s ease-out forwards',
                      }}
                    />
                  )}
                  {/* Cursor dot */}
                  <div
                    className="rounded-full bg-red-500 border-2 border-white shadow-lg shadow-red-500/50"
                    style={{ width: 16, height: 16 }}
                  />
                </div>
              )}

              {/* Hover controls */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 px-2 py-1.5 rounded-xl bg-background/70 backdrop-blur-md border border-border opacity-0 hover:opacity-100 focus-within:opacity-100 transition-opacity shadow-xl group">
                <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.max(50, z - 10))} className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
                  <ZoomOut className="h-3.5 w-3.5" />
                </Button>
                <span className="text-[10px] font-black w-9 text-center text-muted-foreground">{zoom}%</span>
                <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.min(200, z + 10))} className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
                  <ZoomIn className="h-3.5 w-3.5" />
                </Button>
                <div className="h-4 w-px bg-border mx-1" />
                <Button variant="ghost" size="icon" onClick={() => setShowGrid(!showGrid)} className={cn("h-7 w-7 rounded-lg transition-colors", showGrid ? "text-sky-400 bg-sky-400/10" : "text-muted-foreground hover:text-foreground hover:bg-accent")}>
                  <Grid3X3 className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setZoom(100)} className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
                  <RefreshCw className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ) : null}

          {/* ── Live activity notification — friendly, at-a-glance summary of the
              agent's most recent tool action, shown just below the preview
              image only while a run is actually in progress (isAiTyping).
              Gating on isAiTyping (not just isActive/panel-open) prevents the
              strip from showing stale activity once a run has finished but
              the preview panel is still open. This intentionally mirrors
              only the LATEST entry from `toolLogs`; the full history stays in
              the separate Tool Log popup above. */}
          <AnimatePresence mode="wait">
            {isActive && frame && isAiTyping && latestToolLog && (
              <motion.div
                key={latestToolLog.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className="shrink-0 px-4 py-2 border-t border-border bg-card/60 backdrop-blur-sm flex items-center gap-2"
              >
                {latestToolLog.status === 'IN_PROGRESS' ? (
                  <Loader2 className={cn("h-3 w-3 shrink-0 animate-spin", isLatestStepSlow ? "text-amber-400" : "text-sky-400")} />
                ) : latestToolLog.status === 'FAILED' ? (
                  <AlertCircle className="h-3 w-3 text-amber-400 shrink-0" />
                ) : (
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0" />
                )}
                <span className="text-[11px] font-semibold text-foreground/80 truncate">
                  {latestActivityLabel}
                  {latestActivityTarget && (
                    <span className="font-normal text-foreground/60"> — {latestActivityTarget}</span>
                  )}
                </span>
                {latestToolLog.status === 'IN_PROGRESS' && isLatestStepSlow && (
                  <span className="ml-auto flex items-center gap-1.5 shrink-0 pl-2">
                    <span
                      className={cn(
                        "text-[9px] font-bold uppercase tracking-widest",
                        isLatestStepStalled ? "text-red-400/90" : "text-amber-400/90",
                      )}
                    >
                      {isLatestStepStalled ? "Stuck" : "Still working"}
                    </span>
                    <span
                      className={cn(
                        "text-[10px] font-bold tabular-nums rounded px-1.5 py-0.5 border",
                        isLatestStepStalled
                          ? "text-red-400/90 bg-red-400/10 border-red-400/20"
                          : "text-amber-400/90 bg-amber-400/10 border-amber-400/20",
                      )}
                    >
                      {formatElapsed(latestStepElapsedMs)}
                    </span>
                    {/* Once a step has been running well beyond the "still
                        working" threshold, it's reasonable to suspect it's
                        actually stuck rather than just slow — offer a direct
                        way to cancel instead of leaving the user only able to
                        watch the timer or abandon the whole session. */}
                    {isLatestStepStalled && onCancelStep && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={isCancellingStep}
                        onClick={onCancelStep}
                        className="h-6 px-2 text-[9px] font-black uppercase tracking-widest text-red-500 hover:text-red-600 hover:bg-red-500/10 gap-1 shrink-0"
                      >
                        {isCancellingStep ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <X className="h-3 w-3" />
                        )}
                        {isCancellingStep ? "Cancelling…" : "Cancel step"}
                      </Button>
                    )}
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {!frame && (
            <div className="flex-1 flex flex-col items-center justify-center gap-5 text-muted-foreground/30">
              <div className="relative">
                <Loader2 className="h-10 w-10 text-sky-400 animate-spin" />
                <div className="absolute inset-0 blur-xl bg-sky-400/15 animate-pulse" />
              </div>
              <div className="text-center space-y-1">
                <p className="text-sm font-black uppercase tracking-[0.2em] text-foreground/70">Initializing Stream</p>
                <p className="text-[11px] text-muted-foreground/30">Establishing secure CDP connection…</p>
              </div>
            </div>
          )}

          {/* Status bar */}
          <div className="shrink-0 h-9 border-t border-border bg-card/40 px-4 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {frame ? (
                <>
                  <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                  <span className="text-[9px] font-bold text-emerald-500/80 uppercase tracking-wider">Page loaded</span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-3 w-3 text-amber-400" />
                  <span className="text-[9px] font-bold text-amber-400/80 uppercase tracking-wider">Waiting for page…</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {frame ? (
                <>
                  <Wifi className="h-3 w-3 text-emerald-500" />
                  <span className="text-[9px] font-black text-emerald-400/80">STABLE</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3 text-amber-400" />
                  <span className="text-[9px] font-black text-amber-400/80">CONNECTING</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
