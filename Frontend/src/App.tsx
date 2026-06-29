import * as React from "react";
import ChatPage from './components/ui/chat_page';
import { NotFound } from "./components/ui/ghost-404-page";
import { Signup1 } from "./components/ui/signup-1";
import { motion } from "framer-motion";
import { sciparserApi } from "./api";
import { useTheme } from "./contexts/ThemeContext";

const customBezier: [number, number, number, number] = [0.43, 0.13, 0.23, 0.96];

const containerVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.7,
      ease: customBezier,
      delayChildren: 0.1,
      staggerChildren: 0.1,
    },
  },
};

export default function App() {
  const { theme } = useTheme();
  const [isLoggedIn, setIsLoggedIn] = React.useState(false);
  const [hasError, setHasError] = React.useState<string>("");  // ← Changed from false to ""
  const [isLoading, setIsLoading] = React.useState(true);
  const [serverStatus, setServerStatus] = React.useState<"online" | "offline" | "checking">("checking");
  const [isLoginMode, setIsLoginMode] = React.useState(true);  // ← Add this line

  // Check server health
  React.useEffect(() => {
    const checkServerHealth = async () => {
      try {
        const response = await fetch(`/sciparser/v1/health`, { 
          method: "GET",
          signal: AbortSignal.timeout(3000)
        });
        setServerStatus(response.ok ? "online" : "offline");
      } catch (error) {
        setServerStatus("offline");
      } finally {
        setIsLoading(false);  // ← Move this to finally block
      }
    };
    
    checkServerHealth();
  }, []);

  // Check authentication status on mount
  React.useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem("access_token");
      setIsLoggedIn(!!token);
      console.log("Auth check - Token exists:", !!token, "Is logged in:", !!token);
    };
    
    // Initial check
    checkAuth();
    
    // Listen for storage changes (in case token is added in another tab)
    window.addEventListener("storage", checkAuth);
    
    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  // Sync theme with root HTML element data-theme and classList attributes
  React.useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    }
  }, [theme]);

  return (
    <motion.div initial="hidden" animate="visible" variants={containerVariants}>
        {isLoading ? (
          <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          </div>
        ) : serverStatus === "offline" ? (
          <NotFound onGoBack={() => {
            setServerStatus("checking");
            setTimeout(() => {
              window.location.reload();
            }, 1000);
          }} />
        ) : hasError ? (
          <NotFound onGoBack={() => {
            setHasError("");  // ← Clear the error message
            window.location.reload();
          }} />
        ) : isLoggedIn ? (
          <div className="w-screen h-screen flex flex-col font-sans selection:bg-indigo-500 selection:text-white overflow-hidden bg-background text-foreground transition-colors duration-300">
            <ChatPage onLoginStateChange={(status) => setIsLoggedIn(!!status)} />
          </div>
        ) : (
          <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-2 sm:p-6 font-sans selection:bg-indigo-500 selection:text-white transition-colors duration-300">
            <Signup1 
              isLoginMode={isLoginMode}
              onToggleMode={() => setIsLoginMode(!isLoginMode)}
              onSubmit={async (formData) => {
                try {
                  setIsLoading(true);
                  setHasError("");
                  
                  if (isLoginMode) {
                    const res = await sciparserApi.signin(formData.username, formData.password);
                    if (res && res.access_token) {
                      localStorage.setItem("access_token", res.access_token);
                      console.log("Token saved to localStorage");
                    } else {
                      throw new Error("No access token received");
                    }
                  } else {
                    await sciparserApi.signup(formData.username, formData.email, formData.password);
                    // After signup, switch to login mode instead of logging in directly
                    setIsLoginMode(true);
                    setIsLoading(false);
                    return;
                  }
                  
                  setIsLoggedIn(true);
                } catch (error) {
                  const errorMessage = error instanceof Error ? error.message : "Authentication failed";
                  setHasError(errorMessage);
                } finally {
                  setIsLoading(false);
                }
              }}
              loading={isLoading}
              error={hasError ? "Authentication failed" : ""}
              success=""
            />
          </div>
        )}
      </motion.div>
  );
}

