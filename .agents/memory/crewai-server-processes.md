---
name: CrewAI in server processes
description: CrewAI can prompt on stdin at shutdown to ask about viewing execution traces; must disable telemetry in non-interactive/server contexts.
---

CrewAI's telemetry layer prints an execution-traces summary and asks
"Would you like to view your execution traces? [y/N]" after a `crew.kickoff()`
run. In an interactive terminal this is harmless, but in a long-running
server process (e.g. a FastAPI backend that creates CrewAI agents per
request) it can attempt to read stdin and stall the request/response cycle.

**Why:** discovered while wiring CrewAI agents (Planner/Coder) into a
FastAPI backend — a smoke-test script hung waiting on this prompt after a
successful `kickoff()`.

**How to apply:** before importing/using CrewAI in a server or CI context,
set `CREWAI_DISABLE_TELEMETRY=true` and `OTEL_SDK_DISABLED=true` in the
process environment (e.g. in the startup shell script, before `exec`-ing the
Python process).
