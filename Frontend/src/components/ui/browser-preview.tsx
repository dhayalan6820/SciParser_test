import React from 'react';

interface BrowserPreviewProps {
  frame: string | null;
  isActive: boolean;
  onClose: () => void;
}

export function BrowserPreview({ frame, isActive, onClose }: BrowserPreviewProps) {
  if (!isActive) return null;

  return (
    <div className="flex flex-col h-full w-full bg-slate-950 text-slate-100">
      {/* Browser Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5 mr-2">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Live CDP Screencast</span>
        </div>
        <button 
          onClick={onClose} 
          className="text-slate-400 hover:text-white transition-colors p-1"
        >
          ✕
        </button>
      </div>

      {/* Live Viewport */}
      <div className="flex-1 bg-[#0a0a0a] flex items-center justify-center overflow-hidden p-4 relative">
        {frame ? (
          <img 
            src={frame.startsWith('data:') ? frame : `data:image/jpeg;base64,${frame}`} 
            alt="Live Browser" 
            className="max-w-full max-h-full object-contain shadow-2xl border border-white/5 rounded-sm"
          />
        ) : (
          <div className="flex flex-col items-center gap-4 text-slate-600">
            <div className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            <span className="text-xs font-semibold tracking-tight">Initializing Browser Stream...</span>
          </div>
        )}
      </div>
    </div>
  );
}