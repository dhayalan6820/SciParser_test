import * as React from "react";
import ChatPage from './components/ui/chat_page';
import { AdminDashboard } from './components/ui/admin-dashboard';
import { NotFound } from "./components/ui/ghost-404-page";
import { Signup1 } from "./components/ui/signup-1";
import { motion } from "framer-motion";
import { sciparserApi, User, consumeSuspensionMessage } from "./api";
import { apiUrl } from "./config";
import { useTheme } from "./contexts/ThemeContext";
import { LayoutDashboard } from "lucide-react";

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
  const [currentUser, setCurrentUser] = React.useState<User | null>(null);
  const [isCheckingRole, setIsCheckingRole] = React.useState(false);
  // Lets an admin temporarily leave the Admin Dashboard and use the same
  // Chat/Schedule experience regular users get, then jump back.
  const [viewAsUser, setViewAsUser] = React.useState(false);
  // Separate from `hasError` (which drives the full-page NotFound view for
  // app/server-level failures) so a failed sign-in attempt just shows an
  // inline message on the login form instead of navigating away from it.
  const [authError, setAuthError] = React.useState<string>("");

  // Check server health
  React.useEffect(() => {
    const checkServerHealth = async () => {
      try {
        const response = await fetch(apiUrl("/sciparser/v1/health"), { 
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

    // Task #130: a suspended user's open websocket forces a logout+reload; surface
    // the reason on the login screen instead of leaving them with no explanation.
    const suspensionMessage = consumeSuspensionMessage();
    if (suspensionMessage) {
      setAuthError(suspensionMessage);
    }
    
    // Listen for storage changes (in case token is added in another tab)
    window.addEventListener("storage", checkAuth);
    
    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  // Once logged in, fetch the user's profile to determine role-based routing
  // (Admin Dashboard vs the regular chat experience). Regular users still
  // land on the exact same ChatPage they always have.
  React.useEffect(() => {
    if (!isLoggedIn) {
      setCurrentUser(null);
      return;
    }
    let cancelled = false;
    setIsCheckingRole(true);
    sciparserApi
      .getMe()
      .then((user) => {
        if (!cancelled) setCurrentUser(user);
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem("access_token");
          setIsLoggedIn(false);
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsCheckingRole(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

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
    <motion.div initial="hidden" animate="visible" variants={containerVariants} className="h-screen w-screen overflow-hidden">
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
        ) : isLoggedIn && isCheckingRole ? (
          <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          </div>
        ) : isLoggedIn && currentUser?.role === "admin" && !viewAsUser ? (
          <AdminDashboard
            currentUser={currentUser}
            onLogout={() => {
              sciparserApi.logout();
              setIsLoggedIn(false);
              setCurrentUser(null);
              setViewAsUser(false);
            }}
            onOpenUserView={() => setViewAsUser(true)}
          />
        ) : isLoggedIn ? (
          <div className="relative w-screen h-screen flex flex-col font-sans selection:bg-indigo-500 selection:text-white overflow-hidden bg-background text-foreground transition-colors duration-300">
            {currentUser?.role === "admin" && (
              <button
                onClick={() => setViewAsUser(false)}
                title="Back to Admin"
                className="fixed top-3 right-3 z-[60] flex h-10 w-10 items-center justify-center rounded-[12px] border border-border bg-card/90 backdrop-blur text-muted-foreground shadow-md transition-all hover:bg-muted hover:text-foreground active:scale-90"
              >
                <LayoutDashboard className="h-5 w-5" />
              </button>
            )}
            <ChatPage
              onLoginStateChange={(status) => {
                setIsLoggedIn(!!status);
                if (!status) setViewAsUser(false);
              }}
            />
          </div>
        ) : (
          <div className="h-full overflow-y-auto bg-background text-foreground flex flex-col items-center justify-center p-4 sm:p-6 font-sans selection:bg-indigo-500 selection:text-white transition-colors duration-300">
            <Signup1 
              isLoginMode={isLoginMode}
              onToggleMode={() => setIsLoginMode(!isLoginMode)}
              onSubmit={async (formData) => {
                try {
                  setIsLoading(true);
                  setAuthError("");
                  
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
                  setAuthError(errorMessage);
                } finally {
                  setIsLoading(false);
                }
              }}
              loading={isLoading}
              error={authError}
              success=""
            />
          </div>
        )}
      </motion.div>
  );
}

