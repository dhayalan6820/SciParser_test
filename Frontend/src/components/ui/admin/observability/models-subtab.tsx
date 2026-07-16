import * as React from "react";
import { Panel, KPICard } from "../shared";
import { Brain, Layers, Coins, Gauge } from "lucide-react";

interface ModelsSubtabProps {
  data: any;
}

export const ModelsSubtab: React.FC<ModelsSubtabProps> = ({ data }) => {
  // Find most expensive model and provider
  const sortedModels = React.useMemo(() => {
    return [...(data.models || [])].sort((a: any, b: any) => b.cost - a.cost);
  }, [data]);

  const mostExpensiveModel = sortedModels[0]?.model || "None";
  const mostExpensiveProvider = [...(data.providers || [])].sort((a: any, b: any) => b.cost - a.cost)[0]?.provider || "None";

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard index={0} icon={<Brain className="h-4 w-4" />} label="Active Providers" value={data.providers.length} />
        <KPICard index={1} icon={<Brain className="h-4 w-4 text-purple-500" />} label="Active Models" value={data.models.length} />
        <KPICard index={2} icon={<Coins className="h-4 w-4" />} label="Top Provider" value={mostExpensiveProvider} />
        <KPICard index={3} icon={<Coins className="h-4 w-4 text-emerald-500" />} label="Top Model (Cost)" value={mostExpensiveModel} />
      </div>

      {/* Provider Breakdown */}
      <Panel title="LLM Provider Overview" subtitle="Total requests, token volumes, latency, and costs grouped by provider">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.providers.map((p: any) => (
            <div key={p.provider} className="border border-slate-200 dark:border-slate-800 p-4 rounded-lg bg-white dark:bg-slate-900 shadow-sm space-y-2">
              <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
                <span className="text-sm font-semibold capitalize text-emerald-600 dark:text-emerald-400">{p.provider}</span>
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 bg-slate-100 dark:bg-slate-850 rounded">
                  {p.requests} calls
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1">
                <div>
                  <p className="text-muted-foreground">Tokens</p>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{p.tokens.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Avg Latency</p>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{p.avg_latency}ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Total Cost</p>
                  <p className="font-semibold text-emerald-500">${p.cost.toFixed(4)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Models Detailed Breakdown Table */}
      <Panel title="LLM Model Performance" subtitle="Drill-down metrics for every LLM model used by this platform">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase">
                <th className="py-3 px-4">Model Name</th>
                <th className="py-3 px-4">Provider</th>
                <th className="py-3 px-4">Total Runs</th>
                <th className="py-3 px-4">Prompt Tokens</th>
                <th className="py-3 px-4">Completion Tokens</th>
                <th className="py-3 px-4">Total Cost</th>
                <th className="py-3 px-4">Avg Latency</th>
                <th className="py-3 px-4">P95 Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
              {data.models.map((m: any) => (
                <tr key={m.model} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                  <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200">{m.model}</td>
                  <td className="py-3 px-4 capitalize text-slate-600 dark:text-slate-400">{m.provider}</td>
                  <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">{m.requests.toLocaleString()}</td>
                  <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">{m.prompt_tokens.toLocaleString()}</td>
                  <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">{m.completion_tokens.toLocaleString()}</td>
                  <td className="py-3 px-4 font-mono text-emerald-500 font-semibold">${m.cost.toFixed(6)}</td>
                  <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">{m.avg_latency}ms</td>
                  <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">{m.p95_latency}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
};
