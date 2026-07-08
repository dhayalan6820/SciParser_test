---
name: Alembic introduced alongside raw-SQL schema management
description: This codebase historically managed schema via CREATE TABLE IF NOT EXISTS in init_db.py; Alembic was added for new tables without removing that path.
---

Alembic (async-compatible env.py, reusing `src.database.chat_db.DATABASE_URL`/`Base.metadata`
directly instead of a hardcoded `sqlalchemy.url`) now coexists with the older pattern of raw
`CREATE TABLE IF NOT EXISTS` statements in `Backend/src/database/init_db.py`, which still runs
on every app startup.

**Why:** every prior schema change in this project was done via init_db.py raw SQL, and a task
required an Alembic migration for a new table without breaking existing deployments that
don't run `alembic upgrade` explicitly. Both paths create the same table; whichever runs first
wins, the other is a no-op (`IF NOT EXISTS`).

**How to apply:** for genuinely new tables going forward, prefer writing a real Alembic
migration (source of truth) and optionally keep a defensive `CREATE TABLE IF NOT EXISTS`
in init_db.py only if you need zero-downtime compatibility with deployments that skip
`alembic upgrade`. If a table already exists when you add its first migration, running
`alembic upgrade head` will fail with "already exists" — run `alembic stamp head` instead
to mark the DB as up to date without re-running the DDL.
