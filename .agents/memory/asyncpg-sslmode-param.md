---
name: asyncpg rejects sslmode query param
description: Manual SQLAlchemy async engine scripts against the Replit-managed Postgres DATABASE_URL fail unless sslmode is stripped
---

Replit's Postgres `DATABASE_URL` includes a `sslmode=...` query parameter (libpq-style). The `asyncpg` driver's `connect()` does not accept `sslmode` as a kwarg, so any ad-hoc script that does `create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://"))` without stripping that query param fails with `TypeError: connect() got an unexpected keyword argument 'sslmode'`.

**Why:** The app's own SQLAlchemy setup (`Backend/src/database.py` or equivalent) already handles this internally, but one-off debugging/maintenance scripts run outside that setup do not get the same handling.

**How to apply:** When writing a throwaway script to query/update the DB directly (e.g. for QA/testing, promoting a test user, etc.), parse the URL and drop `sslmode` from the query string before creating the async engine, or reuse the app's existing engine/session factory instead of building a new one.
