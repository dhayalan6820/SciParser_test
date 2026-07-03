import * as React from "react";
import { FcGoogle } from "react-icons/fc";
import logoLight from "@/assets/logo-light.png";
import logoDark from "@/assets/logo-dark.png";

import { Button } from "./button";
import { Input } from "./input";
import { useTheme } from "../../contexts/ThemeContext";

interface Signup1Props {
  heading?: string;
  logo?: {
    url: string;
    src: string;
    alt: string;
    title?: string;
  };
  signupText?: string;
  googleText?: string;
  loginText?: string;
  loginUrl?: string;
  
  // Dynamic integration props
  isLoginMode?: boolean;
  onToggleMode?: () => void;
  onSubmit?: (data: any) => Promise<void>;
  loading?: boolean;
  error?: string;
  success?: string;
}

const Signup1 = ({
  heading,
  logo,
  googleText = "Sign up with Google",
  signupText = "Create an account",
  loginText = "Already have an account?",
  loginUrl = "#",
  
  isLoginMode = false,
  onToggleMode,
  onSubmit,
  loading = false,
  error = "",
  success = "",
}: Signup1Props) => {
  const [username, setUsername] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [localError, setLocalError] = React.useState("");
  const { theme } = useTheme();
  const resolvedLogo = logo ?? {
    url: "#",
    src: theme === "dark" ? logoDark : logoLight,
    alt: "SciParser Logo",
    title: "SciParser",
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError("");
    
    if (isLoginMode) {
      if (!username || !password) {
        setLocalError("Username and Password are required");
        return;
      }
    } else {
      if (!username || !email || !password) {
        setLocalError("All fields are required");
        return;
      }
      if (!email.includes("@")) {
        setLocalError("Please enter a valid email address");
        return;
      }
    }

    if (onSubmit) {
      onSubmit({ username, email, password });
    }
  };

  return (
    <main className="bg-background flex flex-col items-center justify-center min-h-screen py-8 px-4">
      <div className="w-full max-w-[400px] space-y-6">
        
        {/* Logo and Greeting Section */}
        <div className="space-y-2 text-center mb-6">
          <div className="flex justify-center mb-3">
            <a href={resolvedLogo.url} className="inline-flex items-center">
              <img
                src={resolvedLogo.src}
                alt={resolvedLogo.alt}
                title={resolvedLogo.title}
                className="h-20 w-auto object-contain hover:scale-105 transition-transform"
              />
            </a>
          </div>
          <h1 className="text-3xl font-semibold text-foreground tracking-tight">
            {isLoginMode ? "Welcome Back" : signupText}
          </h1>
          <p className="text-muted-foreground text-sm">
            {isLoginMode 
              ? "Enter your credentials to access your parser dashboard" 
              : "Enter your details to get started with SciParser"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          
          {/* Username Input Field */}
          <div className="space-y-1.5 flex flex-col">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Username
            </label>
            <Input
              type="text"
              placeholder="Username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="flex h-10 w-full rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          {/* Email Input Field - Only shown in SignUp mode */}
          {!isLoginMode && (
            <div className="space-y-1.5 flex flex-col">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Email
              </label>
              <Input
                type="email"
                placeholder="john@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex h-10 w-full rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          )}

          {/* Password Input Field */}
          <div className="space-y-1.5 flex flex-col">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Password
            </label>
            <Input
              type="password"
              placeholder="••••••••"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="flex h-10 w-full rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          {/* Dynamic Status Alert lines */}
          {(error || localError) && (
            <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/40 rounded-lg text-red-600 dark:text-red-400 text-xs font-medium">
              {error || localError}
            </div>
          )}
          {success && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/40 rounded-lg text-emerald-600 dark:text-emerald-400 text-xs font-medium">
              {success}
            </div>
          )}

          {/* Action Button */}
          <Button 
            type="submit" 
            className="w-full h-10 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-md text-sm shadow-sm transition-colors mt-2 cursor-pointer"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center gap-2 justify-center">
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Processing...
              </span>
            ) : (
              isLoginMode ? "Sign In" : "Create account"
            )}
          </Button>

          {/* Divider styled according to Professional Polish Design rules */}
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-slate-200 dark:border-slate-800"></span>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white dark:bg-slate-900 px-2 text-slate-450 dark:text-slate-500">
                Or continue with
              </span>
            </div>
          </div>

          <Button 
            type="button" 
            variant="outline" 
            className="w-full h-10 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-850 text-slate-700 dark:text-slate-300 font-medium rounded-md text-sm shadow-sm flex items-center justify-center gap-2 cursor-pointer"
          >
            <div className="shrink-0 flex items-center justify-center">
              <FcGoogle size={18} />
            </div>
            {googleText}
          </Button>
        </form>

        {/* Toggle link style */}
        <p className="text-center text-sm text-slate-500 dark:text-slate-400">
          {isLoginMode ? "Don't have an account?" : loginText}{" "}
          <button
            type="button"
            onClick={onToggleMode}
            className="text-indigo-400 dark:text-indigo-300 font-semibold hover:underline bg-transparent border-0 cursor-pointer p-0"
          >
            {isLoginMode ? "Create an account" : "Login"}
          </button>
        </p>
      </div>
    </main>
  );
};

export { Signup1 };
