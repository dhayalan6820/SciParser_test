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

import re
from typing import Optional

from src.services.observer import ObservedState

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

    if _any_match(text, _CRASH_PATTERNS):
        return "BROWSER_CRASH"
    if _any_match(text, _SESSION_EXPIRED_PATTERNS):
        return "SESSION_EXPIRED"
    if _any_match(text, _TIMEOUT_PATTERNS):
        return "TIMEOUT"
    if _any_match(text, _PERMISSION_PATTERNS):
        return "PERMISSION_DENIED"
    if observed is not None and observed.url and _any_match(text, _WRONG_PAGE_PATTERNS):
        return "WRONG_PAGE"
    if _any_match(text, _MISSING_ELEMENT_PATTERNS):
        return "MISSING_ELEMENT"
    if _any_match(text, _WRONG_PAGE_PATTERNS):
        return "WRONG_PAGE"
    if _any_match(text, _TRANSIENT_PATTERNS):
        return "TRANSIENT_BLOCK"
    return None


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
