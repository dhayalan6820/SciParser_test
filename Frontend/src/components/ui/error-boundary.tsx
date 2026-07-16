import * as React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./button";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  errorId: string;
}

export class ErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false,
    errorId: "",
  };

  public static getDerivedStateFromError(_: Error): State {
    const today = new Date();
    const dateStr = today.getFullYear() + 
      String(today.getMonth() + 1).padStart(2, "0") + 
      String(today.getDate()).padStart(2, "0");
    const randStr = Math.random().toString(36).substring(2, 8).toUpperCase();
    const errorId = `ERR-${dateStr}-${randStr}`;
    
    return { hasError: true, errorId };
  }

  public componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled rendering exception:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, errorId: "" });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[400px] w-full flex items-center justify-center p-6 bg-slate-50 dark:bg-slate-950 text-foreground">
          <div className="max-w-md w-full border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-lg text-center space-y-4">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-red-50 dark:bg-red-950/20 text-red-500 border border-red-500/20">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold">We couldn't load this section</h3>
              <p className="text-xs text-muted-foreground">
                We're experiencing a temporary client-side error. Please try refreshing this section or reloading the page.
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-950/50 py-2 px-4 rounded-lg font-mono text-[10px] text-slate-500 border border-slate-100 dark:border-slate-850">
              Support Reference ID: <strong className="text-slate-800 dark:text-slate-200">{this.state.errorId}</strong>
            </div>
            <Button onClick={this.handleReset} variant="outline" size="sm" className="gap-1.5 w-full">
              <RefreshCw className="h-4 w-4" />
              Reload Application
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
