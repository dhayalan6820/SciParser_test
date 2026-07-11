"""
Aggregator / Data-Extraction Interaction Agent — deterministic support layer
for web scraping, data collection, and pagination/infinite-scroll handling.

Same pattern as `booking_agent.py` / `address_agent.py`: the Browser agent
still does the actual clicking and reading; this module gives it (and Brain's
tool-loop) the deterministic piece a raw LLM should never be trusted to handle
on its own — whether new items actually appeared after a scroll, whether a
target item count has been met, and when to stop a runaway pagination loop.

Public API used by brain.py:
  1. `detect_extraction_task`         — is this a scraping/extraction task?
  2. `ExtractionProgressState`        — per-run mutable state dataclass
  3. `detect_data_extraction_context` — does the page observation contain a
                                        listing / grid / table of items?
  4. `detect_pagination_context`      — does the observation have next-page or
                                        infinite-scroll signals?
  5. `handle_aggregator_observation`  — main per-turn handler called by brain.py

This module has ZERO dependency on LangGraph / Brain so detection logic can be
unit-tested in isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import HumanMessage
import json

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# How many consecutive observations may show the same item count before we
# treat it as end-of-results and stop the pagination loop.
MAX_STALLS = 2

# ──────────────────────────────────────────────────────────────────────────────
# Task-intent detection
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACTION_TASK_KEYWORDS = [
    r"\bscrap(?:e|ing)\b",
    r"\bextract(?:ing)?\b",
    r"\bcollect(?:ing)?\s+data\b",
    r"\bget\s+all\b",
    r"\bfetch\s+all\b",
    r"\blist\s+all\b",
    r"\bgather\s+(?:all\s+)?(?:data|information|products|prices|results|items|listings)\b",
    r"\baggregat(?:e|ing)\b",
    r"\bharvest(?:ing)?\b",
    r"\bcrawl(?:ing)?\b",
    r"\bpars(?:e|ing)\b",
    r"\bweb\s+scrape?\b",
    r"\bdata\s+(?:extract|collect|mine|harvest)\b",
    r"\ball\s+(?:products?|prices?|listings?|results?|items?|records?)\b",
    r"\bevery\s+(?:product|price|listing|result|item|record)\b",
]

_EXTRACTION_TASK_RE = [re.compile(p, re.IGNORECASE) for p in _EXTRACTION_TASK_KEYWORDS]


def detect_extraction_task(task_summary: str, confirmed_inputs: Optional[Dict[str, Any]] = None) -> bool:
    """Return True if the task looks like a data extraction / scraping mission.

    Checks the task summary text against a list of extraction keywords.
    Also checks confirmed_inputs for an explicit ``extraction_mode`` flag
    that callers can set to force the aggregator agent to activate.
    """
    if confirmed_inputs and confirmed_inputs.get("extraction_mode"):
        return True
    if not task_summary:
        return False
    text = str(task_summary)
    return any(rx.search(text) for rx in _EXTRACTION_TASK_RE)


# ──────────────────────────────────────────────────────────────────────────────
# Page-observation detection
# ──────────────────────────────────────────────────────────────────────────────

_DATA_LISTING_HINTS = [
    r"\bproduct(?:\s+card)?s?\b",
    r"\blisting(?:s)?\b",
    r"\bresult(?:s)?\b",
    r"\bitem(?:s)?\b",
    r"\brow(?:s)?\b",
    r"\brecord(?:s)?\b",
    r"\bgrid\b",
    r"\btable\b",
    r"\bcatalog(?:ue)?\b",
    r"\bprice\b",
    r"\brating\b",
    r"\breview(?:s)?\b",
    r"\bsearch results\b",
    r"\bmatches found\b",
    r"\bshowing\s+\d+",
    r"\d+\s+(?:products?|items?|results?|listings?)\b",
]

_PAGINATION_HINTS = [
    r"\bnext\s*(?:page|»|›|→|\u003e)?\b",
    r"\bload\s+more\b",
    r"\bshow\s+more\b",
    r"\bpage\s+\d+\s*(?:of|/)\s*\d+\b",
    r"\b(?:page|p)\s*\d+\b",
    r"\bpagination\b",
    r"»|›|→",  # common next-page glyphs
    r"\bscroll\s+(?:to\s+)?(?:load|more)\b",
    r"\binfinite\s+scroll\b",
    r"\bmore\s+(?:products?|items?|results?)\b",
]

_DATA_LISTING_RE = [re.compile(p, re.IGNORECASE) for p in _DATA_LISTING_HINTS]
_PAGINATION_RE   = [re.compile(p, re.IGNORECASE) for p in _PAGINATION_HINTS]

# Regex to extract the number of items/results reported by the page
_ITEM_COUNT_RE = re.compile(
    r"(\d[\d,]*)\s+(?:products?|items?|results?|listings?|matches?)",
    re.IGNORECASE,
)

# Regex to extract page-progress indicators like "Page 3 of 12"
_PAGE_PROGRESS_RE = re.compile(
    r"page\s*(\d+)\s*(?:of|/)\s*(\d+)",
    re.IGNORECASE,
)


def detect_data_extraction_context(observation_text: str) -> bool:
    """True if the observation contains signals of a product/item listing or
    data grid — i.e. there is data to extract from this page view."""
    if not observation_text:
        return False
    t = str(observation_text).lower()
    return any(rx.search(t) for rx in _DATA_LISTING_RE)


def detect_pagination_context(observation_text: str) -> bool:
    """True if the observation contains pagination controls (Next button,
    page numbers, Load More, or infinite-scroll signals)."""
    if not observation_text:
        return False
    t = str(observation_text)
    return any(rx.search(t) for rx in _PAGINATION_RE)


def extract_page_progress(observation_text: str) -> Optional[Tuple[int, int]]:
    """Return (current_page, total_pages) if an explicit page indicator is
    present in the observation, otherwise None."""
    if not observation_text:
        return None
    m = _PAGE_PROGRESS_RE.search(str(observation_text))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def extract_reported_item_count(observation_text: str) -> Optional[int]:
    """Return the total item count reported by the page (e.g. '234 products'),
    or None if no such indicator is found."""
    if not observation_text:
        return None
    m = _ITEM_COUNT_RE.search(str(observation_text))
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Guidance builders
# ──────────────────────────────────────────────────────────────────────────────

def build_extraction_progress_guidance(
    items_extracted: int,
    target_count: int,
    current_page: Optional[int] = None,
    total_pages: Optional[int] = None,
) -> str:
    """Build an inline guidance note confirming extraction is on-track."""
    page_info = ""
    if current_page is not None:
        page_info = f" (page {current_page}" + (f" of {total_pages}" if total_pages else "") + ")"
    remaining = max(0, target_count - items_extracted) if target_count > 0 else None
    remaining_str = f" — {remaining} more needed" if remaining is not None else ""
    return (
        "\n\n[AGGREGATOR_PROGRESS]\n"
        f"Items extracted so far: {items_extracted}{page_info}{remaining_str}. "
        "Verify each new item is unique before appending. Continue to the next "
        "page/scroll position if the target count has not been reached."
    )


def build_stall_guidance(current_page: Optional[int], stall_count: int) -> str:
    """Warn that the page / item count hasn't changed after a scroll or Next click."""
    page_str = f"page {current_page}" if current_page is not None else "the current position"
    return (
        "\n\n[AGGREGATOR_STALLED]\n"
        f"Still on {page_str} after {stall_count} attempt(s) to advance — "
        "no new items appeared. Re-inspect the page: look for a disabled Next "
        "button, a 'You've reached the end' message, a rate-limit banner, or a "
        "loading failure. If this occurs again the run will report end-of-results."
    )


def build_end_of_results_guidance(items_extracted: int) -> str:
    return (
        "\n\n[AGGREGATOR_END_OF_RESULTS]\n"
        f"No new items appeared after repeated attempts. End of results reached "
        f"with {items_extracted} items collected. Finalise the JSON output now."
    )


def build_target_reached_guidance(items_extracted: int, target_count: int) -> str:
    return (
        "\n\n[AGGREGATOR_TARGET_REACHED]\n"
        f"Target of {target_count} items reached ({items_extracted} collected). "
        "Stop pagination immediately and output the final JSON array."
    )


# ──────────────────────────────────────────────────────────────────────────────
# State dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractionProgressState:
    """Per-run tracking for the extraction stall / end-of-results policy.

    Mirrors the shape of ``BookingProgressState`` and ``AddressAutocompleteState``.
    """
    items_extracted: int = 0
    last_item_count: Optional[int] = None   # item count at the previous turn
    current_page: Optional[int] = None
    last_page: Optional[int] = None
    stall_count: int = 0
    spec_injected: bool = False
    target_reached: bool = False
    end_of_results: bool = False
    dynamic_schema: Optional[Dict[str, Any]] = None
    last_confidence_score: float = 0.0

# ──────────────────────────────────────────────────────────────────────────────
# Deep Data Extraction (Schema Generation & Confidence)
# ──────────────────────────────────────────────────────────────────────────────

async def generate_dynamic_schema(task_summary: str, observation_text: str, llm) -> Optional[Dict[str, Any]]:
    """Uses the LLM to generate a dynamic JSON schema based on the task and page content."""
    prompt = (
        f"You are a Data Extraction Architect.\n"
        f"TASK: {task_summary}\n"
        f"PAGE CONTENT START:\n{str(observation_text)[:4000]}\nPAGE CONTENT END\n\n"
        f"Generate a strict JSON Schema (just the 'properties' dict) for a single record to extract.\n"
        f"Focus on the exact fields the user wants in the task.\n"
        f"Output ONLY valid JSON."
    )
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return None

async def assess_extraction_confidence(items: List[Dict], dynamic_schema: Dict[str, Any], llm) -> float:
    """Uses the LLM to assess how completely the extracted items fulfill the schema."""
    if not items or not dynamic_schema:
        return 0.0
        
    prompt = (
        f"Review these {len(items)} extracted items against the schema.\n"
        f"SCHEMA: {json.dumps(dynamic_schema)}\n"
        f"ITEMS: {json.dumps(items[:5])}\n\n"
        f"Rate the extraction completeness and quality on a scale from 0.0 to 1.0.\n"
        f"Output ONLY a single float number (e.g. 0.85)."
    )
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        match = re.search(r'(0\.\d+|1\.0)', resp.content)
        if match:
            return float(match.group(0))
    except Exception:
        pass
    return 1.0 if items else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Main per-turn handler (called by brain.py _call_tool)
# ──────────────────────────────────────────────────────────────────────────────

def handle_aggregator_observation(
    observation_text: str,
    state: ExtractionProgressState,
    task_domain: str,
    target_count: int = 0,
    spec_guidance: Optional[str] = None,
) -> str:
    """Call after each tool execution when the task is an extraction mission
    AND the current observation shows a data-listing or pagination context.

    Injects the aggregator.agent.md Decision Tree + Hard Rules on the first
    call (spec_guidance), then tracks extraction progress across turns and
    appends appropriate guidance notes:

      * Progress confirmation when items / page count advances.
      * Stall warning when the item count / page stays the same.
      * End-of-results marker when two consecutive stalls occur.
      * Target-reached marker when collected items ≥ target_count.

    Parameters
    ----------
    observation_text : str
        Raw tool observation returned by the browser tool.
    state : ExtractionProgressState
        Mutable per-run state shared across all _call_tool invocations.
    task_domain : str
        e.g. "amazon.com" — used for context in guidance text.
    target_count : int
        Requested number of items (0 = no limit, collect all).
    spec_guidance : str | None
        Aggregator spec Decision Tree + Hard Rules text, injected once on the
        first extraction observation (mirrors address/calendar/login pattern).

    Returns
    -------
    str
        The (possibly augmented) observation text.
    """
    text = str(observation_text)

    # Inject spec guidance once on the first extraction observation
    if spec_guidance and not state.spec_injected:
        text += spec_guidance
        state.spec_injected = True

    # ── Target already reached? Just confirm and stop. ───────────────────────
    if state.target_reached:
        text += build_target_reached_guidance(state.items_extracted, target_count)
        return text

    # ── End-of-results already confirmed? Finalise. ──────────────────────────
    if state.end_of_results:
        text += build_end_of_results_guidance(state.items_extracted)
        return text

    # ── Page progress tracking ────────────────────────────────────────────────
    page_progress = extract_page_progress(text)
    if page_progress:
        current_page, total_pages = page_progress
        state.current_page = current_page

    # ── Reported item count (e.g. "234 products") ────────────────────────────
    reported_count = extract_reported_item_count(text)

    # ── Stall detection — compare with previous turn ─────────────────────────
    # A stall is when neither the page number nor the reported item count
    # changed since the last observation.
    current_page_num = state.current_page
    page_stalled   = (current_page_num is not None) and (current_page_num == state.last_page)
    count_stalled  = (reported_count is not None) and (reported_count == state.last_item_count)

    if page_stalled or count_stalled:
        state.stall_count += 1
        if state.stall_count > MAX_STALLS:
            # End of results — finalise
            state.end_of_results = True
            text += build_end_of_results_guidance(state.items_extracted)
            return text
        text += build_stall_guidance(current_page_num, state.stall_count)
    else:
        # Progress made — reset stall counter
        state.stall_count = 0
        if reported_count is not None:
            state.items_extracted = reported_count
        state.last_page       = current_page_num
        state.last_item_count = reported_count

        # Check if target is now met
        if target_count > 0 and state.items_extracted >= target_count:
            state.target_reached = True
            text += build_target_reached_guidance(state.items_extracted, target_count)
            return text

        # Normal progress note
        total_p = page_progress[1] if page_progress else None
        text += build_extraction_progress_guidance(
            state.items_extracted, target_count, current_page_num, total_p
        )

    return text
