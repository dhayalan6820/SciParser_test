// components/ui/message-loading.tsx
import * as React from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

function MessageLoading() {
  const [loadingText, setLoadingText] = React.useState("SciParser is thinking");
  
  React.useEffect(() => {
    const texts = [
      "SciParser is thinking",
      "Analyzing your request",
      "Understanding context",
      "Preparing agent workflow",
      "Initializing multi-agent system"
    ];
    let i = 0;
    const interval = setInterval(() => {
      i = (i + 1) % texts.length;
      setLoadingText(texts[i]);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-start gap-4 w-full max-w-2xl animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 flex items-center justify-center shrink-0 border border-indigo-100/50 dark:border-indigo-500/10">
        <motion.div
          animate={{ 
            scale: [1, 1.2, 1],
            rotate: [0, 10, -10, 0],
            opacity: [0.7, 1, 0.7]
          }}
          transition={{ 
            duration: 3, 
            repeat: Infinity,
            ease: "easeInOut" 
          }}
        >
          <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
        </motion.div>
      </div>
      
      <div className="flex-1 space-y-3 pt-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-widest">
            {loadingText}
          </span>
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-1 h-1 rounded-full bg-indigo-400 dark:bg-indigo-500"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        </div>
        
        <div className="space-y-2">
          <div className="relative h-2 bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden w-full">
            <motion.div 
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-transparent via-indigo-500/20 to-transparent w-1/2"
              animate={{ left: ["-50%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
          </div>
          <div className="relative h-2 bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden w-[90%]">
            <motion.div 
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-transparent via-indigo-500/20 to-transparent w-1/2"
              animate={{ left: ["-50%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear", delay: 0.3 }}
            />
          </div>
          <div className="relative h-2 bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden w-[40%]">
            <motion.div 
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-transparent via-indigo-500/20 to-transparent w-1/2"
              animate={{ left: ["-50%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear", delay: 0.6 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export { MessageLoading };