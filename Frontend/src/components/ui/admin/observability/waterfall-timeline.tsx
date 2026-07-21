import * as React from "react";
import { sciparserApi } from "../../../../api";
import { LoadingState } from "../shared";
import { Clock, Coins, Layers, CheckCircle2, XCircle } from "lucide-react";

interface WaterfallTimelineProps {
  chatId: string;
}

export const WaterfallTimeline: React.FC<WaterfallTimelineProps> = ({ chatId }) => {
  const [data, setData] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [hoveredIndex, setHoveredIndex] = React.useState<number | null>(null);

  React.useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await sciparserApi.observabilityGetWaterfall(chatId);
        setData(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load waterfall data");
      } finally {
        setLoading(false);
      }
    })();
  }, [chatId]);

  if (loading) return <LoadingState />;
  if (error) return <div className="text-sm text-red-500 py-4">{error}</div>;
  if (!data || !data.stages || data.stages.length === 0) {
    return <div className="text-sm text-muted-foreground py-4">No execution timeline details found for this conversation.</div>;
  }

  // Find min and max times to align bars on the timeline
  const firstTime = new Date(data.stages[0].started_at).getTime();
  const lastStage = data.stages[data.stages.length - 1];
  const lastTime = new Date(lastStage.started_at).getTime() + (lastStage.duration_ms || 100);
  const totalSpan = Math.max(lastTime - firstTime, 1);

  return (
    <div className="border border-slate-200 dark:border-slate-800 rounded-lg p-4 bg-white dark:bg-slate-900/60 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div>
          <h4 className="text-sm font-semibold truncate max-w-md">{data.title}</h4>
          <p className="text-[11px] text-muted-foreground">ID: {chatId}</p>
        </div>
        <div className="flex gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-500">
            <Clock className="h-3.5 w-3.5" />
            <span>{(data.total_duration_ms / 1000).toFixed(2)}s</span>
          </div>
          <div className="flex items-center gap-1.5 text-emerald-500 font-medium">
            <Coins className="h-3.5 w-3.5" />
            <span>${data.total_cost.toFixed(4)}</span>
          </div>
          <div className="flex items-center gap-1.5 text-blue-500">
            <Layers className="h-3.5 w-3.5" />
            <span>{data.total_tokens.toLocaleString()} tokens</span>
          </div>
        </div>
      </div>

      <div className="space-y-2.5 overflow-x-auto">
        {/* Timeline ruler */}
        <div className="relative h-5 border-b border-slate-100 dark:border-slate-800 text-[10px] text-muted-foreground select-none">
          <span className="absolute left-0">0s</span>
          <span className="absolute left-1/4">{(data.total_duration_ms * 0.25 / 1000).toFixed(1)}s</span>
          <span className="absolute left-1/2">{(data.total_duration_ms * 0.5 / 1000).toFixed(1)}s</span>
          <span className="absolute left-3/4">{(data.total_duration_ms * 0.75 / 1000).toFixed(1)}s</span>
          <span className="absolute right-0">{(data.total_duration_ms / 1000).toFixed(1)}s</span>
        </div>

        {/* Waterfall Rows */}
        <div className="space-y-1.5 pt-1">
          {data.stages.map((stage: any, idx: number) => {
            const stageTime = new Date(stage.started_at).getTime();
            const startOffset = Math.max(0, ((stageTime - firstTime) / totalSpan) * 100);
            const widthPercent = Math.max(2, ((stage.duration_ms || 100) / totalSpan) * 100);

            // Coloring based on stage type
            let barColor = "bg-blue-500 dark:bg-blue-600";
            let typeLabel = "Agent";
            if (stage.stage_type === "tool") {
              barColor = "bg-amber-500 dark:bg-amber-600";
              typeLabel = "Tool";
            } else if (stage.stage_type === "llm") {
              barColor = "bg-purple-500 dark:bg-purple-600";
              typeLabel = "LLM";
            }

            const isSuccess = (stage.status || "").toUpperCase() === "COMPLETED" || (stage.status || "").toUpperCase() === "SUCCESS";

            return (
              <div
                key={stage.id || idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className="group relative flex items-center hover:bg-slate-50 dark:hover:bg-slate-800/40 p-1.5 rounded transition-colors"
              >
                {/* Left labels column */}
                <div className="w-1/3 shrink-0 flex items-center justify-between pr-4 select-none">
                  <div className="truncate pr-2 flex-1">
                    <div className="flex items-center">
                      <span className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded mr-1.5 bg-slate-100 dark:bg-slate-800 text-slate-500`}>
                        {typeLabel}
                      </span>
                      <span className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate" title={stage.name}>
                        {stage.name}
                      </span>
                    </div>
                    {(stage.tokens > 0 || stage.cost > 0) && (
                      <div className="flex items-center gap-1.5 mt-0.5 pl-[38px] text-[10px] text-muted-foreground font-mono">
                        {stage.tokens > 0 && (
                          <span className="text-blue-600 dark:text-blue-400" title={`Prompt: ${stage.prompt_tokens || 0}, Completion: ${stage.completion_tokens || 0}`}>
                            {stage.tokens.toLocaleString()} toks ({stage.prompt_tokens || 0} p / {stage.completion_tokens || 0} c)
                          </span>
                        )}
                        {stage.tokens > 0 && stage.cost > 0 && <span className="opacity-40">•</span>}
                        {stage.cost > 0 && (
                          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                            ${stage.cost.toFixed(4)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {isSuccess ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    ) : (
                      <div className="flex items-center gap-1.5">
                        {stage.error_message && (
                            <span className="text-[10px] text-red-500/80 max-w-[150px] truncate" title={stage.error_message}>
                                {stage.error_message}
                            </span>
                        )}
                        <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Right bar chart column */}
                <div className="w-2/3 relative h-6 bg-slate-50 dark:bg-slate-900/40 rounded border border-slate-100 dark:border-slate-800 overflow-hidden flex items-center">
                  <div
                    style={{ left: `${startOffset}%`, width: `${widthPercent}%` }}
                    className={`absolute h-4 rounded-sm opacity-85 group-hover:opacity-100 transition-all ${barColor}`}
                  />
                  <span
                    style={{ left: `${Math.min(90, startOffset + widthPercent + 1.5)}%` }}
                    className="absolute text-[10px] font-medium text-slate-500 whitespace-nowrap z-10 select-none"
                  >
                    {stage.duration_ms >= 1000 ? `${(stage.duration_ms / 1000).toFixed(2)}s` : `${stage.duration_ms}ms`}
                  </span>
                </div>

                {/* Hover details tooltip */}
                <div className={`${hoveredIndex === idx ? "block" : "hidden"} absolute left-1/3 top-7 bg-slate-900 text-white text-[11px] p-2.5 rounded-lg shadow-xl border border-slate-800 z-50 w-72 space-y-1 pointer-events-none`}>
                  <div className="font-semibold pb-1 border-b border-slate-800 text-slate-300">{stage.name}</div>
                  <div><span className="text-slate-400">Duration:</span> {stage.duration_ms}ms</div>
                  {stage.tokens > 0 && <div><span className="text-slate-400">Tokens:</span> {stage.tokens.toLocaleString()}</div>}
                  {stage.cost > 0 && <div><span className="text-slate-400">Cost:</span> ${stage.cost.toFixed(6)}</div>}
                  <div><span className="text-slate-400">Status:</span> {stage.status}</div>
                  {stage.error_message && (
                    <div className="text-red-400 font-medium pt-1 border-t border-slate-800 mt-1 max-h-16 overflow-y-auto">
                      {stage.error_message}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
