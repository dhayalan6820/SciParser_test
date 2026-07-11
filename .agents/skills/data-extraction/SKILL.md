---
name: data-extraction
description: >
  Data extraction and aggregation subsystem — handles web scraping, pagination,
  infinite scroll, item counting, and de-duplication for extraction tasks.
  Includes the aggregator deterministic agent and the aggregator agent spec.
---

## What It Does

When a task is classified as a data extraction mission (scraping, crawling, collecting),
the Aggregator agent activates inside the browser tool loop to:
- Track item count across pages/scrolls
- Detect stalled pagination (same count after scroll → end of results)
- Enforce target count limits
- Guide the LLM with extraction-specific strategy sections

## Runtime Files

- **Agent Spec**: [aggregator.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/aggregator.agent.md)
  — Extraction Strategy (Phase 1–3), Pagination & Infinite Scroll, Data Cleaning Rules,
  Decision Tree, Hard Rules, Recovery Protocol.
- **Deterministic Module**: [aggregator_agent.py](file:///d:/Project/SciParser/Backend/src/services/aggregator_agent.py)
  — `detect_extraction_task()`, `ExtractionProgressState`, `detect_data_extraction_context()`,
  `detect_pagination_context()`, `handle_aggregator_observation()`.
- **Integration Point**: [brain.py](file:///d:/Project/SciParser/Backend/src/services/brain.py)
  — Lines ~1589-1620 in `_call_tool()`: the aggregator block runs when
  `_is_extraction_task` is True and data-listing or pagination signals are detected.

## How It's Activated

1. `detect_extraction_task(task_summary, confirmed_inputs)` checks for keywords like
   "scrape", "extract", "collect data", "get all", "list all", etc.
2. If True, the `_aggregator_spec_guidance` is loaded from the spec's Decision Tree
   and Hard Rules sections.
3. On each tool observation, `handle_aggregator_observation()` tracks item count and
   appends progress/stall/completion notes to the observation.

## Key Patterns

- **Keyword-gated activation**: Unlike address/login/calendar agents (which check
  `confirmed_inputs` for specific field types), the aggregator checks the task summary
  text against regex patterns.
- **Stall detection**: `MAX_STALLS = 2` — if two consecutive observations show the same
  item count, extraction stops (end of results).
- **Target count**: `confirmed_inputs.get("count")` or `confirmed_inputs.get("limit")`
  sets the extraction target.

## Common Issues

- **Over-activation**: The keyword list is broad — "extract" matches non-scraping tasks.
  If the aggregator activates unnecessarily, it adds noise to observations.
- **60+ tool calls**: For simple extractions (e.g., "get top 5 from Hacker News"), the
  full agent pipeline (all 11 detectors running on every observation) is overkill.
  Consider simplifying the pipeline for straightforward extraction tasks.
