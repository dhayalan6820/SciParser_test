"""
Address Interaction Agent — deterministic support layer around address
autocomplete widgets.

The Browser agent still does the actual clicking/typing; this module gives it
(and Brain's tool-loop) the deterministic pieces a raw LLM should never be
trusted to eyeball on its own:

  1. `detect_address_autocomplete_context` — recognizes, from a tool
     observation, that an address field with an open suggestion list is on
     screen right now.
  2. `extract_requested_address_components` / `has_requested_address` — pull
     the address the user actually asked for out of `confirmed_inputs`.
  3. `extract_suggestions` — parse the visible suggestion strings out of the
     observation text.
  4. `score_suggestion` / `score_suggestions` — numeric confidence that a
     given suggestion matches the requested address.
  5. `verify_selected_value` — after a selection, confirm the field's final
     value actually reflects the chosen suggestion.
  6. `build_address_guidance` — the text injected into the next turn's
     observation (mirrors the CAPTCHA-skill-injection pattern in brain.py).

Escalation to the user (when confidence is low or verification fails) reuses
the generic obstacle pause/resume framework in `obstacle_handler.py` — see
`AddressMatch` there. This module intentionally has ZERO dependency on
LangGraph/Brain so the scoring/detection logic can be unit-tested in
isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Suggestion auto-selected without asking the user only above this score.
HIGH_CONFIDENCE_THRESHOLD = 0.75

# Max automatic retries (re-typing/re-searching) before escalating to the user.
MAX_RETRIES = 1

# Keys in confirmed_inputs that plausibly hold address information. Checked
# in order — the first matching key that has a non-empty string value wins
# for "the raw address the user gave", in addition to the structured
# component keys below.
_ADDRESS_BLOB_KEYS = [
    "address", "full_address", "street_address", "shipping_address",
    "billing_address", "delivery_address", "home_address", "mailing_address",
]

_COMPONENT_KEYS: Dict[str, List[str]] = {
    "street": ["street", "street_name", "address_line1", "address1", "line1"],
    "house_number": ["house_number", "street_number", "unit", "apt", "apartment", "suite"],
    "city": ["city", "town", "locality"],
    "postal_code": ["postal_code", "zip", "zip_code", "zipcode", "postcode"],
    "country": ["country", "country_code"],
}


def has_requested_address(confirmed_inputs: Optional[Dict[str, Any]]) -> bool:
    """True if `confirmed_inputs` contains anything resembling a requested
    address (either a free-text blob or at least one structured component)."""
    if not confirmed_inputs:
        return False
    for key in _ADDRESS_BLOB_KEYS:
        val = confirmed_inputs.get(key)
        if isinstance(val, str) and val.strip():
            return True
    for keys in _COMPONENT_KEYS.values():
        for k in keys:
            val = confirmed_inputs.get(k)
            if isinstance(val, str) and val.strip():
                return True
    return False


def _parse_blob_address(blob: str) -> Dict[str, str]:
    """Best-effort split of a free-text address into components.

    e.g. "123 Main St Apt 4, Springfield, 62704, USA" ->
      {"house_number": "123", "street": "Main St", "unit": "Apt 4",
       "city": "Springfield", "postal_code": "62704", "country": "USA"}

    This is intentionally lightweight — the goal is a rough component split
    good enough for scoring, not a full postal-address parser.
    """
    components: Dict[str, str] = {}
    parts = [p.strip() for p in blob.split(",") if p.strip()]

    if parts:
        street_part = parts[0]
        m = re.match(r"^(\d+[A-Za-z]?)\s+(.*)$", street_part)
        if m:
            components["house_number"] = m.group(1)
            components["street"] = m.group(2)
        else:
            components["street"] = street_part

    remaining = parts[1:]
    for chunk in remaining:
        postal_match = re.search(r"\b\d{4,10}(-\d{3,4})?\b", chunk)
        if postal_match and "postal_code" not in components:
            components["postal_code"] = postal_match.group(0)
            leftover = (chunk[: postal_match.start()] + chunk[postal_match.end():]).strip()
            if leftover and "country" not in components:
                components["country"] = leftover
            continue
        if "city" not in components:
            components["city"] = chunk
        elif "country" not in components:
            components["country"] = chunk

    return components


def extract_requested_address_components(confirmed_inputs: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Return a normalized dict of address components the user asked for.

    Structured keys (street/city/postal_code/...) take priority; a free-text
    address blob is parsed only to fill in components not already given
    explicitly.
    """
    if not confirmed_inputs:
        return {}

    components: Dict[str, str] = {}
    for canonical, keys in _COMPONENT_KEYS.items():
        for k in keys:
            val = confirmed_inputs.get(k)
            if isinstance(val, str) and val.strip():
                components[canonical] = val.strip()
                break

    for blob_key in _ADDRESS_BLOB_KEYS:
        val = confirmed_inputs.get(blob_key)
        if isinstance(val, str) and val.strip():
            parsed = _parse_blob_address(val)
            for k, v in parsed.items():
                components.setdefault(k, v)
            break

    return components


# ── Address-autocomplete context detection ──────────────────────────────────

_AUTOCOMPLETE_HINTS = [
    r"role=[\"']?listbox",
    r"role=[\"']?option",
    r"\bautocomplete\b",
    r"\bsuggestion(s)?\b",
    r"\bdid you mean\b",
    r"\baddress lookup\b",
    r"\bselect an address\b",
    r"\bmatching addresses\b",
]

_ADDRESS_FIELD_HINTS = [
    r"\baddress\b", r"\bstreet\b", r"\bzip\b", r"\bpostal\b", r"\bpostcode\b",
    r"\bcity\b",
]


def detect_address_autocomplete_context(observation_text: str) -> bool:
    """True if the observation shows an address field with an open
    suggestion/autocomplete dropdown.

    Requires BOTH an autocomplete-dropdown signal AND an address-field signal
    so we don't fire on unrelated dropdowns (e.g. a country-code select).
    """
    if not observation_text:
        return False
    t = str(observation_text).lower()
    has_dropdown = any(re.search(p, t) for p in _AUTOCOMPLETE_HINTS)
    has_address_field = any(re.search(p, t) for p in _ADDRESS_FIELD_HINTS)
    return has_dropdown and has_address_field


# ── Suggestion extraction ───────────────────────────────────────────────────

# Matches list-style suggestion lines, e.g.:
#   - option "123 Main St, Springfield, IL 62704"
#   1. 123 Main St, Springfield, IL 62704
#   * 123 Main St, Springfield, IL 62704
_SUGGESTION_LINE_RE = re.compile(
    r'''(?:^|\n)\s*(?:[-*]|\d+[.)])\s*(?:option\s*)?["']?([^"'\n]{6,120}?)["']?\s*(?=\n|$)''',
    re.IGNORECASE,
)


def extract_suggestions(observation_text: str) -> List[str]:
    """Pull candidate suggestion strings out of an observation.

    Best-effort: looks for list-formatted lines that look like an address
    (contain at least one digit and some alphabetic content), so headings /
    unrelated bullet lines are skipped.
    """
    if not observation_text:
        return []
    text = str(observation_text)
    candidates: List[str] = []
    for match in _SUGGESTION_LINE_RE.finditer(text):
        candidate = match.group(1).strip()
        if not candidate:
            continue
        if not re.search(r"\d", candidate):
            continue
        if not re.search(r"[A-Za-z]", candidate):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


# ── Scoring ──────────────────────────────────────────────────────────────────

_COMPONENT_WEIGHTS = {
    "postal_code": 0.35,
    "street": 0.30,
    "house_number": 0.15,
    "city": 0.15,
    "country": 0.05,
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def _token_overlap_ratio(needle: str, haystack: str) -> float:
    """Fraction of needle's tokens that appear as substrings in haystack."""
    needle_tokens = [t for t in _normalize(needle).split() if t]
    if not needle_tokens:
        return 0.0
    haystack_norm = _normalize(haystack)
    hits = sum(1 for tok in needle_tokens if tok in haystack_norm)
    return hits / len(needle_tokens)


def score_suggestion(suggestion: str, requested: Dict[str, str]) -> float:
    """Confidence (0.0-1.0) that `suggestion` matches the requested address.

    Only components actually present in `requested` contribute to the score;
    their weights are re-normalized so a partial address (e.g. just street +
    postal code) can still reach full confidence.
    """
    if not suggestion or not requested:
        return 0.0

    present = {k: v for k, v in requested.items() if k in _COMPONENT_WEIGHTS and v}
    if not present:
        return 0.0

    total_weight = sum(_COMPONENT_WEIGHTS[k] for k in present)
    score = 0.0
    for component, value in present.items():
        weight = _COMPONENT_WEIGHTS[component] / total_weight
        if component == "postal_code":
            # Postal codes must match exactly (normalized) — a fuzzy partial
            # match on digits is not meaningful evidence.
            ratio = 1.0 if _normalize(value) and _normalize(value) in _normalize(suggestion) else 0.0
        else:
            ratio = _token_overlap_ratio(value, suggestion)
        score += weight * ratio

    return round(min(score, 1.0), 4)


def score_suggestions(
    suggestions: List[str], requested: Dict[str, str]
) -> List[Tuple[str, float]]:
    """Score every suggestion, returned sorted highest-confidence first."""
    scored = [(s, score_suggestion(s, requested)) for s in suggestions]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


# ── Post-selection verification ─────────────────────────────────────────────

def verify_selected_value(final_field_value: str, chosen_suggestion: str) -> bool:
    """True if the address field's final value actually reflects the
    suggestion that was chosen (fuzzy — a field may reformat casing/spacing).
    """
    if not final_field_value or not chosen_suggestion:
        return False
    return _token_overlap_ratio(chosen_suggestion, final_field_value) >= HIGH_CONFIDENCE_THRESHOLD


# ── Guidance injected into the tool-loop (mirrors CAPTCHA skill injection) ──

def build_address_guidance(
    top_choice: str, score: float, candidates: List[Tuple[str, float]]
) -> str:
    """Text appended to the tool observation instructing the agent exactly
    what to do next — auto-select the high-confidence suggestion."""
    ranked = "\n".join(f"  {i+1}. \"{s}\" (confidence {c:.2f})" for i, (s, c) in enumerate(candidates[:5]))
    return (
        "\n\n[ADDRESS_AUTOCOMPLETE_DETECTED]\n"
        f"Best-matching suggestion (confidence {score:.2f}, above the "
        f"{HIGH_CONFIDENCE_THRESHOLD:.2f} auto-select threshold):\n"
        f"  \"{top_choice}\"\n\n"
        f"All candidates considered:\n{ranked}\n\n"
        "Click exactly this suggestion from the dropdown (match its visible "
        "text). After clicking it, re-inspect the field's value and confirm "
        "it reflects this suggestion before moving on. Never invent or guess "
        "an address that is not one of the listed suggestions."
    )


def build_address_retry_guidance(requested: Dict[str, str], candidates: List[Tuple[str, float]]) -> str:
    """Text appended when confidence is too low but a retry budget remains —
    asks the agent to refine the typed input rather than guess a suggestion."""
    ranked = "\n".join(f"  - \"{s}\" (confidence {c:.2f})" for s, c in candidates[:5])
    requested_str = ", ".join(f"{k}={v}" for k, v in requested.items())
    return (
        "\n\n[ADDRESS_AUTOCOMPLETE_LOW_CONFIDENCE]\n"
        f"None of the visible suggestions confidently match the requested "
        f"address ({requested_str}):\n{ranked}\n\n"
        "Do NOT click any of these — none is a confident match. Clear the "
        "field and retype the address more precisely (e.g. include the full "
        "street number and postal code) to get better suggestions. This is "
        "your last automatic retry before the user will be asked to pick "
        "manually."
    )


@dataclass
class AddressAutocompleteState:
    """Per-run tracking for the address-autocomplete escalation policy,
    mirroring the shape of `_captcha_state` in brain.py."""
    retries: int = 0
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    pending_selection: Optional[str] = None
