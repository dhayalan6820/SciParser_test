# Admin Dashboard & Role-Based Access

## What & Why
Today every account is treated the same — there is no concept of "admin" vs
"regular user", no place to manage users, and no visibility into how the
system is actually performing (token spend, cost, which runs succeed vs
fail). Add a `role` to accounts (admin / user) and build a dedicated Admin
Dashboard with two halves: (1) full user management — view, edit,
suspend/disable, delete, and promote/demote roles — and (2) an operations
view surfacing token usage, cost, model/run status, and success-vs-failure
trends so an admin can see where the app is working well and where it's
struggling. Regular users keep their existing chat experience and never see
admin screens or data belonging to other users.

## Done looks like
- Every account has a role (`admin` or `user`); the very first account (or a
  designated seed account) can be promoted to admin so there's always a way in.
- Logging in as an admin shows an "Admin Dashboard" area (separate from the
  normal chat UI) listing all users with key info (email/username, role,
  status, created date, last activity).
- From the dashboard an admin can: view a user's details, edit basic profile
  fields, suspend/reactivate an account, delete an account, and change a
  user's role.
- Logging in as a regular user behaves exactly as it does today — no admin
  UI, no admin API access (calling admin endpoints as a non-admin is
  rejected).
- Suspended users cannot sign in (clear error message) until reactivated by
  an admin.
- The dashboard has an "Operations" view where an admin can see, across all
  users/runs: total and per-run token usage and cost (broken down over
  time and, where useful, by model), how many runs/agent steps succeeded
  vs. failed, and which sites/flows/error types show up most often —
  enough to answer "where does this app work well, and where does it
  struggle" at a glance.
- Numbers shown on the Operations view are drawn from real execution
  history already recorded by the app (not mocked/sample data), so they
  reflect actual usage.

## Out of scope
- Granular/custom permission systems (beyond a simple admin/user role) —
  future work if needed.
- Billing/payment collection (this is internal visibility into spend, not a
  billing system).
- Real-time/streaming metrics or alerting (a periodically-refreshed view of
  historical data is sufficient for now).
- Team/organization-level accounts or multi-tenant hierarchies.
- Audit logging of admin actions (future follow-up).
- Self-service password reset flows (unrelated to this task).

## Steps
1. **Add roles & account status to the data model** — Add a `role`
   (admin/user) and `status` (active/suspended) to the user record, with a
   safe migration for existing accounts (default them to `user`/`active`),
   plus a one-time way to designate the first admin.
2. **Enforce role checks in the backend** — Add an "admin required"
   dependency alongside the existing auth check, reject non-admins from
   admin endpoints, and block sign-in for suspended accounts with a clear
   error.
3. **Build admin user-management API** — Endpoints to list all users
   (with search/pagination), fetch a single user's details, update a user's
   profile/role/status, and delete a user.
4. **Build admin operations/metrics API** — Endpoints that aggregate the
   existing execution/token/cost logs (across all users) into summaries an
   admin can use: totals and trends for token usage and cost, run
   success/failure rates, and the most common failure reasons or
   sites/flows involved, with reasonable date-range filtering.
5. **Build the Admin Dashboard UI** — A new, separate screen (only reachable
   by admins) with: a user-management tab (table/list, detail/edit view,
   role changes, suspend/reactivate, delete with confirmation prompts) and
   an operations tab (charts/summary cards for token spend, cost, and
   success/failure trends).
6. **Wire up role-aware routing** — After login, route admins to the Admin
   Dashboard and regular users to the existing chat experience; make sure
   the admin area is not reachable by guessing a URL as a non-admin.
7. **Verify end-to-end** — Confirm an admin can manage users and view
   accurate operations metrics through the new dashboard, a suspended user
   is blocked at sign-in, a regular user cannot access any admin
   route/screen, and existing chat functionality for regular users is
   unaffected.

## Relevant files
- `Backend/src/database/chat_db.py`
- `Backend/src/services/chat_service.py`
- `Backend/src/services/brain.py:723,946`
- `Backend/src/main.py`
- `Backend/src/config.py`
- `Frontend/src/App.tsx`
- `Frontend/src/api.ts`
- `Frontend/src/components/ui/signup-1.tsx`
- `Frontend/src/components/ui/chat_page.tsx`
