"""
Tests for Task #154 (Agent architecture hardening): the structured Observer
step, per-action Verifier, and deterministic Recovery pre-classifier, plus
stage-based spec prompt assembly.
"""
import pytest

from src.services.observer import observe, ObservedState
from src.services.verifier import verify_action, ValidationResult
from src.services.obstacle_handler import detect_obstacle_from_observed
from src.services.recovery import classify_failure, format_hint
from src.agents import spec_loader


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

def test_observe_detects_loading_modal_login_and_error_flags():
    text = "Please wait, loading... a cookie consent banner is shown. Error: request failed."
    state = observe(text)
    assert state.is_loading is True
    assert state.has_modal is True
    assert state.has_error is True
    assert state.error_signals


def test_observe_extracts_url_when_present():
    state = observe("Current URL: https://example.com/checkout\nPage loaded successfully.")
    assert state.url == "https://example.com/checkout"


def test_observe_clean_page_has_no_flags_and_is_not_blocked():
    state = observe("Welcome to the homepage. Everything looks good.")
    assert state.is_loading is False
    assert state.has_modal is False
    assert state.has_error is False
    assert state.captcha_type is None
    assert state.otp_type is None
    assert state.is_blocked is False


def test_observe_detects_captcha_and_marks_blocked():
    state = observe("Please complete the reCAPTCHA challenge to continue.")
    assert state.captcha_type is not None
    assert state.is_blocked is True


def test_observed_state_to_dict_has_expected_keys():
    state = observe("Some plain text")
    d = state.to_dict()
    for key in ("url", "is_loading", "has_modal", "has_login_form", "has_error",
                "error_signals", "captcha_type", "otp_type", "is_blocked"):
        assert key in d


def test_detect_obstacle_from_observed_reuses_precomputed_flags():
    state = observe("Sign in to your account: please enter the verification code we just sent to your email to continue.")
    match = detect_obstacle_from_observed(state)
    assert match is not None
    assert match.category == "otp"
    assert match.requires_human_input is True


def test_detect_obstacle_from_observed_returns_none_for_clean_state():
    state = observe("Nothing unusual here.")
    assert detect_obstacle_from_observed(state) is None


def test_detect_obstacle_from_observed_handles_none():
    assert detect_obstacle_from_observed(None) is None


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

def test_verify_action_fails_on_tool_error_status():
    state = observe("Error executing tool: element not found")
    result = verify_action("browser_click", {"index": 3}, "FAILED", state)
    assert result.passed is False
    assert result.severity == "BLOCKING"


def test_verify_action_fails_when_captcha_appears_after_action():
    state = observe("Please complete the reCAPTCHA challenge to continue.")
    result = verify_action("browser_click", {"index": 1}, "SUCCESS", state)
    assert result.passed is False
    assert result.severity == "BLOCKING"
    assert "CAPTCHA" in result.reason


def test_verify_action_fails_when_otp_prompt_appears():
    state = observe("Login verification: please enter your OTP below to proceed.")
    result = verify_action("browser_type", {"text": "foo"}, "SUCCESS", state)
    assert result.passed is False
    assert result.severity == "BLOCKING"


def test_verify_action_warns_on_error_signal_without_hard_failure():
    state = observe("Warning: 404 not found for that resource, but page still rendered.")
    result = verify_action("browser_navigate", {"url": "https://x.com"}, "SUCCESS", state)
    assert result.passed is False
    assert result.severity == "WARNING"


def test_verify_action_passes_clean_navigation_to_matching_host():
    state = observe("Current URL: https://example.com/page\nLoaded fine.")
    result = verify_action("browser_navigate", {"url": "https://example.com/page"}, "SUCCESS", state)
    assert result.passed is True


def test_verify_action_warns_on_navigation_host_mismatch():
    state = observe("Current URL: https://other-domain.com/landing\nLoaded fine.")
    result = verify_action("browser_navigate", {"url": "https://example.com/page"}, "SUCCESS", state)
    assert result.passed is True
    assert result.severity == "WARNING"


def test_verify_action_passes_and_notes_loading_after_click():
    state = observe("Please wait, loading the next section...")
    result = verify_action("browser_click", {"index": 2}, "SUCCESS", state)
    assert result.passed is True
    assert result.severity == "INFO"


def test_validation_result_to_prompt_note_empty_when_passed():
    result = ValidationResult("browser_click", True, "ok")
    assert result.to_prompt_note() == ""


def test_validation_result_to_prompt_note_nonempty_when_failed():
    result = ValidationResult("browser_click", False, "boom", severity="BLOCKING")
    note = result.to_prompt_note()
    assert "BLOCKING" in note
    assert "boom" in note


def test_validation_result_to_dict_roundtrip_fields():
    result = ValidationResult("browser_type", False, "reason text", severity="WARNING")
    d = result.to_dict()
    assert d == {
        "tool_name": "browser_type",
        "passed": False,
        "reason": "reason text",
        "severity": "WARNING",
    }


# ---------------------------------------------------------------------------
# Recovery pre-classifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error_text,expected", [
    ("Target page, context or browser has been closed", "BROWSER_CRASH"),
    ("Your session has expired, please log in again", "SESSION_EXPIRED"),
    ("Error executing tool: request timed out after 30s", "TIMEOUT"),
    ("403 Forbidden: access denied", "PERMISSION_DENIED"),
    ("Error: no such element matching that selector", "MISSING_ELEMENT"),
    ("404 page not found", "WRONG_PAGE"),
    ("Please complete the CAPTCHA to continue, rate limit exceeded", "TRANSIENT_BLOCK"),
])
def test_classify_failure_matches_expected_branch(error_text, expected):
    assert classify_failure(error_text) == expected


def test_classify_failure_returns_none_for_ambiguous_text():
    assert classify_failure("The agent could not complete the requested comparison.") is None


def test_format_hint_empty_when_no_classification():
    assert format_hint(None) == ""


def test_format_hint_includes_failure_type_when_classified():
    hint = format_hint("TIMEOUT")
    assert "TIMEOUT" in hint
    assert "DETERMINISTIC PRE-CLASSIFICATION HINT" in hint


# ---------------------------------------------------------------------------
# Stage-based spec loading
# ---------------------------------------------------------------------------

def test_build_system_prompt_full_spec_includes_recovery_protocol():
    spec = spec_loader.load_spec("browser")
    full_prompt = spec_loader.build_system_prompt(spec)
    assert "Recovery Protocol" in full_prompt
    assert "Stealth Behavior" in full_prompt


def test_build_system_prompt_recover_stage_excludes_stealth_and_form_sections():
    spec = spec_loader.load_spec("browser")
    recover_prompt = spec_loader.build_system_prompt(spec, stage="recover")
    assert "Recovery Protocol" in recover_prompt
    assert "Stealth Behavior" not in recover_prompt
    assert "Form Handling" not in recover_prompt


def test_build_system_prompt_execute_stage_excludes_recovery_protocol():
    spec = spec_loader.load_spec("browser")
    execute_prompt = spec_loader.build_system_prompt(spec, stage="execute")
    assert "Stealth Behavior" in execute_prompt
    assert "Recovery Protocol" not in execute_prompt


def test_build_system_prompt_unknown_stage_falls_back_to_full_spec():
    spec = spec_loader.load_spec("browser")
    fallback_prompt = spec_loader.build_system_prompt(spec, stage="not_a_real_stage")
    full_prompt = spec_loader.build_system_prompt(spec)
    assert fallback_prompt == full_prompt


def test_build_system_prompt_always_includes_backstory_regardless_of_stage():
    spec = spec_loader.load_spec("browser")
    recover_prompt = spec_loader.build_system_prompt(spec, stage="recover")
    assert "Backstory" in recover_prompt
