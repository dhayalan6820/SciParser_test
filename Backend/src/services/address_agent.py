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
#
# These patterns were originally written against an assumed, generic
# accessibility-tree/bullet-list shape and were NEVER checked against what
# the two browser engines actually wired into this repo (browser_use_bridge.py)
# really emit. Verified 2026-07-03 by:
#   1. Reading the production serializer source
#      (browser_use.dom.serializer.serializer.DOMTreeSerializer /
#      _build_attributes_string) used for the Chrome/CDP path — it renders
#      "[backend_node_id]<tag attr=value ... />" with UNQUOTED attribute
#      values, and puts each element's own visible text on a SEPARATE line
#      below it (not inline, not bulleted, not quoted).
#   2. Reading `_CAMOUFOX_DOM_JS` in browser_use_bridge.py — the JS injected
#      for the Firefox/camoufox engine, which is `config.BROWSER_ENGINE`'s
#      DEFAULT ("camoufox"). It NEVER reads/emits `role`/ARIA attributes at
#      all, and collapses every interactive element (including
#      `role="option"` suggestion rows, which still match its `[tabindex]`
#      CSS selector) to a single line: "  [N] <tag>[type] visible text".
#   3. Loading a live, real ARIA-compliant address/lookup-style autocomplete
#      widget (github.com/alphagov/accessible-autocomplete — the same
#      role=combobox/listbox/option pattern used by many production address
#      lookups, incl. GOV.UK's address-lookup pattern) in headless Chromium
#      and inspecting its actual rendered markup:
#        <ul role="listbox">
#          <li role="option" aria-selected="false" tabindex="-1">United States</li>
#          ...
#        </ul>
#      i.e. plain option text with NO surrounding quotes/bullets/numbering.
#
# The original "-"/"1." bullet-list assumption matches NEITHER real engine's
# output, which means the detector could silently never fire in production
# (see task: "Confirm address-suggestion detection matches real site markup").

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

    Always requires an address-field signal (so we never fire on an
    unrelated dropdown, e.g. a country-code select). On top of that, EITHER
    of the following counts as evidence a dropdown is actually open:
      - an explicit ARIA/keyword hint (`role=listbox`, "suggestions", ...) —
        this is all the Chrome/browser-use CDP path ever needs, since its
        serializer preserves `role` attributes.
      - >=2 address-shaped candidate lines extracted from the raw text —
        needed because the default camoufox/Firefox engine strips ARIA
        `role` attributes entirely (see module-level note above), so a real
        address-suggestion dropdown on that engine never contains any of the
        keyword hints even though it is genuinely open.
    """
    if not observation_text:
        return False
    t = str(observation_text).lower()
    has_address_field = any(re.search(p, t) for p in _ADDRESS_FIELD_HINTS)
    if not has_address_field:
        return False
    has_dropdown_keyword = any(re.search(p, t) for p in _AUTOCOMPLETE_HINTS)
    if has_dropdown_keyword:
        return True
    return len(extract_suggestions(observation_text)) >= 2


# ── Suggestion extraction ───────────────────────────────────────────────────

# Chrome/browser-use CDP path: DOMTreeSerializer renders an option row as
# "[id]<li role=option ... />" (unquoted attrs) with its visible text on the
# NEXT line (any indentation), e.g.:
#   [43]<li id=autocomplete-default__option--0 role=option selected=false />
#   123 Main St, Springfield, IL 62704
_OPTION_TAG_LINE_RE = re.compile(
    r'''\[\d+\][^\n]*?\brole=[\"']?option\b[^\n]*/?>\s*\n\s*([^\n]{2,120})''',
    re.IGNORECASE,
)

# Firefox/camoufox engine (the default per config.BROWSER_ENGINE): every
# interactive element — including suggestion rows, since role is stripped —
# collapses to a single line "  [N] <tag>[type] visible text". Restricted to
# tags real suggestion rows are actually rendered as (list items, generic
# containers, anchors, native <option>s) so we don't also sweep up unrelated
# <button>/<input> controls on the same page.
_CAMOUFOX_ELEMENT_LINE_RE = re.compile(
    r'''\[\d+\]\s*<(?:li|div|a|option|span)>(?:\[[^\]\n]*\])?\s*([^\n]{4,120}?)\s*(?:\xe2\x86\x92[^\n]*)?$''',
    re.MULTILINE | re.IGNORECASE,
)

# Best-effort legacy fallback for bullet/numbered-list-style tool output,
# e.g.:
#   - option "123 Main St, Springfield, IL 62704"
#   1. 123 Main St, Springfield, IL 62704
# Not confirmed against either real engine wired into this repo today, but
# kept in case another MCP browser tool formats observations this way.
_SUGGESTION_LINE_RE = re.compile(
    r'''(?:^|\n)\s*(?:[-*]|\d+[.)])\s*(?:option\s*)?["']?([^"'\n]{6,120}?)["']?\s*(?=\n|$)''',
    re.IGNORECASE,
)


def _looks_like_address_candidate(text: str) -> bool:
    """Cheap filter so headings / unrelated element text isn't mistaken for
    an address suggestion: must contain at least one digit (house number or
    postal code) and some alphabetic content (street/city name)."""
    return bool(re.search(r"\d", text) and re.search(r"[A-Za-z]", text))


def extract_suggestions(observation_text: str) -> List[str]:
    """Pull candidate suggestion strings out of an observation.

    Tries, in order, the real Chrome/browser-use option-row shape, the real
    (default) camoufox single-line element shape, and a legacy bullet/list
    fallback — see the format notes above `_OPTION_TAG_LINE_RE`. Best-effort:
    a candidate must look address-like (digit + alphabetic content) so
    headings / unrelated lines are skipped.
    """
    if not observation_text:
        return []
    text = str(observation_text)
    candidates: List[str] = []
    for pattern in (_OPTION_TAG_LINE_RE, _CAMOUFOX_ELEMENT_LINE_RE, _SUGGESTION_LINE_RE):
        for match in pattern.finditer(text):
            candidate = match.group(1).strip()
            if not candidate or not _looks_like_address_candidate(candidate):
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

# Matches an address-labelled textbox/field's current value in common
# accessibility-tree / DOM-dump observation shapes, e.g.:
#   textbox "Address" value="123 Main St, Springfield, 62704"
#   Address field: 123 Main St, Springfield, 62704
#   input[name=address] value="123 Main St"
# Best-effort by design (see Backend/src/services/address_agent.py module
# docstring and follow-up task to calibrate against real site markup).
_ADDRESS_FIELD_VALUE_RE = re.compile(
    r'''(?:address|street)[^\n]{0,40}?(?:value|:)\s*[:=]?\s*["']([^"'\n]{4,160})["']''',
    re.IGNORECASE,
)
_ADDRESS_FIELD_VALUE_FALLBACK_RE = re.compile(
    r'''(?:address|street)\s*(?:field)?\s*:\s*([^\n]{4,160})''',
    re.IGNORECASE,
)
# Real Chrome/browser-use CDP path: a whole element (incl. its `value=`
# attribute) renders unquoted on ONE line, e.g.:
#   [12]<input id=shipping-address name=address role=combobox value=123 Main St, Springfield, 62704 />
# `value=` isn't the last attribute in browser-use's include-attributes
# ordering, so the capture stops at the next `key=` token (or the closing
# `/>`) rather than swallowing trailing attributes.
_ADDRESS_FIELD_VALUE_UNQUOTED_RE = re.compile(
    r'''<[a-zA-Z][\w:-]*\b[^\n]*?(?:address|street)[^\n]*?\bvalue=(.+?)(?=\s+[a-zA-Z][\w-]*=|\s*/>|\s*$)''',
    re.IGNORECASE,
)


def extract_address_field_value(observation_text: str) -> Optional[str]:
    """Best-effort extraction of the CURRENT VALUE of the address input field
    from a tool observation, so verification checks the specific field the
    agent just filled in rather than the entire page/DOM text blob (which
    could coincidentally contain the suggestion elsewhere, e.g. in a
    breadcrumb, another field, or leftover dropdown markup).

    Returns None when no address-field value can be confidently located —
    callers must treat that as "cannot verify" rather than falling back to
    scanning the whole observation.
    """
    if not observation_text:
        return None
    text = str(observation_text)
    match = _ADDRESS_FIELD_VALUE_RE.search(text)
    if match:
        return match.group(1).strip()
    match = _ADDRESS_FIELD_VALUE_UNQUOTED_RE.search(text)
    if match:
        return match.group(1).strip()
    match = _ADDRESS_FIELD_VALUE_FALLBACK_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def verify_selected_value(field_value: Optional[str], chosen_suggestion: str) -> bool:
    """True if the address field's own current value (NOT the whole page/DOM
    text) actually reflects the suggestion that was chosen (fuzzy — a field
    may reformat casing/spacing).

    `field_value` must be the extracted value of the specific address input
    (see `extract_address_field_value`), not an entire observation blob —
    otherwise the suggestion text could coincidentally appear elsewhere on
    the page and produce a false positive.
    """
    if not field_value or not chosen_suggestion:
        return False
    return _token_overlap_ratio(chosen_suggestion, field_value) >= HIGH_CONFIDENCE_THRESHOLD


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
    spec_injected: bool = False


# ── Orchestration: the two decision points Brain's tool-loop calls into ─────
#
# These wrap the pure detect/score/verify functions above into the two
# stateful decisions the tool-loop needs each turn, INCLUDING the escalation
# (raise ObstacleInputNeeded) branch, so that "does this eventually pause the
# run and ask the user?" is unit-testable here instead of only reachable
# through Brain's nested, non-importable `_call_tool` closure.

def handle_address_dropdown_observation(
    observation_text: str,
    requested_address: Dict[str, str],
    state: AddressAutocompleteState,
    task_domain: str,
    spec_guidance: Optional[str] = None,
) -> str:
    """Call when `detect_address_autocomplete_context` is True for the current
    observation. Extracts + scores suggestions and either:
      - injects high-confidence auto-select guidance, or
      - injects one-time retry guidance and consumes the retry budget, or
      - raises `ObstacleInputNeeded(category="address",
        obstacle_type="low_confidence_selection")` once the retry budget is
        exhausted, so the run pauses via the existing OTP-style flow.

    Mutates `state` in place. Returns the (possibly guidance-augmented)
    observation text.
    """
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if spec_guidance and not state.spec_injected:
        text += spec_guidance
        state.spec_injected = True

    suggestions = extract_suggestions(text)
    if not suggestions:
        return text

    scored = score_suggestions(suggestions, requested_address)
    top_choice, top_score = scored[0]
    if top_score >= HIGH_CONFIDENCE_THRESHOLD:
        text += build_address_guidance(top_choice, top_score, scored)
        state.pending_selection = top_choice
        state.candidates = scored
    elif state.retries < MAX_RETRIES:
        text += build_address_retry_guidance(requested_address, scored)
        state.retries += 1
        state.candidates = scored
    else:
        raise ObstacleInputNeeded(
            ObstacleMatch(
                category="address",
                obstacle_type="low_confidence_selection",
                requires_human_input=True,
                candidates=[s for s, _ in scored[:5]],
            ),
            task_domain,
        )
    return text


def handle_address_verification_observation(
    observation_text: str,
    state: AddressAutocompleteState,
    task_domain: str,
) -> str:
    """Call on the turn after an auto-selected suggestion's dropdown has
    closed (`state.pending_selection` is set but the dropdown is no longer
    open). Extracts the address field's OWN value and verifies it reflects
    the selection; either clears `pending_selection`, injects a one-time
    retry note, or raises `ObstacleInputNeeded(category="address",
    obstacle_type="verification_failed")` once the retry budget is exhausted.

    No-op (returns the text unchanged) if there is nothing pending to verify.
    """
    from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch

    text = str(observation_text)
    if not state.pending_selection:
        return text

    field_value = extract_address_field_value(text)
    verified = verify_selected_value(field_value, state.pending_selection)
    if verified:
        state.pending_selection = None
    elif state.retries < MAX_RETRIES:
        text += (
            "\n\n[ADDRESS_VERIFICATION_FAILED]\n"
            f"The field does not appear to reflect the selected suggestion "
            f"\"{state.pending_selection}\". Re-open the address field, "
            "retype it, and re-select the correct suggestion from the dropdown."
        )
        state.retries += 1
        state.pending_selection = None
    else:
        raise ObstacleInputNeeded(
            ObstacleMatch(
                category="address",
                obstacle_type="verification_failed",
                requires_human_input=True,
                candidates=[s for s, _ in state.candidates[:5]],
            ),
            task_domain,
        )
    return text
