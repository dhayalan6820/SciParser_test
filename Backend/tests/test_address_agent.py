"""Tests for the deterministic Address Interaction Agent support layer
(src/services/address_agent.py): context detection, requested-address
extraction, suggestion extraction/scoring, and post-selection verification.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest

from src.services import address_agent
from src.services.obstacle_handler import ObstacleInputNeeded, ObstacleMatch, build_input_form


# ── has_requested_address / extract_requested_address_components ───────────

def test_has_requested_address_true_for_blob_key():
    assert address_agent.has_requested_address({"address": "123 Main St"}) is True


def test_has_requested_address_true_for_structured_key():
    assert address_agent.has_requested_address({"street": "Main St", "zip": "62704"}) is True


def test_has_requested_address_false_when_absent():
    assert address_agent.has_requested_address({"destination": "Paris"}) is False
    assert address_agent.has_requested_address({}) is False
    assert address_agent.has_requested_address(None) is False


def test_extract_requested_address_components_structured_keys_take_priority():
    confirmed = {
        "street": "Main St",
        "city": "Springfield",
        "zip": "62704",
        "address": "999 Fake Ave, Nowhere, 00000",
    }
    components = address_agent.extract_requested_address_components(confirmed)
    assert components["street"] == "Main St"
    assert components["city"] == "Springfield"
    assert components["postal_code"] == "62704"


def test_extract_requested_address_components_parses_blob():
    confirmed = {"address": "123 Main St, Springfield, 62704, USA"}
    components = address_agent.extract_requested_address_components(confirmed)
    assert components["house_number"] == "123"
    assert "Main St" in components["street"]
    assert components["city"] == "Springfield"
    assert components["postal_code"] == "62704"
    assert components["country"] == "USA"


def test_extract_requested_address_components_empty_when_no_address():
    assert address_agent.extract_requested_address_components({}) == {}
    assert address_agent.extract_requested_address_components(None) == {}


# ── detect_address_autocomplete_context ─────────────────────────────────────

def test_detect_address_autocomplete_context_true_when_dropdown_and_address_present():
    text = 'Address field open. Suggestions: role="listbox" with matching addresses below.'
    assert address_agent.detect_address_autocomplete_context(text) is True


def test_detect_address_autocomplete_context_false_without_dropdown():
    text = "Address field: 123 Main St. Form submitted successfully."
    assert address_agent.detect_address_autocomplete_context(text) is False


def test_detect_address_autocomplete_context_false_without_address_field():
    text = "Country dropdown suggestions role=\"listbox\" open."
    assert address_agent.detect_address_autocomplete_context(text) is False


def test_detect_address_autocomplete_context_false_on_empty():
    assert address_agent.detect_address_autocomplete_context("") is False
    assert address_agent.detect_address_autocomplete_context(None) is False


# ── extract_suggestions ──────────────────────────────────────────────────────

def test_extract_suggestions_parses_list_lines():
    observation = (
        "Address suggestions dropdown open:\n"
        "- 123 Main St, Springfield, IL 62704\n"
        "- 456 Main St, Springfield, IL 62705\n"
        "- 789 Oak Ave, Shelbyville, IL 62565\n"
    )
    suggestions = address_agent.extract_suggestions(observation)
    assert len(suggestions) == 3
    assert "123 Main St, Springfield, IL 62704" in suggestions


def test_extract_suggestions_ignores_non_address_bullets():
    observation = "- Accept cookies\n- 123 Main St, Springfield, IL 62704\n- Close\n"
    suggestions = address_agent.extract_suggestions(observation)
    assert suggestions == ["123 Main St, Springfield, IL 62704"]


def test_extract_suggestions_returns_empty_for_no_matches():
    assert address_agent.extract_suggestions("Nothing relevant here.") == []
    assert address_agent.extract_suggestions("") == []


# ── Real-engine markup regression tests ─────────────────────────────────────
# These fixtures mirror the ACTUAL text the two browser engines wired into
# this repo (Backend/src/agents/browser_use_bridge.py) produce, verified
# 2026-07-03 against the browser_use library's serializer source and a live
# ARIA-compliant address-autocomplete widget (accessible-autocomplete /
# GOV.UK address-lookup pattern) rendered in headless Chromium — see the
# module docstring notes above `_AUTOCOMPLETE_HINTS` in address_agent.py.
# Neither shape is a bullet/numbered list, which is what the previous
# (unverified) regexes assumed.

# Firefox/camoufox engine — config.BROWSER_ENGINE's DEFAULT. _CAMOUFOX_DOM_JS
# never emits role/ARIA attributes, so every interactive element (including
# role="option" rows, which still match its `[tabindex]` selector) collapses
# to "  [N] <tag>[type] visible text".
_CAMOUFOX_DROPDOWN_OBSERVATION = (
    "URL: https://example.gov.uk/apply\n"
    "Title: Address lookup\n"
    "Engine: Firefox (camoufox)\n"
    "\n"
    "Interactive elements — use [index] with browser_click / browser_type:\n"
    "  [0] <input>[text] 123 Main St\n"
    "  [1] <li> 123 Main St, Springfield, IL 62704\n"
    "  [2] <li> 456 Main St, Springfield, IL 62705\n"
    "  [3] <li> 789 Oak Ave, Shelbyville, IL 62565\n"
)

# Chrome/browser-use CDP path — DOMTreeSerializer renders
# "[backend_node_id]<tag attr=value ... />" with UNQUOTED attributes, and the
# option's own visible text on the line immediately below it.
_BROWSER_USE_DROPDOWN_OBSERVATION = (
    "[10]<input id=shipping-address name=address role=combobox aria-expanded=true value=123 Main />\n"
    "\t[11]<ul role=listbox />\n"
    "\t\t[12]<li id=opt-0 role=option selected=false />\n"
    "\t\t123 Main St, Springfield, IL 62704\n"
    "\t\t[13]<li id=opt-1 role=option selected=false />\n"
    "\t\t456 Main St, Springfield, IL 62705\n"
)


def test_detect_address_autocomplete_context_true_for_camoufox_markup_without_role_hints():
    # Regression: camoufox never emits role=listbox/option, so detection must
    # not depend solely on those keyword hints.
    assert address_agent.detect_address_autocomplete_context(_CAMOUFOX_DROPDOWN_OBSERVATION) is True


def test_detect_address_autocomplete_context_true_for_browser_use_unquoted_markup():
    assert address_agent.detect_address_autocomplete_context(_BROWSER_USE_DROPDOWN_OBSERVATION) is True


def test_detect_address_autocomplete_context_false_for_camoufox_markup_with_single_result():
    # A single address-shaped line elsewhere on the page (e.g. a static
    # "Address: 123 Main St" summary row) must not be mistaken for an open
    # multi-option dropdown.
    text = (
        "Interactive elements — use [index] with browser_click / browser_type:\n"
        "  [0] <a> Terms and conditions\n"
        "  [1] <div> Address: 123 Main St, Springfield, IL 62704\n"
    )
    assert address_agent.detect_address_autocomplete_context(text) is False


def test_extract_suggestions_parses_camoufox_element_lines():
    suggestions = address_agent.extract_suggestions(_CAMOUFOX_DROPDOWN_OBSERVATION)
    assert suggestions == [
        "123 Main St, Springfield, IL 62704",
        "456 Main St, Springfield, IL 62705",
        "789 Oak Ave, Shelbyville, IL 62565",
    ]


def test_extract_suggestions_ignores_camoufox_input_field_line():
    # The address input's own (still-being-typed) value must not be treated
    # as one of the dropdown's suggestions.
    suggestions = address_agent.extract_suggestions(_CAMOUFOX_DROPDOWN_OBSERVATION)
    assert "123 Main St" not in suggestions


def test_extract_suggestions_parses_browser_use_option_tag_lines():
    suggestions = address_agent.extract_suggestions(_BROWSER_USE_DROPDOWN_OBSERVATION)
    assert suggestions == [
        "123 Main St, Springfield, IL 62704",
        "456 Main St, Springfield, IL 62705",
    ]


def test_extract_address_field_value_from_browser_use_unquoted_attribute():
    text = "[12]<input id=shipping-address name=address role=combobox value=123 Main St, Springfield, 62704 />"
    assert address_agent.extract_address_field_value(text) == "123 Main St, Springfield, 62704"


def test_handle_address_dropdown_high_confidence_on_camoufox_markup():
    # End-to-end: the exact function Brain's tool-loop calls into must fire
    # on real camoufox-shaped observation text, not just the old assumed
    # bullet-list fixtures.
    state = address_agent.AddressAutocompleteState()
    assert address_agent.detect_address_autocomplete_context(_CAMOUFOX_DROPDOWN_OBSERVATION) is True
    result = address_agent.handle_address_dropdown_observation(
        _CAMOUFOX_DROPDOWN_OBSERVATION,
        {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"},
        state,
        "example.gov.uk",
    )
    assert "[ADDRESS_AUTOCOMPLETE_DETECTED]" in result
    assert state.pending_selection == "123 Main St, Springfield, IL 62704"


# ── score_suggestion / score_suggestions ────────────────────────────────────

def test_score_suggestion_high_for_exact_match():
    requested = {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"}
    score = address_agent.score_suggestion("123 Main St, Springfield, IL 62704", requested)
    assert score >= address_agent.HIGH_CONFIDENCE_THRESHOLD


def test_score_suggestion_low_for_wrong_postal_code():
    requested = {"street": "Main St", "postal_code": "62704"}
    score = address_agent.score_suggestion("123 Main St, Springfield, IL 99999", requested)
    assert score < address_agent.HIGH_CONFIDENCE_THRESHOLD


def test_score_suggestion_zero_for_no_requested_components():
    assert address_agent.score_suggestion("123 Main St", {}) == 0.0


def test_score_suggestion_zero_for_empty_suggestion():
    assert address_agent.score_suggestion("", {"street": "Main St"}) == 0.0


def test_score_suggestions_sorted_descending():
    requested = {"street": "Main St", "postal_code": "62704"}
    suggestions = [
        "789 Oak Ave, Shelbyville, IL 62565",
        "123 Main St, Springfield, IL 62704",
    ]
    scored = address_agent.score_suggestions(suggestions, requested)
    assert scored[0][0] == "123 Main St, Springfield, IL 62704"
    assert scored[0][1] >= scored[1][1]


# ── verify_selected_value ────────────────────────────────────────────────────

def test_verify_selected_value_true_for_matching_field():
    assert address_agent.verify_selected_value(
        "Address field value: 123 Main St, Springfield, IL 62704",
        "123 Main St, Springfield, IL 62704",
    ) is True


def test_verify_selected_value_false_for_mismatched_field():
    assert address_agent.verify_selected_value(
        "Address field value: 456 Elm St, Shelbyville, IL 62565",
        "123 Main St, Springfield, IL 62704",
    ) is False


def test_verify_selected_value_false_for_empty_inputs():
    assert address_agent.verify_selected_value("", "123 Main St") is False
    assert address_agent.verify_selected_value("123 Main St", "") is False


def test_verify_selected_value_false_when_field_value_is_none():
    # extract_address_field_value returns None when it can't confidently
    # locate the field's own value — verification must fail closed, not
    # fall back to scanning the whole page for a coincidental match.
    assert address_agent.verify_selected_value(None, "123 Main St") is False


# ── extract_address_field_value ─────────────────────────────────────────────

def test_extract_address_field_value_from_quoted_value_attribute():
    text = 'textbox "Address" value="123 Main St, Springfield, IL 62704"'
    assert address_agent.extract_address_field_value(text) == "123 Main St, Springfield, IL 62704"


def test_extract_address_field_value_from_label_colon_format():
    text = "Page loaded.\nAddress field: 123 Main St, Springfield, IL 62704\nSubmit button visible."
    assert address_agent.extract_address_field_value(text) == "123 Main St, Springfield, IL 62704"


def test_extract_address_field_value_none_when_absent():
    text = "Page loaded. Submit button visible. No address information here."
    assert address_agent.extract_address_field_value(text) is None


def test_extract_address_field_value_does_not_false_positive_on_unrelated_quotes():
    # A suggestion that happens to also appear elsewhere in the page (e.g. a
    # breadcrumb or the now-closed dropdown's leftover markup) must NOT be
    # picked up as if it were the address field's own current value.
    text = 'Breadcrumb: "123 Main St, Springfield, IL 62704" > Checkout\nSubmit button visible.'
    assert address_agent.extract_address_field_value(text) is None


def test_verify_selected_value_ignores_coincidental_match_elsewhere_on_page():
    # Regression: verification must be based on the extracted field value,
    # not a naive substring/overlap check against the entire observation —
    # otherwise a suggestion appearing anywhere on the page falsely "verifies".
    observation = (
        'Breadcrumb: "123 Main St, Springfield, IL 62704" > Checkout\n'
        "Address field: 456 Elm St, Shelbyville, IL 62565\n"
    )
    field_value = address_agent.extract_address_field_value(observation)
    assert field_value == "456 Elm St, Shelbyville, IL 62565"
    assert address_agent.verify_selected_value(
        field_value, "123 Main St, Springfield, IL 62704"
    ) is False


# ── handle_address_dropdown_observation / handle_address_verification_observation ──
# These are the exact functions Brain's tool-loop calls into each turn, so
# testing them here proves the pause-trigger (ObstacleInputNeeded) behavior
# without needing to reach into Brain's non-importable nested closures.

_NO_MATCH_OBSERVATION = (
    'Address field open. Suggestions: role="listbox" with matching addresses below.\n'
    '- "999 Nowhere Ave, Faraway, ZZ 00000"\n'
    '- "888 Unrelated Rd, Somewhere Else, YY 11111"\n'
)


def test_handle_address_dropdown_high_confidence_injects_guidance_and_sets_pending():
    state = address_agent.AddressAutocompleteState()
    observation = (
        'Address field open. Suggestions: role="listbox" with matching addresses below.\n'
        '- "123 Main St, Springfield, IL 62704"\n'
    )
    result = address_agent.handle_address_dropdown_observation(
        observation,
        {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"},
        state,
        "example.com",
    )
    assert "[ADDRESS_AUTOCOMPLETE_DETECTED]" in result
    assert state.pending_selection == "123 Main St, Springfield, IL 62704"
    assert state.retries == 0


def test_handle_address_dropdown_low_confidence_retries_once_then_escalates():
    state = address_agent.AddressAutocompleteState()
    requested = {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"}

    # First low-confidence pass: consumes the one retry, does NOT raise.
    result = address_agent.handle_address_dropdown_observation(
        _NO_MATCH_OBSERVATION, requested, state, "example.com"
    )
    assert "[ADDRESS_AUTOCOMPLETE_LOW_CONFIDENCE]" in result
    assert state.retries == 1

    # Second low-confidence pass: retry budget exhausted -> must pause the run.
    with pytest.raises(ObstacleInputNeeded) as exc_info:
        address_agent.handle_address_dropdown_observation(
            _NO_MATCH_OBSERVATION, requested, state, "example.com"
        )
    assert exc_info.value.match.category == "address"
    assert exc_info.value.match.obstacle_type == "low_confidence_selection"
    assert exc_info.value.match.requires_human_input is True
    assert exc_info.value.match.candidates


def test_handle_address_dropdown_injects_spec_guidance_once():
    state = address_agent.AddressAutocompleteState()
    observation = (
        'Address field open. Suggestions: role="listbox" with matching addresses below.\n'
        '- "123 Main St, Springfield, IL 62704"\n'
    )
    result = address_agent.handle_address_dropdown_observation(
        observation,
        {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"},
        state,
        "example.com",
        spec_guidance="\n\n[ADDRESS_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert "[ADDRESS_AGENT_SPEC]" in result
    assert state.spec_injected is True

    # A second turn must not re-inject the (already-seen) spec text again.
    result2 = address_agent.handle_address_dropdown_observation(
        observation,
        {"street": "Main St", "house_number": "123", "city": "Springfield", "postal_code": "62704"},
        state,
        "example.com",
        spec_guidance="\n\n[ADDRESS_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert result2.count("[ADDRESS_AGENT_SPEC]") == 0


def test_handle_address_verification_success_clears_pending_selection():
    state = address_agent.AddressAutocompleteState(pending_selection="123 Main St, Springfield, IL 62704")
    observation = "Address field: 123 Main St, Springfield, IL 62704\nForm ready to submit."
    result = address_agent.handle_address_verification_observation(observation, state, "example.com")
    assert state.pending_selection is None
    assert "[ADDRESS_VERIFICATION_FAILED]" not in result


def test_handle_address_verification_failure_retries_once_then_escalates():
    state = address_agent.AddressAutocompleteState(
        pending_selection="123 Main St, Springfield, IL 62704",
        candidates=[("123 Main St, Springfield, IL 62704", 0.9)],
    )
    bad_observation = "Address field: 456 Elm St, Shelbyville, IL 62565\nForm ready to submit."

    # First verification failure: consumes the one retry, does NOT raise.
    result = address_agent.handle_address_verification_observation(bad_observation, state, "example.com")
    assert "[ADDRESS_VERIFICATION_FAILED]" in result
    assert state.retries == 1
    assert state.pending_selection is None

    # Simulate a second auto-selection + failed verification: retry budget
    # exhausted -> must pause the run instead of looping forever.
    state.pending_selection = "123 Main St, Springfield, IL 62704"
    with pytest.raises(ObstacleInputNeeded) as exc_info:
        address_agent.handle_address_verification_observation(bad_observation, state, "example.com")
    assert exc_info.value.match.category == "address"
    assert exc_info.value.match.obstacle_type == "verification_failed"
    assert exc_info.value.match.requires_human_input is True


def test_handle_address_verification_noop_when_nothing_pending():
    state = address_agent.AddressAutocompleteState()
    observation = "Address field: 123 Main St, Springfield, IL 62704\n"
    result = address_agent.handle_address_verification_observation(observation, state, "example.com")
    assert result == observation
    assert state.pending_selection is None


# ── build_address_guidance / build_address_retry_guidance ───────────────────

def test_build_address_guidance_contains_top_choice_and_instruction():
    guidance = address_agent.build_address_guidance(
        "123 Main St, Springfield, IL 62704", 0.9,
        [("123 Main St, Springfield, IL 62704", 0.9)],
    )
    assert "123 Main St, Springfield, IL 62704" in guidance
    assert "ADDRESS_AUTOCOMPLETE_DETECTED" in guidance


def test_build_address_retry_guidance_warns_against_clicking():
    guidance = address_agent.build_address_retry_guidance(
        {"street": "Main St"}, [("789 Oak Ave", 0.2)]
    )
    assert "ADDRESS_AUTOCOMPLETE_LOW_CONFIDENCE" in guidance
    assert "Do NOT click" in guidance


# ── AddressAutocompleteState ─────────────────────────────────────────────────

def test_address_autocomplete_state_defaults():
    state = address_agent.AddressAutocompleteState()
    assert state.retries == 0
    assert state.candidates == []
    assert state.pending_selection is None


# ── ObstacleMatch/build_input_form integration for the "address" category ──

def test_obstacle_match_carries_candidates():
    match = ObstacleMatch(
        category="address", obstacle_type="low_confidence_selection",
        requires_human_input=True, candidates=["123 Main St", "456 Main St"],
    )
    assert match.candidates == ["123 Main St", "456 Main St"]
    assert match.skill_name == "address_low_confidence_selection"


def test_build_input_form_for_address_lists_candidates_as_select_options():
    match = ObstacleMatch(
        category="address", obstacle_type="low_confidence_selection",
        requires_human_input=True, candidates=["123 Main St", "456 Main St"],
    )
    form = build_input_form(match, "example.com")
    assert form["title"] == "Confirm Address"
    field = form["sections"][0]["fields"][0]
    assert field["type"] == "select"
    values = [opt["value"] for opt in field["options"]]
    assert "123 Main St" in values
    assert "456 Main St" in values
    assert "__none__" in values
