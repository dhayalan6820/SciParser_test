"""
Structured Observer step.

Produces one `ObservedState` object per tool observation so that obstacle
detection, per-action verification, and recovery classification all read
flags off a single parsed representation of the page state instead of each
running its own ad-hoc regex pass over the raw observation text.

This does not replace the underlying pattern-matching in
`src.services.obstacle_handler` (that remains the canonical source of
CAPTCHA/OTP detection logic) — it centralizes WHEN that matching runs (once,
per tool result) and adds the additional structural flags (loading/modal/
login/error) the reference architecture calls for, so downstream code reads
`ObservedState` fields rather than re-scanning `str(observation)` itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.services.obstacle_handler import detect_captcha_type, detect_otp

_LOADING_PATTERNS = [
    r"\bloading\b", r"\bplease wait\b", r"\bspinner\b", r"\bfetching\b",
    r"\bpage is still loading\b",
]
_MODAL_PATTERNS = [
    r"\bmodal\b", r"\bdialog\b", r"\bpop[- ]?up\b", r"\boverlay\b",
    r"\bcookie (?:consent|banner|notice)\b", r"\baccept (?:all )?cookies\b",
]
_LOGIN_PATTERNS = [
    r"\bsign[- ]?in\b", r"\blog[- ]?in\b", r"\busername\b",
    r"\bpassword\b.{0,40}\bfield\b", r"\benter your password\b",
]
# Deliberately narrower than a bare "error" substring match — avoids
# false-positives on copy that merely mentions the word (e.g. "no errors
# found", "error-free checkout"). Mirrors the "Error" convention brain.py
# already uses to derive tool-call SUCCESS/FAILED status.
_ERROR_PATTERNS = [
    r"^error\b", r"\berror:", r"\berror executing tool\b", r"\bfailed to\b",
    r"\bexception\b", r"\bnot found\b", r"\bunreachable\b",
    r"\btimed out\b", r"\btimeout\b", r"\bpermission denied\b",
    r"\baccess denied\b", r"\b403 forbidden\b", r"\b404\b",
    r"\bsession expired\b", r"\bsession has expired\b",
]

_URL_RE = re.compile(r"(?:current[_ ]?url|url)\s*[:=]\s*(\S+)", re.IGNORECASE)


@dataclass
class ObservedState:
    """Structured snapshot of one tool observation."""

    raw_text: str
    url: Optional[str] = None
    is_loading: bool = False
    has_modal: bool = False
    has_login_form: bool = False
    has_error: bool = False
    error_signals: List[str] = field(default_factory=list)
    captcha_type: Optional[str] = None
    otp_type: Optional[str] = None
    elements_summary: str = ""

    @property
    def is_blocked(self) -> bool:
        """True when the page shows a blocker the agent cannot just click through."""
        return bool(self.captcha_type or self.otp_type or self.has_modal)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "is_loading": self.is_loading,
            "has_modal": self.has_modal,
            "has_login_form": self.has_login_form,
            "has_error": self.has_error,
            "error_signals": self.error_signals,
            "captcha_type": self.captcha_type,
            "otp_type": self.otp_type,
            "is_blocked": self.is_blocked,
        }


def observe(observation_text: str) -> ObservedState:
    """Parse a raw tool observation into a structured `ObservedState`.

    Called once per tool result in `_call_tool` — every other detector
    (CAPTCHA, OTP, address/calendar/login/booking agents, recovery
    classification) should prefer reading flags off the returned state
    instead of re-running regex over `observation_text` themselves.
    """
    text = str(observation_text or "")
    t = text.lower()

    url_match = _URL_RE.search(text)
    url = url_match.group(1).strip().rstrip(".,)") if url_match else None

    error_signals = [p for p in _ERROR_PATTERNS if re.search(p, t, re.MULTILINE)]

    return ObservedState(
        raw_text=text,
        url=url,
        is_loading=any(re.search(p, t) for p in _LOADING_PATTERNS),
        has_modal=any(re.search(p, t) for p in _MODAL_PATTERNS),
        has_login_form=any(re.search(p, t) for p in _LOGIN_PATTERNS),
        has_error=bool(error_signals),
        error_signals=error_signals,
        captcha_type=detect_captcha_type(text),
        otp_type=detect_otp(text),
        elements_summary=text[:300],
    )
