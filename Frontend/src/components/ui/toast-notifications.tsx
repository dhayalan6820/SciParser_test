import * as React from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export type ToastType = "success" | "info" | "warning" | "error" | "critical";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  errorId?: string;
  duration?: number;
}

type ToastContextType = (
  type: ToastType,
  title: string,
  message: string,
  errorId?: string,
  duration?: number
) => void;

const ToastContext = React.createContext<ToastContextType | null>(null);

export const useToast = () => {
  const context = React.useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within a ToastProvider");
  return context;
};

// Global trigger fallback if used outside React Context
let globalToastTrigger: ToastContextType | null = null;
export const toast = (
  type: ToastType,
  title: string,
  message: string,
  errorId?: string,
  duration?: number
) => {
  if (globalToastTrigger) {
    globalToastTrigger(type, title, message, errorId, duration);
  } else {
    console.warn("ToastProvider not initialized yet. Message:", message);
  }
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = React.useState<ToastMessage[]>([]);

  const addToast = React.useCallback(
    (type: ToastType, title: string, message: string, errorId?: string, duration: number = 5000) => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, type, title, message, errorId, duration }]);

      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    },
    []
  );

  React.useEffect(() => {
    globalToastTrigger = addToast;
    return () => {
      globalToastTrigger = null;
    };
  }, [addToast]);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none select-none">
        <AnimatePresence>
          {toasts.map((t) => {
            let icon = <Info className="h-5 w-5 text-blue-500" />;
            let borderColor = "border-blue-500/25";
            let bgClass = "bg-white dark:bg-slate-900";
            
            if (t.type === "success") {
              icon = <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
              borderColor = "border-emerald-500/25";
            } else if (t.type === "warning") {
              icon = <AlertTriangle className="h-5 w-5 text-amber-500 animate-bounce" />;
              borderColor = "border-amber-500/25";
            } else if (t.type === "error") {
              icon = <AlertCircle className="h-5 w-5 text-red-500 animate-pulse" />;
              borderColor = "border-red-500/25";
            } else if (t.type === "critical") {
              icon = <AlertCircle className="h-5 w-5 text-red-700 animate-ping" />;
              borderColor = "border-red-700/40";
              bgClass = "bg-red-50/10 dark:bg-red-950/10";
            }

            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 50, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.15 } }}
                className={`pointer-events-auto border rounded-xl p-4 shadow-xl flex items-start gap-3 backdrop-blur-md ${bgClass} ${borderColor}`}
              >
                <div className="shrink-0 mt-0.5">{icon}</div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-xs font-semibold leading-tight">{t.title}</h4>
                  <p className="text-[11px] text-muted-foreground mt-0.5 leading-normal">{t.message}</p>
                  {t.errorId && (
                    <div className="mt-1.5 font-mono text-[9px] text-slate-500 bg-slate-50 dark:bg-slate-950/40 py-0.5 px-2 rounded border border-slate-100 dark:border-slate-800 inline-block">
                      Reference ID: {t.errorId}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => removeToast(t.id)}
                  className="shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
};
