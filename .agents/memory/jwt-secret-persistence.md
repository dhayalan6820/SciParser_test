---
name: JWT_SECRET_KEY persistence in dev
description: Why login sessions randomly invalidate on backend restart, and why other requests (e.g. proxy tests) then fail with 401 instead of their real error
---

If `JWT_SECRET_KEY` is not set, dev backends often auto-generate a random signing secret at process startup (only requiring a stable one in production). Every workflow restart then invalidates all existing JWTs, causing "Signature verification failed" and 401s on unrelated endpoints (e.g. a proxy connectivity test looked like a proxy failure but was actually an auth failure — the proxy was never contacted).

**Why:** convenient default for prod-safety, but silently breaks session continuity in dev whenever the backend restarts (which happens often while iterating).

**How to apply:** when debugging a mysterious 401 after a backend restart, check first whether it's really an auth/session issue before chasing the endpoint's own logic. Fix by setting a persistent `JWT_SECRET_KEY` secret (via requestEnvVar, since it's a signing secret) so it survives restarts.
