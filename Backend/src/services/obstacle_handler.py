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
    if 'captcha' in t and ('type' in t or 'enter' in t or 'characters' in t):
        return 'image_text'
    return None


# ── OTP / verification-code detector (first new obstacle type) ─────────────

_OTP_PATTERNS = [
    r"enter the (?:code|verification code|otp)\b",
    r"one[- ]time (?:password|code|pin)\b",
    r"\bone-time code\b",
    r"enter the \d{4,8}[- ]?digit code",
    r"check your (?:email|phone|inbox) for a (?:code|pin)",
    r"we(?:'ve| have)? (?:sent|texted|emailed) you a (?:code|pin)",
    r"\bcode sent to\b",
    r"\bauthentication code\b.{0,40}(?:enter|required|below|to continue|to proceed)",
    # These three are the "weak" signals below — a bare mention of
    # "verification code" / "otp" / "security code" anywhere on a page (a
    # help article, footer disclaimer, or an unrelated newsletter/SMS-signup
    # banner) is NOT evidence the current step is actually blocked. Only
    # treat them as a real obstacle when they appear alongside an imperative
    # cue (enter/type/confirm/provide) or an explicit "required to continue"
    # framing, i.e. the page is actually asking THIS action for THIS step.
    r"(?:enter|type|input|confirm|provide).{0,30}\bverification code\b",
    r"\bverification code\b.{0,40}(?:required|below|to continue|to proceed|has been sent|is required)",
    r"(?:enter|type|input|confirm|provide).{0,30}\botp\b",
    r"\botp\b.{0,40}(?:required|below|to continue|to proceed|has been sent)",
    r"\bsecurity code\b.{0,40}(?:sent|emailed|texted)",
]

# Mentions of "code"/"verification" that are almost never an actual
# login/identity blocker — checkout discounts, generic zip/area codes, or
# marketing opt-ins that just describe a future/optional text message. If any
# of these appear, treat the page as NOT presenting a real OTP obstacle even
# if one of the (weaker) patterns above also matched nearby text.
_OTP_FALSE_POSITIVE_CONTEXT = [
    r"promo code", r"discount code", r"coupon code", r"referral code", r"gift code",
    r"\bzip code\b", r"\bpostal code\b", r"\barea code\b", r"\bsource code\b", r"\bqr code\b",
    r"sign up for texts?", r"text alerts", r"sms alerts", r"\bsubscribe\b",
    r"\bnewsletter\b", r"join our (?:list|texting|sms)", r"opt[- ]?in",
    r"marketing (?:texts|messages|emails)",
]

# A verification-code prompt is only a real "human must type a code" blocker
# when it happens on a sign-in/authentication step or a payment/checkout
# step — those are the only two places a site legitimately needs to prove
# it's really you before letting the run continue. The same wording can also
# show up on unrelated steps (e.g. an address-verification/autocomplete
# widget) where the agent should NOT stop and interrupt the user. Require at
# least one of these context cues to appear alongside the OTP pattern.
_OTP_SIGNIN_CONTEXT = [
    r"\bsign[- ]?in\b", r"\blog[- ]?in\b", r"\blogin\b", r"\bpassword\b",
    r"\byour account\b", r"\btwo[- ]factor\b", r"\b2fa\b", r"\bmfa\b",
    r"\bauthenticat", r"\bidentity\b", r"\bverify your account\b",
]
_OTP_PAYMENT_CONTEXT = [
    r"\bpayment\b", r"\bcheckout\b", r"\bbilling\b", r"\bcard number\b",
    r"\bcvv\b", r"\bcharge\b", r"\bpurchase\b", r"\border total\b",
    r"\bplace your order\b", r"\btransaction\b", r"\bpay now\b", r"\bsubtotal\b",
]


def _detect_otp_context(t: str) -> Optional[str]:
    """Return 'signin' or 'payment' if the text shows one of those contexts, else None."""
    if any(re.search(p, t) for p in _OTP_SIGNIN_CONTEXT):
        return "signin"
    if any(re.search(p, t) for p in _OTP_PAYMENT_CONTEXT):
        return "payment"
    return None


def detect_otp(observation_text: str) -> Optional[str]:
    """Return an OTP obstacle_type string if a verification-code prompt is
    present, else None.

    Callers should check `detect_captcha_type` first — some CAPTCHA copy also
    contains the phrase "verification code", and CAPTCHA takes priority since
    the agent can attempt to self-solve it instead of asking the user.

    Only trigger when the page text actually indicates THIS step is blocked
    right now (an imperative "enter/type the code", "code sent to you", or an
    explicit "required to continue") — a bare mention of the words
    "verification code"/"otp" elsewhere on the page (help text, footer,
    unrelated newsletter/SMS opt-in banner) must never pause the run and ask
    the user for something that was never actually required.

    We also require the prompt to actually be tied to a sign-in/authentication
    step or a payment/checkout step (`_detect_otp_context`) — those are the
    only two places a real identity/security code is legitimately needed. The
    same wording appearing on an unrelated step (e.g. an address-check or
    autocomplete widget) is not treated as a human-input obstacle.
    """
    if detect_captcha_type(observation_text):
        return None
    t = observation_text.lower()
    if any(re.search(p, t) for p in _OTP_FALSE_POSITIVE_CONTEXT):
        return None
    if not _detect_otp_context(t):
        return None
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


def build_input_form(match: ObstacleMatch, site_domain: str, is_retry: bool = False) -> Dict[str, Any]:
    """Build a NEEDS_INPUT-compatible form for an obstacle that requires a
    human to resolve. Reuses the exact same form schema the existing
    Input-Understanding NEEDS_INPUT flow already renders in-chat, so no
    frontend changes are needed to surface a new obstacle type here.

    `is_retry=True` means we hit the SAME obstacle again after the user
    already answered once — the previous code didn't work (wrong, expired, or
    single-use and already consumed). We must never resubmit that stale value
    ourselves; instead we say so explicitly and ask for a brand new one."""
    if match.category == "otp":
        description = (
            (
                f"That verification code didn't work — it may have expired or already been used. "
                f"{site_domain} needs a **new** code. Please request/check for a fresh one and enter it below."
            )
            if is_retry
            else (
                f"{site_domain} is asking for a verification code sent to your email or "
                "phone to continue. Please check your inbox/messages and enter the code below."
            )
        )
        return {
            "title": "Verification Code Required",
            "description": description,
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
