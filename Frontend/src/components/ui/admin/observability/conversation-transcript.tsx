import * as React from "react";
import { sciparserApi } from "../../../../api";
import { LoadingState } from "../shared";
import { Bot, User as UserIcon, MessageSquare } from "lucide-react";

interface ConversationTranscriptProps {
  chatId: string;
}

export const ConversationTranscript: React.FC<ConversationTranscriptProps> = ({ chatId }) => {
  const [messages, setMessages] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let mounted = true;
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const res = await sciparserApi.getChatHistory(chatId);
        if (mounted) {
          setMessages(res.messages || []);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load chat history");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    
    if (chatId) {
      fetchHistory();
    }
    
    return () => { mounted = false; };
  }, [chatId]);

  if (loading) {
    return (
      <div className="py-4 bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 mt-4">
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4 bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 mt-4 text-center text-red-500 text-sm">
        {error}
      </div>
    );
  }

  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2 bg-slate-50 dark:bg-slate-900/50">
        <MessageSquare className="h-4 w-4 text-slate-500" />
        <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300">Conversation Transcript</h4>
        <span className="text-[10px] bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded-full text-slate-600 dark:text-slate-400 ml-2">
          {messages.length} messages
        </span>
      </div>
      
      <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role !== 'user' && (
              <div className="h-6 w-6 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0 mt-1">
                <Bot className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
            )}
            
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13px] ${
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-tr-sm' 
                : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-sm'
            }`}>
              <div className="whitespace-pre-wrap break-words">{msg.content || (msg.role === 'assistant' && msg.plan?.length ? "(Agent is processing...)" : "(Empty message)")}</div>
              
              <div className={`text-[9px] mt-1.5 flex items-center gap-2 ${
                msg.role === 'user' ? 'text-blue-200' : 'text-slate-400 dark:text-slate-500'
              }`}>
                {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ""}
                {msg.cost > 0 && <span>• ${msg.cost.toFixed(4)}</span>}
              </div>
            </div>

            {msg.role === 'user' && (
              <div className="h-6 w-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mt-1">
                <UserIcon className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
