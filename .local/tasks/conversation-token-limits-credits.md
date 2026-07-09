# Per-chat token counts, usage limits & credits

## What & Why
Admins can currently see a user's total token/cost usage, but not a breakdown per conversation, and there's no way to cap how many tokens a user can consume or to grant them extra capacity. This adds visible per-conversation token counts, a per-user token/usage limit that actually blocks further usage once exhausted, and an admin-managed credits balance so admins can control and top up what each user can use.

## Done looks like
- Each conversation shows its own input/output token counts and a total, and a user's total token usage across all their conversations is visible (to the user and/or admin, matching how usage is already surfaced today).
- Every user has a credit balance. Sending a chat message / running an automation consumes credits based on tokens used; when a user's balance runs out, they see a clear message and further usage is blocked until they have credits again.
- Admins can view any user's current credit balance and remaining allowance, and can grant/adjust (add or set) a user's credits from the admin dashboard.
- Existing users get sensible default credits so nothing breaks for current accounts after this ships.

## Out of scope
- Payment processing / purchasing credits with real money (this is admin-granted credits only, no billing integration).
- Changing the underlying cost-per-token pricing model already used for cost calculation.
- Security/audit logging of credit changes (out of scope per prior analytics work, which explicitly excluded security metrics).

## Steps
1. **Data model for credits & limits** — Add persistent fields for a user's credit balance (and/or token limit) on the user record, with a migration and sensible defaults for existing users.
2. **Per-conversation token aggregation** — Compute and expose input/output/total token counts per conversation (chat), reusing the existing token-usage data already recorded per message/run, and a rolled-up total per user.
3. **Enforcement at usage time** — Before/while processing a chat message or automation run, check the user's remaining credits; if exhausted, stop the run and return a clear, user-facing "out of credits" message instead of proceeding. Deduct credits based on actual tokens used after each run.
4. **Admin credit management UI** — Let admins view a user's credit balance/usage and grant or adjust credits (e.g. from the Users table or the user analytics drill-down), with immediate effect.
5. **Surface per-conversation counts in the UI** — Show the per-conversation token counts (and running total) somewhere sensible for the user (e.g. chat history) and for admins (e.g. user analytics drill-down), consistent with existing usage displays.

## Relevant files
- `Backend/src/database/chat_db.py:65-111`
- `Backend/src/services/chat_service.py`
- `Backend/src/services/brain.py:108-125,740-751`
- `Backend/src/schemas/schema.py:69-122`
- `Backend/src/main.py`
- `Frontend/src/api.ts:934-1018`
- `Frontend/src/components/ui/admin/users-tab.tsx`
- `Frontend/src/components/ui/admin/user-analytics-panel.tsx`
