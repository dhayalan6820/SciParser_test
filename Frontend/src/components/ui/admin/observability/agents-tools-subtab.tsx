import * as React from "react";
import { Panel } from "../shared";
import { Bot, Cpu, Layers } from "lucide-react";

interface AgentsToolsSubtabProps {
  data: any;
}

export const AgentsToolsSubtab: React.FC<AgentsToolsSubtabProps> = ({ data }) => {
  return (
    <div className="space-y-6">
      {/* Agents Performance */}
      <Panel title="Agent Stage Performance" subtitle="Aggregations of Planner, Research, and Browser ReAct execution times">
        {data.agents.length === 0 ? (
          <div className="text-center py-6 text-sm text-muted-foreground">No agent run data recorded.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase">
                  <th className="py-3 px-4">Agent Role</th>
                  <th className="py-3 px-4">Total Runs</th>
                  <th className="py-3 px-4">Completed</th>
                  <th className="py-3 px-4">Failed</th>
                  <th className="py-3 px-4">Avg Duration</th>
                  <th className="py-3 px-4">Avg Tokens</th>
                  <th className="py-3 px-4">Avg Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
                {data.agents.map((a: any) => (
                  <tr key={a.agent} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-800 dark:text-slate-200 capitalize">
                      <span className="flex items-center gap-2">
                        <Bot className="h-4 w-4 text-emerald-500 shrink-0" />
                        {a.agent}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{a.runs}</td>
                    <td className="py-3.5 px-4 font-mono text-emerald-500 font-medium">{a.completed}</td>
                    <td className="py-3.5 px-4 font-mono text-red-500 font-medium">{a.failed}</td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{a.avg_duration.toFixed(2)}s</td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{a.avg_tokens.toLocaleString()}</td>
                    <td className="py-3.5 px-4 font-mono text-emerald-500 font-semibold">${a.avg_cost.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Tools Performance */}
      <Panel title="Tool Invocation Performance" subtitle="Execution metrics for browser actions, database access, and other utility tools">
        {data.tools.length === 0 ? (
          <div className="text-center py-6 text-sm text-muted-foreground">No tool calls recorded in this period.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase">
                  <th className="py-3 px-4">Tool Name</th>
                  <th className="py-3 px-4">Total Calls</th>
                  <th className="py-3 px-4">Success</th>
                  <th className="py-3 px-4">Failed</th>
                  <th className="py-3 px-4">Avg Duration</th>
                  <th className="py-3 px-4">Avg Tokens</th>
                  <th className="py-3 px-4">Avg Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
                {data.tools.map((t: any) => (
                  <tr key={t.tool} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-800 dark:text-slate-200">
                      <span className="flex items-center gap-2">
                        <Cpu className="h-4 w-4 text-amber-500 shrink-0" />
                        {t.tool}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{t.calls}</td>
                    <td className="py-3.5 px-4 font-mono text-emerald-500 font-medium">{t.completed}</td>
                    <td className="py-3.5 px-4 font-mono text-red-500 font-medium">{t.failed}</td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{t.avg_duration}s</td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{t.avg_tokens.toLocaleString()}</td>
                    <td className="py-3.5 px-4 font-mono text-emerald-500 font-semibold">${t.avg_cost.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* MCP Servers */}
      <Panel title="MCP Server Observability" subtitle="Connection status, reconnect events, and request latencies for MCP nodes">
        {data.mcp_servers.length === 0 ? (
          <div className="text-center py-6 text-sm text-muted-foreground">No active MCP Server logs found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase">
                  <th className="py-3 px-4">MCP Server Node</th>
                  <th className="py-3 px-4">Total Calls</th>
                  <th className="py-3 px-4">Success</th>
                  <th className="py-3 px-4">Failures</th>
                  <th className="py-3 px-4">Avg Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
                {data.mcp_servers.map((m: any) => (
                  <tr key={m.mcp_server} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/35 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-800 dark:text-slate-200 capitalize">
                      <span className="flex items-center gap-2">
                        <Layers className="h-4 w-4 text-blue-500 shrink-0" />
                        {m.mcp_server}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{m.calls}</td>
                    <td className="py-3.5 px-4 font-mono text-emerald-500 font-medium">{m.success}</td>
                    <td className="py-3.5 px-4 font-mono text-red-500 font-medium">{m.failures}</td>
                    <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-slate-400">{m.avg_latency}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
