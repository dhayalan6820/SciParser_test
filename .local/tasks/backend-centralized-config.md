# Centralize backend config, remove hardcoded secrets/URLs

## What & Why
Backend configuration (JWT secret, API keys, database URL, CORS origins, SMTP settings, third-party base URLs, ports, timeouts) is currently scattered across many files, and some values — most critically the JWT signing secret — are hardcoded directly in source code as fallback values. This is a security risk (anyone with repo access can forge auth tokens) and makes it hard to know what needs to change between development and production. Consolidate everything into one settings module that reads from environment variables, with sensible dev defaults and hard failures when a required production secret is missing.

## Done looks like
- A single settings file is the one place a developer looks to see every configurable value the backend uses, and to know which ones must be set via secrets for production.
- No API keys, JWT secret, database credentials, or SMTP credentials exist anywhere in source code, including as fallback/default values — only in environment variables.
- Non-secret infrastructure values (ports, timeouts, base URLs, CORS origins) have safe development defaults but can be overridden per-environment.
- The app clearly fails at startup with an actionable error message if a required production secret (JWT secret, DB URL) is missing, instead of silently using an insecure fallback.
- Existing functionality (auth, chat, browser automation, scheduling, email) continues to work unchanged in this dev environment.

## Out of scope
- Adding new features or changing any runtime behavior beyond how config values are sourced.
- Rotating/changing the actual values of existing secrets already in use — only removing hardcoded fallbacks and wiring through env vars.
- Frontend configuration (covered by a separate task).

## Steps
1. **Create the central settings module** — Add one module that defines every configurable value (JWT secret + algorithm, DATABASE_URL, OPENROUTER_API_KEY + base URL, TAVILY_API_KEY, SMTP host/port/user/pass/from, CORS allowed origins, server host/port, HTTP client timeouts, browser automation timeouts) as environment-driven settings with an `ENVIRONMENT` flag (development/production). Secrets have no hardcoded fallback value; non-secret infra values have documented dev defaults.
2. **Fail fast on missing required production config** — When `ENVIRONMENT=production`, raise a clear startup error if JWT secret, DATABASE_URL, or other required secrets are unset, instead of silently falling back to an insecure default.
3. **Replace every hardcoded value across the backend** — Update all files currently defining or duplicating these values (JWT secret in two places, OpenRouter base URL, CORS `allow_origins=["*"]`, SMTP settings, uvicorn host/port, HTTP/browser timeouts, localhost CDP URLs) to import from the new settings module instead.
4. **Document required environment variables** — Update `.env.example` (or create one if missing) to list every variable the settings module reads, with comments distinguishing "required in production" from "safe dev default", and use the environment-secrets flow to ensure real secret values are set for this environment rather than left as placeholders.
5. **Verify** — Restart the backend workflow and confirm it starts cleanly, auth/login still works, and no behavior changed.

## Relevant files
- `Backend/src/utils/validator.py:15,25`
- `Backend/src/services/chat_service.py:20-21`
- `Backend/src/services/brain.py:533,543,600,612,635,1357`
- `Backend/src/main.py:292,307,539,1194,1327,1458`
- `Backend/src/services/ATAG.py:389`
- `Backend/src/agents/browser_use_bridge.py:158-163,244,687,867`
- `Backend/src/database/chat_db.py:13,15`
- `Backend/src/database/init_db.py:3,9`
