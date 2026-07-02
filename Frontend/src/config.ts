// config.ts
//
// Single source of truth for every environment-specific frontend value
// (API base URL, WebSocket base URL, default CDP debug URL, environment
// name). All values are sourced from Vite environment variables
// (`import.meta.env.VITE_*`) with safe development fallbacks that preserve
// same-origin request behavior. See `.env.example` for the full list of
// supported variables.

const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

// Empty string keeps requests same-origin (relative URLs), which is the
// correct default for both local dev (proxied by Vite) and production
// (served from the same origin as the backend), unless overridden.
export const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, "");

function deriveWsBaseUrl(apiBaseUrl: string): string {
  const explicit = (import.meta.env.VITE_WS_BASE_URL ?? "").trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  if (apiBaseUrl) {
    // Derive ws(s):// from the configured http(s):// API base URL.
    return apiBaseUrl.replace(/^https/i, "wss").replace(/^http/i, "ws");
  }

  // Same-origin fallback: derive from the current page location so it
  // works transparently in both development (via the Vite proxy) and
  // production.
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  return "";
}

export const WS_BASE_URL = deriveWsBaseUrl(API_BASE_URL);

// Default value pre-filled into the "Connect Your Browser" CDP URL input.
export const DEFAULT_CDP_URL =
  (import.meta.env.VITE_DEFAULT_CDP_URL ?? "").trim() || "http://localhost:9222";

// Current environment: "development" | "production" (mirrors Vite's mode).
export const ENVIRONMENT = import.meta.env.MODE ?? "development";
export const IS_PRODUCTION = import.meta.env.PROD === true;

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function wsUrl(path: string): string {
  return `${WS_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
