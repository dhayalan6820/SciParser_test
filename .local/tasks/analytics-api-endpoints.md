# Analytics API Endpoints

## What & Why
Once the `llm_requests` table is populated with real data, the frontend needs clean API endpoints to query it. This task adds backend routes for both the admin-facing analytics (all users, system-wide) and the user-facing "my usage" view. All endpoints are read-only, paginated, and filterable by date range.

## Done looks like
- **Admin endpoints** (require admin role):
  - `GET /admin/analytics/overview` — today's totals: requests, tokens (by type), cost, active users
  - `GET /admin/analytics/top-users?days=7&limit=25` — ranked table: user, total tokens, input tokens, output tokens, cost, request count, last active
  - `GET /admin/analytics/token-breakdown?days=7` — daily time-series: per-day totals for system / user / history / memory / tool / rag / input / output tokens and cost
  - `GET /admin/analytics/requests?chat_id=&user_id=&days=7&page=1&limit=50` — paginated list of `llm_requests` rows with all columns, filterable by chat/user/date
- **User endpoints** (authenticated, own data only):
  - `GET /users/me/analytics?days=30` — stats cards: today / 7d / 30d / lifetime token totals, cost, request count, average tokens per request
  - `GET /users/me/token-breakdown?days=30` — daily time-series: per-day breakdown by token category (system / history / memory / tool / rag / input / output)
  - `GET /users/me/requests?chat_id=&page=1&limit=50` — paginated list of the user's own `llm_requests` rows
- All endpoints return JSON. No CSV/PDF export at this stage.
- Existing admin endpoints (`/admin/usage`, `/admin/metrics/overview`, etc.) continue to work unchanged.

## Out of scope
- CSV / Excel / PDF export
- Spike detection or alerting
- WebSocket / real-time push
- Memory analytics or RAG analytics breakdowns beyond token counts

## Steps
1. **Create `analytics_service.py`** — A new service module with async query functions that read from `llm_requests` (and fall back to `agent_execution_logs` for any rows that predate the new table). Keep all SQL here, away from route handlers.
2. **Add admin analytics routes to `main.py`** — Wire the four admin endpoints listed above. Enforce the existing `require_admin` dependency. Return data directly as JSON dicts; no new Pydantic response models needed unless one already exists that fits.
3. **Add user analytics routes to `main.py`** — Wire the three user endpoints. Enforce `get_current_user` and filter all queries to `user_id = current_user.user_id` so users can never see each other's data.
4. **Add date-range and pagination helpers** — Small utility functions for parsing `?days=N` into a UTC `since` timestamp and `?page=N&limit=M` into SQL `OFFSET`/`LIMIT`. Reuse across both admin and user routes.

## Relevant files
- `Backend/src/main.py`
- `Backend/src/services/chat_service.py`
- `Backend/src/database/chat_db.py`
