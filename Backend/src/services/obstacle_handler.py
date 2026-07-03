"""
Generic obstacle-handling framework.

Provides one shared detect -> pause/ask-or-retry -> resume -> remember shape
for mid-run blockers (CAPTCHA, OTP/verification codes, and future obstacle
types like cookie-consent walls), so each new obstacle type is a small,
contained addition instead of new plumbing.

How the two existing obstacle types use this shape:

- CAPTCHA (agent can attempt to self-solve): detected via `detect_obstacle`,
  looked up in procedural memory (`memory_service.get_captcha_skill`), and
  the agent tries the stored bypass steps. Outcome is evaluated on the next
  tool result via `Brain._evaluate_captcha_outcome`.

- OTP / verification code (only a human can resolve it): detected via
  `detect_obstacle` with `requires_human_input=True`, which makes the tool
  graph raise `ObstacleInputNeeded`. The run pauses, a NEEDS_INPUT-shaped
  form (`build_input_form`) is surfaced in-chat, and the run resumes with
  the submitted value once the user answers.

How to add a future obstacle type (e.g. a cookie-consent wall):
1. Add a `detect_<type>(text)` function with its recognition patterns.
2. Branch to it from `detect_obstacle()`, returning an `ObstacleMatch` with
   `requires_human_input=True` if only a human can resolve it, or `False` if
   the agent should attempt an automatic bypass like CAPTCHA.
3. If it requires human input, add a form-building branch to
   `build_input_form()`.
4. Memory is keyed off `ObstacleMatch.skill_name` ("{category}_{obstacle_type}"),
   the same procedural-skill naming CAPTCHA already uses — no schema change
   needed to remember it per site/flow.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


# ── CAPTCHA detector (canonical source — brain._detect_captcha wraps this) ──

def detect_captcha_type(observation_text: str) -> Optional[str]:
    """Return CAPTCHA type string if a known CAPTCHA signal is present, else None."""
    t = observation_text.lower()
    if 'recaptcha' in t or 'g-recaptcha' in t:
        if 'v3' in t or 'invisible' in t:
            return 'recaptcha_v3'
        return 'recaptcha_v2'
    if 'hcaptcha' in t or 'h-captcha' in t:
        return 'hcaptcha'
    if 'cf-turnstile' in t or ('cloudflare' in t and 'challenge' in t):
        return 'cloudflare_turnstile'
    if 'slider' in t and ('captcha' in t or 'drag' in t or 'verify' in t):
        return 'slider'
    if ('captcha' in t or 'verification code' in t) and (
        'type' in t or 'enter' in t or 'characters' in t
    ):
        return 'image_text'
    return None


# ── OTP / verification-code detector (first new obstacle type) ─────────────

_OTP_PATTERNS = [
    r"enter the (?:code|verification code|otp)\b",
    r"one[- ]time (?:password|code|pin)\b",
    r"\bverification code\b",
    r"\bone-time code\b",
    r"\botp\b",
    r"enter the \d{4,8}[- ]?digit code",
    r"check your (?:email|phone|inbox) for a (?:code|pin)",
    r"we(?:'ve| have)? (?:sent|texted|emailed) you a code",
    r"\bcode sent to\b",
    r"\bauthentication code\b",
    r"\bsecurity code\b.*(?:sent|emailed|texted)",
]


def detect_otp(observation_text: str) -> Optional[str]:
    """Return an OTP obstacle_type string if a verification-code prompt is
    present, else None.

    Callers should check `detect_captcha_type` first — some CAPTCHA copy also
    contains the phrase "verification code", and CAPTCHA takes priority since
    the agent can attempt to self-solve it instead of asking the user.
    """
    if detect_captcha_type(observation_text):
        return None
    t = observation_text.lower()
    for pattern in _OTP_PATTERNS:
        if re.search(pattern, t):
            return "email_or_sms_code"
    return None


@dataclass
class ObstacleMatch:
    category: str               # "captcha" | "otp" | future obstacle categories
    obstacle_type: str            # e.g. "recaptcha_v2", "email_or_sms_code"
    requires_human_input: bool     # True => only a human can resolve it (OTP)

    @property
    def skill_name(self) -> str:
        """Procedural-memory key — same naming scheme CAPTCHA already uses."""
        return f"{self.category}_{self.obstacle_type}"


def detect_obstacle(observation_text: str) -> Optional[ObstacleMatch]:
    """Single entry point: scan a tool observation for any known obstacle.

    CAPTCHA is checked first (agent can self-solve it), then OTP (requires a
    human). Add a new `detect_*` function + branch here to plug in a future
    obstacle type — no other code needs to change.
    """
    if not observation_text:
        return None
    text = str(observation_text)

    captcha_type = detect_captcha_type(text)
    if captcha_type:
        return ObstacleMatch(category="captcha", obstacle_type=captcha_type, requires_human_input=False)

    otp_type = detect_otp(text)
    if otp_type:
        return ObstacleMatch(category="otp", obstacle_type=otp_type, requires_human_input=True)

    return None


class ObstacleInputNeeded(Exception):
    """Raised mid-run when an obstacle can only be resolved by a human (e.g.
    OTP). Caught around the tool-execution graph to pause the run and surface
    a NEEDS_INPUT form instead of dying with a generic error."""

    def __init__(self, match: ObstacleMatch, site_domain: str):
        self.match = match
        self.site_domain = site_domain
        super().__init__(f"Obstacle '{match.skill_name}' on {site_domain} requires human input")


def build_input_form(match: ObstacleMatch, site_domain: str) -> Dict[str, Any]:
    """Build a NEEDS_INPUT-compatible form for an obstacle that requires a
    human to resolve. Reuses the exact same form schema the existing
    Input-Understanding NEEDS_INPUT flow already renders in-chat, so no
    frontend changes are needed to surface a new obstacle type here."""
    if match.category == "otp":
        return {
            "title": "Verification Code Required",
            "description": (
                f"{site_domain} is asking for a verification code sent to your email or "
                "phone to continue. Please check your inbox/messages and enter the code below."
            ),
            "sections": [
                {
                    "section_title": None,
                    "fields": [
                        {
                            "id": "otp_code",
                            "label": "Verification Code",
                            "type": "text",
                            "placeholder": "e.g. 123456",
                            "required": True,
                            "options": None,
                            "note": "Used once to continue this task and never stored.",
                        }
                    ],
                }
            ],
            "security_note": "Your verification code is used once to continue this task and is never saved.",
            "obstacle_type": match.obstacle_type,
            "obstacle_category": match.category,
        }

    # Future human-input obstacle types (e.g. a forced re-login) plug in here.
    return {
        "title": "Input Required",
        "description": f"{site_domain} requires additional input to continue.",
        "sections": [],
    }
