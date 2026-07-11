---
name: planner-agent
description: >
  Input understanding and mission planning agent — Agent 1 and Agent 2 in the
  pipeline. Classifies user intent, extracts confirmed_inputs, generates
  NEEDS_INPUT forms, and produces numbered Mission Objectives for execution.
---

## What It Does

The Planner handles the first two stages of every request:
1. **Agent 1 (Input Understanding)**: Decides if the task is READY or NEEDS_INPUT.
   Extracts `task_summary`, `confirmed_inputs`, and `discovery_strategy`.
2. **Agent 2 (Mission Planning)**: Generates a numbered MISSION OBJECTIVE with a
   REASONING block and a PLAN (JSON array of tasks/subtasks) for the Browser agent.

## Runtime Files

- **Agent Spec**: [planner.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/planner.agent.md)
  — Input Understanding decision logic, precedence rules, mission design principles,
  output format for both READY and NEEDS_INPUT responses.
- **Processor**: [ATAG.py](file:///d:/Project/SciParser/Backend/src/services/ATAG.py)
  — `ATAGProcessor` class: `run_input_understanding()`, `run_planner()`, `run_critic()`,
  `summarize_context()`, `generate_code()`.
- **Caller**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — `process_message()` calls `atag_processor.run_input_understanding()` for Agent 1,
  then `atag_processor.run_planner()` for Agent 2.

## How It's Activated

Every user message goes through Agent 1 first (unless resuming from an obstacle pause).
Agent 2 runs only when Agent 1 returns `READY`.

## Key Patterns

- **Precedence rule**: Current user message always wins over chat history values —
  the spec includes an explicit "Precedence Rule" section to prevent stale credential reuse.
- **Override intent detection**: `Brain._is_credential_override_intent()` detects phrases
  like "use a different account" and adds a stronger directive to Agent 1.
- **Reset intent detection**: `Brain._is_reset_intent()` detects "start over" phrases
  and wipes prior session state.
- **Discovery strategies**: The planner classifies how the browser agent should find
  its target — `direct_execution`, `tavily_search_for_url`, or `tavily_search_for_details`.

## Common Issues

- **Stale history values**: Agent 1 sometimes reuses a password from a prior turn instead
  of asking for a fresh one. The precedence rule in the spec mitigates this.
- **Over-asking**: Agent 1 may ask for inputs that can be discovered autonomously. The spec
  explicitly says to ONLY ask for truly missing critical info.
