---
name: FK guard for message save
description: Always call get_or_create_chat_session before INSERT message in brain.py
---

## Rule
Call `await self.db_manager.get_or_create_chat_session(user_id, chat_id)` immediately
before any `db.add(Message(...))` + `await db.commit()` in process_message.

## Why
After a backend restart, a user can resume an old thread (thread ID persists in the
frontend). If that session ID doesn't exist in `chat_sessions` (e.g., DB was
wiped), the message INSERT fails with ForeignKeyViolationError. The first call at
the top of process_message is not enough because the session might be gone by
the time the final AI response is saved (minutes later).

## How to apply
The guard is at ~line 793 in brain.py, right before the final `async with
AsyncSessionLocal()` block that saves the AI response message.
