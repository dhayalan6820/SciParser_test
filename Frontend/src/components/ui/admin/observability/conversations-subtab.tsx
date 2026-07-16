import * as React from "react";
import { sciparserApi } from "../../../../api";
import { Panel, LoadingState } from "../shared";
import { WaterfallTimeline } from "./waterfall-timeline";
import { Search, ChevronDown, ChevronUp, Clock, Coins, Layers, Eye } from "lucide-react";

interface ConversationsSubtabProps {
  days: number;
}

export const ConversationsSubtab: React.FC<ConversationsSubtabProps> = ({ days }) => {
  const [conversations, setConversations] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [limit] = React.useState(10);
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const fetchConversations = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await sciparserApi.observabilityGetConversations(days, page, limit, search, status);
      setConversations(res.conversations || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, [days, page, limit, search, status]);

  React.useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap justify-between items-center gap-4 bg-white dark:bg-slate-900 p-3 rounded-lg border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search conversations by title..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 border border-slate-200 dark:border-slate-800 bg-transparent rounded-lg text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="border border-slate-200 dark:border-slate-800 bg-transparent rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="completed">Completed</option>
          </select>
        </div>

        <div className="text-xs text-muted-foreground">
          Showing <span className="font-semibold text-foreground">{conversations.length}</span> of {total} conversations
        </div>
      </div>

      {/* Main List */}
      <Panel title="Session Auditing & Waterfall Trace" subtitle="Inspect conversation run history and ReAct execution waterfall diagrams">
        {loading && conversations.length === 0 ? (
          <LoadingState />
        ) : error ? (
          <div className="text-red-500 text-sm py-4">{error}</div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">No conversations found matching filters.</div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {conversations.map((c) => {
              const isExpanded = expandedId === c.conversation_id;

              return (
                <div key={c.conversation_id} className="group">
                  {/* Summary Row */}
                  <div
                    onClick={() => toggleExpand(c.conversation_id)}
                    className="flex justify-between items-center py-4 px-3 hover:bg-slate-50/50 dark:hover:bg-slate-900/35 cursor-pointer transition-colors"
                  >
                    <div className="flex-1 min-w-0 pr-6">
                      <div className="flex items-center gap-2.5">
                        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                          c.status === "active" ? "bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400" : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                        }`}>
                          {c.status}
                        </span>
                        <h4 className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                          {c.title || "Untitled Conversation"}
                        </h4>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-500">
                        <span>User: <strong className="text-slate-700 dark:text-slate-300 font-medium">{c.username}</strong></span>
                        <span>•</span>
                        <span>{new Date(c.started).toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Stats columns */}
                    <div className="flex gap-6 text-xs font-mono shrink-0 select-none">
                      <div className="flex items-center gap-1.5 text-slate-500" title="Messages count">
                        <Eye className="h-3.5 w-3.5" />
                        <span>{c.messages_count} msgs</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-500" title="Tokens consumed">
                        <Layers className="h-3.5 w-3.5" />
                        <span>{c.total_tokens.toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-emerald-500 font-medium" title="Run cost">
                        <Coins className="h-3.5 w-3.5" />
                        <span>${c.cost.toFixed(4)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Waterfall Section */}
                  {isExpanded && (
                    <div className="bg-slate-50/50 dark:bg-slate-900/10 p-4 border-t border-b border-slate-100 dark:border-slate-850">
                      <WaterfallTimeline chatId={c.conversation_id} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination Ruler */}
        {totalPages > 1 && (
          <div className="flex justify-between items-center border-t border-slate-100 dark:border-slate-800 pt-4 mt-4 text-xs">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800/40 disabled:opacity-50 transition-colors"
            >
              Previous
            </button>
            <span className="text-muted-foreground">
              Page <span className="font-semibold text-foreground">{page}</span> of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800/40 disabled:opacity-50 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </Panel>
    </div>
  );
};
