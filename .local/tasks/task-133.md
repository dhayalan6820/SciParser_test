---
title: Admin Dashboard: Premium Redesign + Real Monitoring Sections
---
# Admin Dashboard: Premium Redesign + Real Monitoring Sections

## What & Why
The Admin Dashboard (Task #127) works but is visually basic — plain tabs,
no theme switching, no charts, no animation. The user provided a detailed
design brief modeled on modern SaaS dashboards (Vercel/Stripe/Linear/
Notion/Supabase style: sidebar nav, KPI cards with trend graphs,
interactive charts, activity timeline, live agent/browser monitoring).
Restyle the dashboard to that premium standard, and add new dashboard
sections that expose data the backend already tracks but the UI doesn't
yet surface (agent run monitoring, automation/workflow monitoring, browser
session details, token/usage breakdowns, security/login activity).

Everything built must be backed by real data already recorded by the app
(users, `AgentExecutionLog`/execution history, browser session state,
schedules/automations, auth/login events). Do not fabricate data for
systems the app doesn't have.

## Explicitly out of scope (no real data source exists)
- Organizations / multi-tenant workspaces, workspace switcher.
- Billing Dashboard: invoices, payments, credits, subscription history,
  payment methods.
- API Keys management/marketplace.
- System Health infra metrics: CPU/RAM/GPU/Disk/Bandwidth/Redis/
  Queues/Workers/DB-server-level metrics, API latency dashboards.
- Command palette, global search, workspace switcher, support tickets,
  feature flags, developer tools section.
- Operations filtering/export by user/date/model and CSV/JSON export —
  already covered by in-progress Task #129; this task should not duplicate
  that work (build on top of whatever UI Task #129 lands, if it merges
  first).

## Done looks like
- The dashboard shell (top nav, sidebar, content area) is restyled to a
  premium look: rounded cards, soft shadows, consistent spacing, working
  dark/light theme toggle, smooth hover/transition animations, responsive
  down to mobile (sidebar becomes a drawer).
- Dashboard Overview: KPI stat cards (total users, active users, running
  agents, completed automations, success rate, total token usage, total
  cost) each with an icon, value, % change vs. a prior period, and a small
  trend sparkline — all computed from real historical data.
- Analytics section: interactive charts (using data already available from
  execution logs) for runs over time, success/error rate, token
  consumption, and browser-session volume, with a 7d/30d/90d/1y range
  toggle.
- Recent Activity timeline: a real feed of recent events (logins, agent
  run started/completed/failed, user registered, schedule triggered)
  pulled from existing tables/logs, not synthetic data.
- AI Agent Monitoring section: table/list of recent+running agent
  executions with status (running/queued/failed/completed), runtime,
  and a way to drill into a single run's step timeline/logs; retry/cancel
  actions wired to real backend operations where such operations already
  exist (if no cancel/retry endpoint exists yet, add a minimal one scoped
  to this feature).
- Automation Monitoring section: real schedule/automation run history
  (status, last run time, success/fail counts) reusing the existing
  scheduler data.
- Browser Automation section: list of active/recent browser sessions with
  status, using the existing browser-session/WS stream infrastructure
  already in the app (no new browser infra).
- Usage Dashboard: token usage broken down by prompt/completion (and
  cached, if tracked) tokens, daily/monthly totals, and top users by usage
  — derived from existing `AgentExecutionLog` data.
- Security section: recent logins and failed login attempts, and currently
  suspended/blocked users — derived from real auth/user records (only
  include failed-login tracking if it's cheap to add via existing auth
  code path; otherwise scope down to logins + suspensions using existing
  data).
- Tables (Users, Agent runs, Automations, Browser sessions) support
  sorting, search, and pagination; column visibility and CSV export are
  nice-to-have if time allows but not required if they'd duplicate #129.
- Regular (non-admin) users are unaffected; no new admin-only data leaks
  into non-admin views; existing role/auth checks from Task #127 are
  reused unchanged.
- Existing Users tab functionality (search/edit/suspend/delete/promote)
  and Operations tab metrics keep working exactly as before.

## Steps
1. **Design the shell** — Rework `admin-dashboard.tsx`'s layout into
   top-nav + collapsible sidebar + content area, add a dark/light theme
   toggle (reuse the app's existing theme system if one exists; otherwise
   add a minimal one scoped to the admin area), and apply the shadcn/ui
   card/shadow/rounded-corner styling described in the brief.
2. **Audit backend data availability** — For each new section
   (agent monitoring, automation monitoring, browser sessions, usage
   breakdown, security/logins), confirm what's already queryable from
   `chat_service.py` / `AgentExecutionLog` / scheduler tables / auth
   tables, and note any small backend additions needed (e.g. a lightweight
   endpoint to list recent browser sessions, or a login-attempts table if
   one doesn't exist and is cheap to add).
3. **Build KPI + Analytics overview** — New stat cards with trend
   sparklines and range-filterable charts (7d/30d/90d/1y), backed by
   aggregation endpoints (new or extending the existing operations-metrics
   endpoint).
4. **Build Recent Activity timeline** — A merged, time-sorted feed of
   real events across logins, agent runs, and automations.
5. **Build AI Agent Monitoring, Automation Monitoring, and Browser
   Automation sections** — New sidebar pages/tabs, each with a real-data
   table/list and drill-in detail view; add retry/cancel actions only
   where a safe backend hook already exists or can be added simply.
6. **Build Usage Dashboard and Security section** — Token/cost breakdown
   views and login/suspension activity views using existing data.
7. **Polish & responsiveness pass** — Skeleton loaders for
   loading states, empty states where a section has no data yet, error
   states for failed fetches, and mobile drawer navigation.
8. **Verify end-to-end** — Confirm existing Users/Operations
   functionality is unchanged, non-admins still can't reach any admin
   route, all new sections show real data (spot-check against the
   database), and run the backend test suite plus a UI smoke test of the
   new dashboard.

## Relevant files
- `Frontend/src/components/ui/admin-dashboard.tsx`
- `Backend/src/services/chat_service.py`
- `Backend/src/database/chat_db.py`
- `Backend/src/main.py` (admin routes)
- `Backend/src/services/brain.py` (execution logging)
- `Frontend/src/api.ts`