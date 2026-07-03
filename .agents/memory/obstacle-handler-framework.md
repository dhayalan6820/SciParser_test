---
name: Obstacle handler framework (CAPTCHA/OTP mid-run blockers)
description: How mid-run blockers (CAPTCHA, OTP, future obstacle types) are detected, paused, resumed, and remembered per-site in SciParser's Brain.
---

Mid-run blockers are split into two kinds in `src/services/obstacle_handler.py`:
- **Agent-solvable** (CAPTCHA): `requires_human_input=False` — the agent attempts a stored bypass skill itself; outcome evaluated on the next tool result.
- **Human-only** (OTP/verification code, and future types like forced re-login or cookie walls): `requires_human_input=True` — raises `ObstacleInputNeeded`, which the retry loop in `Brain.process_message` catches to pause the run, persist a `pending_obstacle` blob into `ChatSession.session_state`, and surface the existing generic NEEDS_INPUT chat form (reused as-is, no frontend changes needed).

**Why:** Keeping detection generic in one dispatcher (`detect_obstacle`) means a brand-new obstacle type is just a new `detect_<type>` function + a `build_input_form` branch — no new pause/resume/remember plumbing, and no risk of diverging from the CAPTCHA pattern that already works.

**How to apply:** When adding a new mid-run blocker type, decide human-only vs. agent-solvable first. Procedural memory is keyed by `ObstacleMatch.skill_name` ("{category}_{obstacle_type}") — for human-only types this only records *recognition* (the site/flow uses this obstacle), never the secret/code itself. Resume logic bypasses the normal Agent-1 planning step and Agent-2 mission-objective regeneration on the first resumed attempt, feeding the user's answer straight into the tool graph instead of re-planning from scratch. Give up gracefully (no infinite re-asking) after ~2-3 failed resume attempts on the same obstacle.
