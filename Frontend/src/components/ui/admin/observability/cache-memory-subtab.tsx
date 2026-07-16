import * as React from "react";
import { Panel, KPICard } from "../shared";
import { Database, Zap, RefreshCw, Layers } from "lucide-react";

interface CacheMemorySubtabProps {
  data: any;
}

export const CacheMemorySubtab: React.FC<CacheMemorySubtabProps> = ({ data }) => {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Zap className="h-4 w-4" />} label="Prompt Cache Hit Rate" value={`${data.prompt_cache_hit_rate}%`} />
        <KPICard index={1} icon={<Zap className="h-4 w-4 text-purple-500" />} label="Cache Hit Saves" value={`$${data.saved_cost_usd.toFixed(4)}`} />
        <KPICard index={2} icon={<Database className="h-4 w-4" />} label="Memory Reads (Hits)" value={data.memory_reads.toLocaleString()} />
        <KPICard index={3} icon={<RefreshCw className="h-4 w-4 text-emerald-500" />} label="Memory Sync Writes" value={data.memory_writes.toLocaleString()} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Cache Savings details */}
        <Panel title="Cache Utilization Details" subtitle="Prompt caching hits/misses and token conservation">
          <div className="space-y-4 pt-1 text-xs">
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Prompt Cache Hits</span>
              <span className="font-mono font-semibold text-emerald-500">{data.cache_hits.toLocaleString()} calls</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Prompt Cache Misses</span>
              <span className="font-mono font-semibold text-slate-650">{data.cache_misses.toLocaleString()} calls</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Tokens Reused/Saved</span>
              <span className="font-mono font-semibold text-blue-500">{data.saved_tokens.toLocaleString()} tokens</span>
            </div>
            <div className="flex justify-between items-center pb-1">
              <span className="font-medium text-slate-650">Estimated Financial Savings</span>
              <span className="font-mono font-bold text-emerald-500">${data.saved_cost_usd.toFixed(6)} USD</span>
            </div>
          </div>
        </Panel>

        {/* Memory Search precision & hit rate */}
        <Panel title="Semantic Long-Term Memory Stats" subtitle="Access frequencies for episodic and semantic memory blocks">
          <div className="space-y-4 pt-1 text-xs">
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Embedding Model Requests</span>
              <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">{data.embedding_calls.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Vector Database Searches</span>
              <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">{data.vector_searches.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="font-medium text-slate-650">Episodic Retrieval Hits</span>
              <span className="font-mono font-semibold text-blue-500">{(data.memory_reads - data.semantic_hits).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center pb-1">
              <span className="font-medium text-slate-650">Semantic Base Hits</span>
              <span className="font-mono font-semibold text-purple-500">{data.semantic_hits.toLocaleString()}</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
};
