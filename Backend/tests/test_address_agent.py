"""Tests for the deterministic Address Interaction Agent support layer
(src/services/address_agent.py): context detection, requested-address
extraction, suggestion extraction/scoring, and post-selection verification.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

from src.services import address_agent
from src.services.obstacle_handler import ObstacleMatch, build_input_form


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
