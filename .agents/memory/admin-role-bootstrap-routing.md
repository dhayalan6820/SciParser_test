---
name: Admin role bootstrap & routing
description: How admin role is bootstrapped on migration and how the frontend routes admins vs regular users without a router library
---

When adding `role`/`status` to an existing `users` table via an additive migration, auto-promote the earliest-created user to `admin` if no admin exists yet. This guarantees there's always at least one admin account after deploying the feature, without requiring manual DB surgery or a separate seed script.

**Why:** Existing production data has no concept of roles yet; without a bootstrap step, every user defaults to `user` and nobody can reach the admin UI post-migration.

**How to apply:** Run the promotion check once at startup, after the additive `ALTER TABLE` migrations, inside the same startup routine that creates/verifies tables. Only promote when zero admins exist — never touch role assignments once at least one admin is present.

For frontend routing: this app has no router library (App.tsx uses conditional rendering based on auth state). Role-based routing follows the same pattern — after login, fetch the user's profile (`/me`) to get `role`, then conditionally render the admin dashboard vs the normal page. No separate router, guard component, or route table needed; a plain conditional in the top-level App component is sufficient and keeps regular users' code path completely untouched.

**Why:** Introducing a router just for a two-way admin/non-admin split would be disproportionate complexity for a codebase that doesn't otherwise use one, and risks touching the existing (working) regular-user render path.

Bootstrap the admin promotion in two places, not one: also check/promote at user-creation time (not just once at startup migration). A DB that starts truly empty (e.g. a fresh environment) never hits the startup "existing users, no admin" case — the first admin can only be created at signup time, so `create_user` must independently check `count(role='admin') == 0` and promote the new user if so.

**Why:** A code review caught that startup-only bootstrap leaves a fresh/empty DB with zero admins until a restart happens to occur after the first signup — an easy gap to miss since the "existing data" migration case and the "brand new install" case look similar but need separate bootstrap checks.

Do not reuse one state variable for two semantically different error surfaces (e.g. a fatal app-level error that renders a full-page fallback view, vs. a form-level validation/auth error meant to display inline). Give each its own state.

**Why:** In this app, `hasError` was originally a fatal-error flag driving a full-page NotFound/404 view. Repurposing it to also carry sign-in error messages meant every failed login incorrectly redirected to the 404 page instead of showing the message on the form — caught only via e2e browser testing, not by type-checking or unit tests, since the types lined up fine.
