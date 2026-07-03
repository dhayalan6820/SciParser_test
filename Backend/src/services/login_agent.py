"""
Login / Signup Interaction Agent — deterministic support layer around
credential and account-creation forms.

Same pattern as `address_agent.py`: the Browser agent still does the actual
clicking/typing; this module gives it (and Brain's tool-loop) the
deterministic pieces a raw LLM should never be trusted to eyeball on its own:

  1. `detect_login_form_context` — recognizes, from a tool observation, that
     a login/signup form with credential fields is on screen right now.
  2. `extract_requested_credentials` / `has_requested_credentials` — pull the
     credential values the user actually supplied out of `confirmed_inputs`.
  3. `extract_form_fields` — parse the visible labeled input fields out of
     the observation text.
  4. `map_fields_to_credentials` — deterministically decide which visible
     field each known credential value belongs in (email vs username,
     password vs confirm-password), instead of leaving that judgment call to
     the LLM on a page with several look-alike fields.
  5. `detect_login_failure` — recognize an explicit rejection (wrong
     password, locked account, too many attempts) so the agent stops
     retrying with the same credentials it already tried.
  6. `build_login_field_guidance` — the text injected into the next turn's
     observation naming exactly which field gets which value.

Escalation to the user (credentials rejected — only a human can supply a
corrected value or decide how to proceed) reuses the generic obstacle
pause/resume framework in `obstacle_handler.py` (category="login"). This
module has ZERO dependency on LangGraph/Brain so the detection/mapping logic
can be unit-tested in isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Max automatic re-attempts (e.g. re-typing after a benign validation error)
# before treating a rejection as something only a human can resolve.
MAX_RETRIES = 1

_EMAIL_KEYS = ["email", "email_address", "login_email"]
_USERNAME_KEYS = ["username", "user_name", "login", "login_username", "handle"]
_PASSWORD_KEYS = ["password", "pass", "login_password"]
_CONFIRM_PASSWORD_KEYS = ["confirm_password", "password_confirmation", "confirm_pass", "repeat_password"]


def _first_present(confirmed_inputs: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for k in keys:
        val = confirmed_inputs.get(k)
        if isinstance(val, str) and val.strip():
            return val
    return None


def has_requested_credentials(confirmed_inputs: Optional[Dict[str, Any]]) -> bool:
    """True if `confirmed_inputs` contains anything resembling login/signup
    credentials (an identifier plus, usually, a password)."""
    if not confirmed_inputs:
        return False
    identifier = _first_present(confirmed_inputs, _EMAIL_KEYS + _USERNAME_KEYS)
    password = _first_present(confirmed_inputs, _PASSWORD_KEYS)
    return bool(identifier or password)


def extract_requested_credentials(confirmed_inputs: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Return the identifier/password values supplied for this task, keyed
    "email" | "username" | "password" | "confirm_password" (only keys that
    were actually present are included)."""
    if not confirmed_inputs:
        return {}
    result: Dict[str, str] = {}
    email = _first_present(confirmed_inputs, _EMAIL_KEYS)
    if email:
        result["email"] = email
    username = _first_present(confirmed_inputs, _USERNAME_KEYS)
    if username:
        result["username"] = username
    password = _first_present(confirmed_inputs, _PASSWORD_KEYS)
    if password:
        result["password"] = password
    confirm = _first_present(confirmed_inputs, _CONFIRM_PASSWORD_KEYS)
    if confirm:
        result["confirm_password"] = confirm
    return result


# ── Login/signup form context detection ─────────────────────────────────────

_FORM_WIDGET_HINTS = [
    r"\bsign[- ]?in\b", r"\blog[- ]?in\b", r"\blogin\b", r"type=[\"']?password",
    r"\bcreate (?:an )?account\b", r"\bsign[- ]?up\b", r"\bregister\b",
]
_FORM_FIELD_HINTS = [
    r"\bemail\b", r"\busername\b", r"\bpassword\b",
]


def detect_login_form_context(observation_text: str) -> bool:
    """True if the observation shows a login/signup form with credential
    fields. Requires BOTH a login/signup-widget signal AND a credential-field
    signal so we don't fire on unrelated password-mention text."""
    if not observation_text:
        return False
    t = str(observation_text).lower()
    has_widget = any(re.search(p, t) for p in _FORM_WIDGET_HINTS)
    has_field = any(re.search(p, t) for p in _FORM_FIELD_HINTS)
    return has_widget and has_field


# ── Field extraction ─────────────────────────────────────────────────────────

# Matches labeled textbox/input entries in common accessibility-tree / DOM
# dump observation shapes, e.g.:
#   textbox "Email"
#   textbox "Confirm Password"
#   input[type=password][name=password]
_FIELD_LABEL_RE = re.compile(
    r'''(?:textbox|input)\s+["']([^"'\n]{2,40})["']''',
    re.IGNORECASE,
)
_FIELD_ATTR_RE = re.compile(
    r'''input\[type=(password|email|text)\]\[name=([a-zA-Z0-9_\-]{2,40})\]''',
    re.IGNORECASE,
)


def extract_form_fields(observation_text: str) -> List[str]:
    """Pull candidate labeled-field strings out of an observation
    (accessibility-tree labels or input[type][name] attribute dumps)."""
    if not observation_text:
        return []
    text = str(observation_text)
    fields: List[str] = []
    for match in _FIELD_LABEL_RE.finditer(text):
        label = match.group(1).strip()
        if label and label not in fields:
            fields.append(label)
    for match in _FIELD_ATTR_RE.finditer(text):
        label = match.group(2).strip()
        if label and label not in fields:
            fields.append(label)
    return fields


def _classify_field(label: str) -> Optional[str]:
    """Best-effort classification of a visible field label into
    "email" | "username" | "password" | "confirm_password"."""
    t = label.lower()
    if re.search(r"\bconfirm\b|\brepeat\b|\bre-?enter\b", t) and "password" in t:
        return "confirm_password"
    if "password" in t or "pass" in t:
        return "password"
    if "email" in t or "e-mail" in t:
        return "email"
    if "username" in t or "user name" in t or "handle" in t or t.strip() in ("login", "user id"):
        return "username"
    return None


def map_fields_to_credentials(fields: List[str], credentials: Dict[str, str]) -> Dict[str, str]:
    """Map each classified field label to the credential value it should
    receive. Returns {field_label: value} for fields we're confident about —
    callers must NOT type into fields absent from this mapping's keys."""
    mapping: Dict[str, str] = {}
    for label in fields:
        role = _classify_field(label)
        if not role:
            continue
        if role == "username" and "username" not in credentials and "email" in credentials:
            # Site only offers a "username"-labeled field but the task only
            # supplied an email — email is the most common identifier for it.
            mapping[label] = credentials["email"]
        elif role in credentials:
            mapping[label] = credentials[role]
    return mapping


# ── Failure detection (only a human can supply a corrected value) ──────────

_FAILURE_PATTERNS: Dict[str, List[str]] = {
    "invalid_credentials": [
        r"incorrect (?:email|username|password)",
        r"invalid (?:email|username|password|credentials)",
        r"(?:email|username|password) (?:is|was) incorrect",
        r"we don'?t recognize (?:that|this) (?:email|username|account)",
        r"wrong password",
        r"login failed",
        r"sign[- ]?in failed",
    ],
    "account_locked": [
        r"account (?:has been |is )?locked",
        r"account (?:has been |is )?(?:suspended|disabled)",
        r"too many failed (?:attempts|login attempts)",
        r"temporarily (?:locked|blocked)",
    ],
    "too_many_attempts": [
        r"too many attempts",
        r"please try again (?:later|in \d+)",
        r"rate limit",
    ],
    "unrecognized_device": [
        r"(?:new|unrecognized) device",
        r"verify it'?s you",
        r"confirm your identity",
    ],
}


def detect_login_failure(observation_text: str) -> Optional[str]:
    """Return a failure-type string ("invalid_credentials", "account_locked",
    "too_many_attempts", "unrecognized_device") if the page shows an explicit
    rejection of the credentials just submitted, else None.

    Deliberately narrow — generic help text mentioning "password" elsewhere
    on the page must never be mistaken for an active rejection banner."""
    if not observation_text:
        return None
    t = str(observation_text).lower()
    for failure_type, patterns in _FAILURE_PATTERNS.items():
        if any(re.search(p, t) for p in patterns):
            return failure_type
    return None


# ── Guidance injected into the tool-loop ─────────────────────────────────────

def build_login_field_guidance(mapping: Dict[str, str]) -> str:
    """Text appended to the tool observation naming exactly which visible
    field gets which credential role (never the raw secret value itself)."""
    if not mapping:
        return ""
    lines = []
    for label in mapping.keys():
        role = _classify_field(label) or "value"
        lines.append(f"  - Field \"{label}\" -> type the {role.replace('_', ' ')} for this task")
    return (
        "\n\n[LOGIN_FORM_DETECTED]\n"
        "Use exactly this field mapping (do not guess which field is which "
        "if there is more than one similar-looking field):\n"
        + "\n".join(lines)
        + "\n\nType only the values already provided for this task. Never invent, "
        "reuse a placeholder, or guess a credential that wasn't supplied."
    )


@dataclass
class LoginFormState:
    """Per-run tracking for the login-form escalation policy, mirroring
    `AddressAutocompleteState`."""
    retries: int = 0
    guidance_injected: bool = False
    spec_injected: bool = False


def handle_login_form_observation(
    observation_text: str,
    credentials: Dict[str, str],
    state: LoginFormState,
    task_domain: str,
    spec_guidance: Optional[str] = None,
) -> str:
    """Call when `detect_login_form_context` is True for the current
    observation. Injects the field-mapping guidance once per form
    appearance, and raises `ObstacleInputNeeded(category="login", ...)`
    immediately if the page shows an explicit credential-rejection banner
    (only a human can supply a corrected value — retrying blindly with the
    same rejected credentials would just loop)."""
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if spec_guidance and not state.spec_injected:
        text += spec_guidance
        state.spec_injected = True

    failure_type = detect_login_failure(text)
    if failure_type:
        if state.retries < MAX_RETRIES:
            state.retries += 1
            text += (
                f"\n\n[LOGIN_REJECTED: {failure_type}]\n"
                "The site rejected the last submission. Re-check that the correct "
                "field received the correct value (see field mapping below) before "
                "resubmitting. If this happens again, the run will pause and ask "
                "the user for a corrected value."
            )
        else:
            raise ObstacleInputNeeded(
                ObstacleMatch(
                    category="login",
                    obstacle_type=failure_type,
                    requires_human_input=True,
                ),
                task_domain,
            )

    if not state.guidance_injected:
        fields = extract_form_fields(text)
        mapping = map_fields_to_credentials(fields, credentials)
        guidance = build_login_field_guidance(mapping)
        if guidance:
            text += guidance
            state.guidance_injected = True

    return text
