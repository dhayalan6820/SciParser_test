---
title: Centralize frontend config, remove hardcoded URLs
---
# Centralize frontend config, remove hardcoded URLs

## What & Why
Frontend API/WebSocket base URLs and other environment-specific values (default CDP URL, dev proxy target) are currently duplicated and hardcoded across multiple files (`api.ts`, `api/agent.ts`, `chat_page.tsx`, `vite.config.ts`). There is no single place to see or change these values for development vs. production, and no actual usage of Vite env variables despite an `.env.example` implying support for it. Consolidate everything into one config module driven by Vite environment variables.

## Done looks like
- A single config file is the one place a developer looks to see and change every environment-specific frontend value (API base URL, WebSocket base URL, default CDP debug URL, dev proxy target).
- Switching between development and production no longer requires touching multiple files — only environment variables change.
- No hardcoded backend URLs remain duplicated across `api.ts`, `api/agent.ts`, and UI components; they all read from the shared config.
- Existing functionality (API calls, WebSocket streams, CDP connect flow) continues to work unchanged in this dev environment.

## Out of scope
- Backend configuration (covered by a separate task).
- Any actual API/URL value changes — only how they're sourced/organized.
- Third-party asset/CDN URLs unrelated to the app's own backend (fonts, images, proxy provider examples).

## Steps
1. **Create the central frontend config module** — Add one module exporting the API base URL, derived WebSocket base URL, default CDP debug URL, and current environment (dev/prod), all sourced from Vite env variables (`import.meta.env.VITE_*`) with safe development fallbacks matching current behavior (same-origin requests).
2. **Wire Vite dev proxy off the same source of truth** — Update `vite.config.ts` so the backend proxy target for local development is read from an env variable rather than hardcoded, defaulting to the current local value.
3. **Replace duplicated URL construction** — Update `api.ts`, `api/agent.ts`, and any component building API/WebSocket URLs directly (e.g. the CDP default input, browser stream WebSocket) to import from the new config module instead of hardcoding or redefining `BASE_URL`.
4. **Document required environment variables** — Update `Frontend/.env.example` to list every variable the config module reads, distinguishing values needed for production deployment from safe local defaults.
5. **Verify** — Restart the frontend workflow and confirm the app loads, login works, and chat/browser streaming still connects correctly.

## Relevant files
- `Frontend/src/api.ts:3,60,469`
- `Frontend/src/api/agent.ts:1,58`
- `Frontend/src/App.tsx:37`
- `Frontend/src/components/ui/chat_page.tsx:162,564,2271`
- `Frontend/vite.config.ts:18,22`
- `Frontend/.env.example`