"""
Recovery decision tree — deterministic failure pre-classification.

`ATAG.run_critic` already asks the LLM to classify a failure using the
"Recovery Protocol" section of `browser.agent.md` (the source of truth for
the full decision tree — see `Backend/src/agents/specs/recovery.md` for a
human-readable copy of the same tree kept in sync with that section).

`classify_failure` here is a cheap, deterministic PRE-classification layer
that runs before the LLM critic call: for the failure categories that have
unambiguous, mechanically-detectable signatures (a hard timeout string, a
browser-crash error, an HTTP 401/403, a URL that no longer matches the
domain the mission started on, a "no such element" tool error) there is no
need to spend an LLM call to figure out what already-parsed `ObservedState`
+ the raw error string make obvious. It never fully replaces the LLM
critic (`WRONG_PLAN`/`MISSING_INPUT` genuinely require judgment about intent,
not just pattern matching) — it only supplies a `FAILURE_TYPE` hint that is
passed into the critic prompt so the LLM has to reason less about the
mechanical part of the classification and can spend its attention on
picking the revised strategy.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Dict, Optional
from urllib.parse import urlparse

from src.services.observer import ObservedState

logger = logging.getLogger(__name__)

# Per-domain counters tracking how often `classify_failure` finds a
# mechanical match vs. falls through to `None` (generic LLM critic path).
# In-memory only — this is a lightweight operational signal (see the
# "Extending the tree" section of `Backend/src/agents/specs/recovery.md`),
# not a persisted metric. It resets on process restart, which is fine: the
# question it answers ("is a NEW site pattern showing up right now")
# is inherently about the current run/deployment, not long-term history.
_UNKNOWN_DOMAIN = "unknown"
_classification_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"classified": 0, "unclassified": 0})


def _extract_domain(error_msg: str, observed: Optional[ObservedState]) -> str:
    """Best-effort domain extraction so fallback-rate can be broken down by
    site. Prefers the parsed `ObservedState.url` (most reliable); falls back
    to scanning the raw error text for a URL; defaults to "unknown" when
    neither yields a host (e.g. a bare tool error with no page context)."""
    candidates = []
    if observed is not None and observed.url:
        candidates.append(observed.url)
    url_match = re.search(r"https?://[^\s\"'>)]+", str(error_msg or ""))
    if url_match:
        candidates.append(url_match.group(0))

    for candidate in candidates:
        try:
            host = urlparse(candidate).netloc
        except ValueError:
            continue
        if host:
            return host.lower()
    return _UNKNOWN_DOMAIN


def _record_classification(domain: str, matched: bool) -> None:
    stats = _classification_stats[domain]
    if matched:
        stats["classified"] += 1
    else:
        stats["unclassified"] += 1
        logger.info(
            "recovery.classify_failure: no mechanical branch matched for domain=%s "
            "(falls through to generic LLM critic) — unclassified=%d/%d for this domain "
            "this run. See 'Extending the tree' in Backend/src/agents/specs/recovery.md "
            "if this keeps recurring for the same domain/pattern.",
            domain, stats["unclassified"], stats["unclassified"] + stats["classified"],
        )


def get_classification_stats() -> Dict[str, Dict[str, int]]:
    """Snapshot of per-domain classify/fall-through counts accumulated this
    process's lifetime. Useful for a debug endpoint or periodic log summary;
    not persisted across restarts."""
    return {domain: dict(counts) for domain, counts in _classification_stats.items()}


def reset_classification_stats() -> None:
    """Clears the in-memory counters. Exists mainly for test isolation."""
    _classification_stats.clear()


# Ordered most-specific-first: the first matching branch wins.
FAILURE_TYPES = (
    "BROWSER_CRASH",
    "SESSION_EXPIRED",
    "TIMEOUT",
    "PERMISSION_DENIED",
    "UNEXPECTED_REDIRECT",
    "MISSING_ELEMENT",
    "WRONG_PAGE",
    "TRANSIENT_BLOCK",
    "MISSING_INPUT",
    "SITE_UNSUPPORTED",
    "WRONG_PLAN",
)

_CRASH_PATTERNS = [
    r"\btarget (?:page|context|browser)\b.{0,60}\bclosed\b",
    r"\bbrowser (?:has )?(?:crashed|disconnected)\b",
    r"\bconnection closed\b", r"\bwebsocket.*closed\b",
    r"\bexecution context was destroyed\b",
]
_SESSION_EXPIRED_PATTERNS = [
    r"\bsession (?:has )?expired\b", r"\bsession (?:is )?(?:no longer )?valid\b.*\bfalse\b",
    r"\bplease log ?in again\b", r"\byou(?:'ve| have) been (?:logged|signed) out\b",
    r"\bre-?authenticate\b",
]
_TIMEOUT_PATTERNS = [
    r"\btimed out\b", r"\btimeout\b", r"\bexceeded.*(?:ms|seconds|s)\b.*wait",
]
_PERMISSION_PATTERNS = [
    r"\bpermission denied\b", r"\baccess denied\b", r"\b401\b", r"\b403\b",
    r"\bforbidden\b", r"\bunauthorized\b", r"\byou (?:don't|do not) have (?:permission|access)\b",
]
_MISSING_ELEMENT_PATTERNS = [
    r"\bno such element\b", r"\belement not found\b", r"\bcould not find\b.*\b(?:element|selector|button|field)\b",
    r"\bselector.*not (?:found|match)\b",
]
_WRONG_PAGE_PATTERNS = [
    r"\b404\b", r"\bpage not found\b", r"\bthis page (?:isn't|is not) available\b",
    r"\bunexpected page\b",
]
_TRANSIENT_PATTERNS = [
    r"\bcaptcha\b", r"\brate limit\b", r"\btoo many requests\b", r"\b429\b",
    r"\bbot detected\b", r"\bare you a robot\b", r"\bplease slow down\b",
]


def _any_match(text: str, patterns: list) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_failure(error_msg: str, observed: Optional[ObservedState] = None) -> Optional[str]:
    """Return one of `FAILURE_TYPES`, or `None` when no mechanical signature
    matches and the LLM critic should classify from scratch (typically
    `WRONG_PLAN` or a genuinely ambiguous `MISSING_INPUT` case).

    This is intentionally a hint, not a verdict — callers pass the result
    into the critic prompt as an additional data point; the critic's own
    `FAILURE_TYPE:` output line remains authoritative.
    """
    text = str(error_msg or "")
    if observed is not None:
        text = f"{text}\n{observed.raw_text}"

    domain = _extract_domain(error_msg, observed)
    result: Optional[str] = None
    if _any_match(text, _CRASH_PATTERNS):
        result = "BROWSER_CRASH"
    elif _any_match(text, _SESSION_EXPIRED_PATTERNS):
        result = "SESSION_EXPIRED"
    elif _any_match(text, _TIMEOUT_PATTERNS):
        result = "TIMEOUT"
    elif _any_match(text, _PERMISSION_PATTERNS):
        result = "PERMISSION_DENIED"
    elif observed is not None and observed.url and _any_match(text, _WRONG_PAGE_PATTERNS):
        result = "WRONG_PAGE"
    elif _any_match(text, _MISSING_ELEMENT_PATTERNS):
        result = "MISSING_ELEMENT"
    elif _any_match(text, _WRONG_PAGE_PATTERNS):
        result = "WRONG_PAGE"
    elif _any_match(text, _TRANSIENT_PATTERNS):
        result = "TRANSIENT_BLOCK"

    _record_classification(domain, matched=result is not None)
    return result


def format_hint(failure_type: Optional[str]) -> str:
    """Formats the pre-classification as a short line to prepend to the
    critic prompt. Returns an empty string when there is no confident hint
    (`classify_failure` returned `None`) so the critic prompt is unchanged
    for the ambiguous cases that genuinely need full LLM judgment."""
    if not failure_type:
        return ""
    return (
        f"DETERMINISTIC PRE-CLASSIFICATION HINT: {failure_type} "
        f"(pattern-matched from the error text/observed state — confirm or override this in your FAILURE_TYPE line).\n\n"
    )
