# Analytics UI — Admin Usage Tab & User Dashboard

## What & Why
With real token data flowing and the API endpoints in place, this task replaces the placeholder charts in the admin Usage tab and adds a new "My Usage" page for regular users. Both surfaces use Recharts (already installed) and call the new analytics endpoints.

## Done looks like
- **Admin → Usage tab** (existing tab, replaced content):
  - Summary cards at the top: Today's Requests, Today's Tokens, Today's Cost, Active Users — all real numbers
  - Stacked bar chart: daily token breakdown for the last 7 / 30 days — bars split by System / User / History / Memory / Tool tokens, selectable time range
  - Cost trend line chart: daily cost over the selected range
  - Top Users table: columns for User, Requests, Total Tokens, Input, Output, Cost, Last Active — sortable, paginated (25 rows), clicking a user row opens the existing per-user analytics drill-down
  - Per-request expandable row list at the bottom: each row shows model, source, total tokens (input + output), cost, latency, timestamp — expanding a row reveals the full category breakdown (system / user / history / memory / tool / rag tokens)
- **User → "My Usage" page** (new page, accessible from the sidebar for all logged-in users):
  - Four stat cards: Today / 7 Days / 30 Days / Lifetime — each showing token count and cost
  - Line chart: daily tokens over the selected period, with a secondary line for cost
  - Stacked area chart: daily token breakdown by category (system / user / history / memory / tool)
  - Request list: the user's own recent LLM requests, same expandable-row design as admin
  - Time range selector: 7d / 30d / 90d
- Loading skeletons shown while data fetches; empty state copy shown if the user has no requests yet
- No new charting library needed — use the `recharts` components already in the codebase

## Out of scope
- CSV / PDF export buttons
- Alerting / threshold warnings
- Memory analytics sub-tab
- Organisation-level aggregation

## Steps
1. **Create `useAnalytics` hooks** — Two React hooks: `useAdminAnalytics(days)` and `useMyAnalytics(days)`. Each calls the relevant API endpoints and returns `{ data, isLoading, error }`. Use the existing `apiClient` / fetch pattern already used elsewhere in the frontend.
2. **Replace admin Usage tab content** — Swap the current placeholder charts for the real components: summary cards, stacked bar chart, cost trend line, top-users table, and expandable request list. Keep the tab title and position unchanged.
3. **Build the token breakdown chart components** — Reusable `TokenBreakdownBarChart` and `TokenTrendLineChart` components that accept time-series data and render stacked bars / lines with a legend labelled by token category.
4. **Add the "My Usage" page** — New route and page component for `/usage` (or `/my-usage`). Add a sidebar link visible to all authenticated users. Compose the stat cards, line chart, stacked area chart, and request list using the same chart components built in step 3.
5. **Build the expandable request row** — A shared `LlmRequestRow` component that renders a compact summary row and, when expanded, shows a breakdown table: system tokens / user tokens / history tokens / memory tokens / tool tokens / rag tokens / input total / output total / cost / latency / finish reason.
6. **Wire time-range selector** — A `<TimeRangeSelector days={days} onChange={setDays} />` component with 7d / 30d / 90d options, used on both the admin and user pages to re-fetch with the selected window.

## Relevant files
- `Frontend/src/components/ui/admin-dashboard.tsx`
- `Frontend/src/App.tsx`
