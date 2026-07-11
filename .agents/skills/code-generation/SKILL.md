---
name: code-generation
description: >
  Standalone script generation agent — converts browser execution traces into
  runnable Python scripts using Playwright, Tavily, or browser-use frameworks.
  Includes syntax validation with automatic fix passes.
---

## What It Does

After a browser task completes, the system can generate a standalone Python script that
reproduces the task. This is useful for turning one-off agent runs into repeatable
automation scripts.

## Runtime Files

- **Agent Spec**: [coder.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/coder.agent.md)
  — Output Rules (raw Python only, no markdown), Framework-specific templates
  (Playwright, Tavily, browser-use), self-validation rules.
- **Generator**: [ATAG.py](file:///d:/Project/SciParser/Backend/src/services/ATAG.py)
  — `ATAGProcessor.generate_code()` method. Uses `code_llm` (lower temperature 0.1)
  with optional Tavily search for URL discovery.
- **Caller**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — `self.code_processor = ATAGProcessor(self.code_llm, tavily_api_key=...)`.

## How It's Activated

Script generation is triggered by the frontend when the user requests a reproducible
script after a browser task completes.

## Key Patterns

- **Three frameworks**: The spec supports Playwright (async, headless Chromium),
  Tavily (synchronous search, no browser), and browser-use (Agent-based).
- **Ground truth**: Scripts use real URLs/selectors from the execution trace, never
  placeholder URLs like `https://example.com`.
- **Syntax validation**: Generated code is compiled and checked for syntax errors with
  up to 2 automatic fix passes.
- **Tavily enrichment**: When the task requires discovering a URL at runtime, the script
  includes a Tavily search step as a runtime fallback.

## Common Issues

- **Credit billing gap**: Script generation's LLM cost is not yet included in the
  per-run credit deduction (see `.agents/memory/credit-deduction-timing.md`).
