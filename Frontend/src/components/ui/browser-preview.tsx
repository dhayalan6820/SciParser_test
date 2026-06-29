import React, { useState, useEffect, useRef } from 'react';
import { 
  Globe, RefreshCw, ChevronLeft, ChevronRight, Home, 
  Maximize2, Minimize2, Monitor, Layout, ExternalLink, 
  MousePointer2, Camera, Download, Settings, X, 
  Terminal, Code, Check, Copy, RotateCcw, Search, 
  Filter, Trash2, DownloadCloud, Play, Pause, Square,
  ZoomIn, ZoomOut, Grid3X3, Moon, Sun, Clock, Zap, Activity,
  Loader2, AlertCircle, ShieldCheck, Cpu, Wifi, WifiOff, CheckCircle2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../../lib/utils';
import { Button } from './button';

interface BrowserPreviewProps {
  frame: string | null;
  isActive: boolean;
  onClose: () => void;
  toolLogs: any[];
  isAiTyping: boolean;
  activeThreadId?: string;
  isSelectionMode?: boolean;
  selectedTools?: string[];
  onToggleToolSelection?: (id: string) => void;
  onClearLogs?: () => void;
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
  onToggleToolSelection,
  onClearLogs
}: BrowserPreviewProps) {
  const [viewMode, setViewMode] = useState<'split' | 'browser' | 'logs'>('split');
  const [isFullSize, setIsFullSize] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [autoScroll, setAutoScroll] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [logFilter, setLogFilter] = useState<'all' | 'success' | 'error' | 'running'>('all');
  const [isDark, setIsDark] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [browserHeight, setBrowserHeight] = useState(65); // Browser height %
  const containerRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [toolLogs, autoScroll]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsResizing(true);
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !workspaceRef.current) return;
      const containerRect = workspaceRef.current.getBoundingClientRect();
      const newHeight = ((e.clientY - containerRect.top) / containerRect.height) * 100;
      if (newHeight > 20 && newHeight < 85) {
        setBrowserHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  if (!isActive) return null;

  const filteredLogs = toolLogs.filter(log => {
    const matchesSearch = log.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                         JSON.stringify(log.tool_input).toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = logFilter === 'all' || 
                         (logFilter === 'success' && log.status === 'SUCCESS') ||
                         (logFilter === 'error' && log.status === 'FAILED') ||
                         (logFilter === 'running' && log.status === 'IN_PROGRESS');
    return matchesSearch && matchesFilter;
  });

  const browserStatus = frame ? 'Connected' : 'Connecting';

  return (
    <div 
      ref={containerRef}
      className={cn(
        "flex flex-col h-full w-full bg-[#05070A] text-[#F8FAFC] overflow-hidden transition-all duration-500",
        isFullSize && "fixed inset-0 z-[200] p-4 bg-black/80 backdrop-blur-xl"
      )}
    >
      <div className={cn(
        "flex flex-col h-full w-full rounded-[20px] border border-[#232B36] bg-[#0B0F14] shadow-[0_20px_70px_rgba(0,0,0,0.48)] overflow-hidden",
        isFullSize && "max-w-[1600px] mx-auto"
      )}>
        {/* Browser Header / Toolbar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#232B36] bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-4 min-w-0 flex-1">
            <div className="flex items-center gap-2 shrink-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#22D3EE]/10 text-[#22D3EE]">
                <Globe className="h-4 w-4" />
              </div>
              <div className="hidden sm:block">
                <div className="text-[13px] font-black uppercase tracking-wider">Live Browser</div>
                <div className="flex items-center gap-1.5">
                  <div className={cn("h-1.5 w-1.5 rounded-full", frame ? "bg-[#10B981] animate-pulse" : "bg-[#F59E0B]")} />
                  <span className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-widest">{browserStatus}</span>
                </div>
              </div>
            </div>

            {/* URL Bar */}
            <div className="flex-1 max-w-2xl flex items-center gap-2 px-3 py-1.5 rounded-xl bg-black/40 border border-[#232B36] group focus-within:border-[#22D3EE]/40 transition-all">
              <div className="flex items-center gap-1 shrink-0">
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg hover:bg-white/5 text-[#9CA3AF]"><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg hover:bg-white/5 text-[#9CA3AF]"><ChevronRight className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg hover:bg-white/5 text-[#9CA3AF]"><RefreshCw className="h-3.5 w-3.5" /></Button>
              </div>
              <div className="h-4 w-px bg-[#232B36] mx-1" />
              <div className="flex-1 truncate text-[13px] font-medium text-[#CBD5E1] select-all">
                {toolLogs.find(l => l.tool_name === 'browser_navigate')?.tool_input?.url || 'https://www.google.com'}
              </div>
              <ShieldCheck className="h-3.5 w-3.5 text-[#10B981] shrink-0" />
            </div>
          </div>

          <div className="flex items-center gap-1.5 ml-4 shrink-0">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setIsFullSize(!isFullSize)}
              className="h-9 px-3 rounded-xl hover:bg-white/5 text-[#9CA3AF] gap-2"
            >
              {isFullSize ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              <span className="text-[11px] font-bold uppercase tracking-wider hidden md:block">{isFullSize ? 'Exit Full Size' : 'View Full Size'}</span>
            </Button>
            <div className="h-6 w-px bg-[#232B36] mx-1" />
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={onClose}
              className="h-9 w-9 rounded-xl hover:bg-red-500/10 text-red-400"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Main Workspace Area */}
        <div ref={workspaceRef} className="flex-1 flex flex-col overflow-hidden relative">
          {/* Top Panel: Browser Stream */}
          <div 
            style={{ height: viewMode === 'browser' ? '100%' : viewMode === 'logs' ? '0%' : `${browserHeight}%` }}
            className={cn(
              "flex flex-col w-full bg-black relative transition-all duration-300 shrink-0",
              viewMode === 'logs' && "hidden"
            )}
          >
            <div className="flex-1 flex items-center justify-center overflow-hidden p-4 relative">
              {showGrid && (
                <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(255,255,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[size:40px_40px]" />
              )}
              
              {frame ? (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="relative group"
                  style={{ transform: `scale(${zoom / 100})` }}
                >
                  <img 
                    src={frame.startsWith('data:') ? frame : `data:image/png;base64,${frame}`} 
                    alt="Live Browser" 
                    className="max-w-full max-h-full object-contain shadow-[0_30px_100px_rgba(0,0,0,0.8)] border border-white/5 rounded-lg"
                  />
                  
                  {/* Floating Browser Controls */}
                  <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1 p-1.5 rounded-2xl bg-[#111827]/80 backdrop-blur-xl border border-[#232B36] shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0">
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-xl hover:bg-white/10 text-white"><Camera className="h-4 w-4" /></Button>
                    <div className="h-4 w-px bg-[#232B36] mx-1" />
                    <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.max(50, z - 10))} className="h-8 w-8 rounded-xl hover:bg-white/10 text-white"><ZoomOut className="h-4 w-4" /></Button>
                    <span className="text-[10px] font-black w-10 text-center">{zoom}%</span>
                    <Button variant="ghost" size="icon" onClick={() => setZoom(z => Math.min(200, z + 10))} className="h-8 w-8 rounded-xl hover:bg-white/10 text-white"><ZoomIn className="h-4 w-4" /></Button>
                    <div className="h-4 w-px bg-[#232B36] mx-1" />
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => setShowGrid(!showGrid)}
                      className={cn("h-8 w-8 rounded-xl hover:bg-white/10", showGrid ? "text-[#22D3EE]" : "text-white")}
                    >
                      <Grid3X3 className="h-4 w-4" />
                    </Button>
                  </div>
                </motion.div>
              ) : (
                <div className="flex flex-col items-center gap-6 text-[#64748B]">
                  <div className="relative">
                    <Loader2 className="h-12 w-12 text-[#22D3EE] animate-spin" />
                    <div className="absolute inset-0 blur-xl bg-[#22D3EE]/20 animate-pulse" />
                  </div>
                  <div className="flex flex-col items-center gap-2">
                    <span className="text-sm font-black uppercase tracking-[0.2em] text-[#F8FAFC]">Initializing Stream</span>
                    <span className="text-[11px] font-medium opacity-60">Establishing secure CDP connection...</span>
                  </div>
                </div>
              )}
            </div>

            {/* Browser Status Bar */}
            <div className="h-10 border-t border-[#232B36] bg-white/[0.02] px-4 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-4 overflow-x-auto hide-scrollbar">
                <div className="flex items-center gap-1.5 shrink-0">
                  <CheckCircle2 className="h-3.5 w-3.5 text-[#10B981]" />
                  <span className="text-[10px] font-bold text-[#10B981] uppercase tracking-wider">Page loaded successfully</span>
                </div>
                <div className="h-3 w-px bg-[#232B36]" />
                <div className="flex items-center gap-3 text-[10px] font-bold text-[#9CA3AF] uppercase tracking-widest shrink-0">
                  <div className="flex items-center gap-1"><span>Load Time</span> <span className="text-[#F8FAFC]">1.42s</span></div>
                  <div className="flex items-center gap-1"><span>DOM Ready</span> <span className="text-[#F8FAFC]">1.12s</span></div>
                  <div className="flex items-center gap-1"><span>Resources</span> <span className="text-[#F8FAFC]">34</span></div>
                  <div className="flex items-center gap-1"><span>Size</span> <span className="text-[#F8FAFC]">1.2 MB</span></div>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0 ml-4">
                <div className="flex items-center gap-1.5">
                  <Activity className="h-3 w-3 text-[#22D3EE]" />
                  <span className="text-[10px] font-black text-[#22D3EE]">60 FPS</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Wifi className="h-3 w-3 text-[#10B981]" />
                  <span className="text-[10px] font-black text-[#10B981]">STABLE</span>
                </div>
              </div>
            </div>
          </div>

          {/* Resize Handle */}
          {viewMode === 'split' && (
            <div 
              onMouseDown={handleMouseDown}
              className="h-1.5 w-full bg-[#232B36] hover:bg-[#22D3EE] cursor-row-resize transition-colors z-20 relative group shrink-0"
            >
              <div className="absolute inset-x-0 -top-2 -bottom-2 cursor-row-resize" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-1 w-12 rounded-full bg-[#374151] group-hover:bg-[#22D3EE] transition-colors" />
            </div>
          )}

          {/* Bottom Panel: Tool Execution Log */}
          <div 
            style={{ height: viewMode === 'logs' ? '100%' : viewMode === 'browser' ? '0%' : `${100 - browserHeight}%` }}
            className={cn(
              "flex flex-col w-full bg-[#0A0C10] border-t border-[#232B36] transition-all duration-300",
              viewMode === 'browser' && "hidden"
            )}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#232B36] bg-white/[0.02] shrink-0">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-[#22D3EE]" />
                <span className="text-[11px] font-black uppercase tracking-[0.2em]">Tool Execution Log</span>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={onClearLogs}
                  className="h-7 px-2 rounded-lg hover:bg-white/5 text-[#9CA3AF] text-[10px] font-bold uppercase tracking-wider"
                >
                  Clear
                </Button>
              </div>
            </div>

            {/* Log Filters & Search */}
            <div className="px-3 py-2 border-b border-[#232B36] flex items-center gap-2 shrink-0">
              <div className="flex-1 relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748B]" />
                <input 
                  type="text" 
                  placeholder="Search logs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-black/40 border border-[#232B36] text-[11px] outline-none focus:border-[#22D3EE]/40 transition-all"
                />
              </div>
              <div className="flex items-center gap-1 p-1 rounded-lg bg-black/40 border border-[#232B36]">
                {['all', 'success', 'error'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setLogFilter(f as any)}
                    className={cn(
                      "px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-wider transition-all",
                      logFilter === f ? "bg-[#22D3EE] text-black" : "text-[#64748B] hover:text-[#F8FAFC]"
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Logs List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 font-mono hide-scrollbar">
              {filteredLogs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center gap-3 text-[#64748B]">
                  <div className="h-10 w-10 rounded-full border border-dashed border-[#232B36] flex items-center justify-center">
                    <Code className="h-5 w-5 opacity-20" />
                  </div>
                  <span className="text-[11px] font-bold uppercase tracking-widest opacity-40">No activity recorded</span>
                </div>
              ) : (
                filteredLogs.map((log, idx) => {
                  const isSelected = selectedTools.includes(log.id || String(idx));
                  const status = log.status;
                  
                  return (
                    <motion.div 
                      key={log.id || idx}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      onClick={() => onToggleToolSelection?.(log.id || String(idx))}
                      className={cn(
                        "group relative flex flex-col gap-2 p-3 rounded-xl border transition-all cursor-pointer",
                        status === 'IN_PROGRESS' ? "border-[#22D3EE]/30 bg-[#22D3EE]/5" : 
                        status === 'SUCCESS' ? "border-[#10B981]/20 bg-[#10B981]/5 hover:border-[#10B981]/40" : 
                        "border-[#EF4444]/20 bg-[#EF4444]/5 hover:border-[#EF4444]/40",
                        isSelectionMode && isSelected && "ring-2 ring-[#22D3EE] border-[#22D3EE]"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-black text-[#64748B]">{idx + 1}</span>
                          <span className={cn(
                            "text-[12px] font-bold",
                            status === 'IN_PROGRESS' ? "text-[#22D3EE]" : 
                            status === 'SUCCESS' ? "text-[#10B981]" : "text-[#EF4444]"
                          )}>
                            {log.tool_name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider",
                            status === 'IN_PROGRESS' ? "bg-[#22D3EE]/20 text-[#22D3EE]" : 
                            status === 'SUCCESS' ? "bg-[#10B981]/20 text-[#10B981]" : "bg-[#EF4444]/20 text-[#EF4444]"
                          )}>
                            {status}
                          </span>
                          <span className="text-[9px] text-[#64748B] font-bold">10:08:24</span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex flex-col gap-1">
                          <span className="text-[9px] font-black text-[#64748B] uppercase tracking-widest">Input</span>
                          <div className="text-[11px] text-[#CBD5E1] bg-black/40 p-2 rounded-lg border border-white/[0.03] break-all">
                            {typeof log.tool_input === 'string' ? log.tool_input : JSON.stringify(log.tool_input)}
                          </div>
                        </div>
                        {log.tool_output && (
                          <div className="flex flex-col gap-1">
                            <span className="text-[9px] font-black text-[#64748B] uppercase tracking-widest">Output</span>
                            <div className="text-[11px] text-[#9CA3AF] bg-black/20 p-2 rounded-lg border border-white/[0.02] break-words">
                              {log.tool_output}
                            </div>
                          </div>
                        )}
                      </div>

                      {isSelectionMode && (
                        <div className={cn(
                          "absolute top-2 right-2 h-5 w-5 rounded-full border flex items-center justify-center transition-all",
                          isSelected ? "bg-[#22D3EE] border-[#22D3EE]" : "bg-black/40 border-[#374151]"
                        )}>
                          {isSelected && <Check className="h-3 w-3 text-black" />}
                        </div>
                      )}
                    </motion.div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>

            {/* Log Footer */}
            <div className="px-4 py-2 border-t border-[#232B36] bg-white/[0.02] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <div className={cn("h-2 w-2 rounded-full", isAiTyping ? "bg-[#22D3EE] animate-pulse" : "bg-[#64748B]")} />
                <span className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-widest">{isAiTyping ? 'Agent Executing...' : 'Idle'}</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-widest">Auto-scroll</span>
                  <button 
                    onClick={() => setAutoScroll(!autoScroll)}
                    className={cn(
                      "w-8 h-4 rounded-full relative transition-all duration-300",
                      autoScroll ? "bg-[#10B981]" : "bg-[#374151]"
                    )}
                  >
                    <div className={cn(
                      "absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all duration-300",
                      autoScroll ? "left-4.5" : "left-0.5"
                    )} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
