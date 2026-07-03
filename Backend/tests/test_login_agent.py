"""Tests for the deterministic Login/Signup Interaction Agent support layer
(src/services/login_agent.py): context detection, credential extraction,
field mapping, and failure detection.
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake:fake@localhost/fake")

import pytest

from src.services import login_agent
from src.services.obstacle_handler import ObstacleInputNeeded, build_input_form, ObstacleMatch


# ── has_requested_credentials / extract_requested_credentials ──────────────

def test_has_requested_credentials_true_for_email_and_password():
    assert login_agent.has_requested_credentials({"email": "a@b.com", "password": "hunter2"}) is True


def test_has_requested_credentials_false_when_absent():
    assert login_agent.has_requested_credentials({"destination": "Paris"}) is False
    assert login_agent.has_requested_credentials({}) is False
    assert login_agent.has_requested_credentials(None) is False


def test_extract_requested_credentials_maps_known_keys():
    creds = login_agent.extract_requested_credentials({
        "email": "a@b.com", "password": "hunter2", "confirm_password": "hunter2",
    })
    assert creds == {"email": "a@b.com", "password": "hunter2", "confirm_password": "hunter2"}


def test_extract_requested_credentials_prefers_username_key_variants():
    creds = login_agent.extract_requested_credentials({"user_name": "jdoe", "pass": "hunter2"})
    assert creds["username"] == "jdoe"
    assert creds["password"] == "hunter2"


def test_extract_requested_credentials_empty_when_absent():
    assert login_agent.extract_requested_credentials({}) == {}
    assert login_agent.extract_requested_credentials(None) == {}


# ── detect_login_form_context ────────────────────────────────────────────────

def test_detect_login_form_context_true_for_signin_form():
    text = 'Sign in to your account. textbox "Email" textbox "Password" type="password"'
    assert login_agent.detect_login_form_context(text) is True


def test_detect_login_form_context_false_without_widget():
    text = "Your password is stored securely. No form here."
    assert login_agent.detect_login_form_context(text) is False


def test_detect_login_form_context_false_without_field():
    text = "Sign in to continue browsing our catalog."
    assert login_agent.detect_login_form_context(text) is False


def test_detect_login_form_context_false_on_empty():
    assert login_agent.detect_login_form_context("") is False
    assert login_agent.detect_login_form_context(None) is False


# ── extract_form_fields / map_fields_to_credentials ─────────────────────────

def test_extract_form_fields_parses_labeled_textboxes():
    text = 'textbox "Email" textbox "Password" textbox "Confirm Password"'
    fields = login_agent.extract_form_fields(text)
    assert "Email" in fields
    assert "Password" in fields
    assert "Confirm Password" in fields


def test_extract_form_fields_parses_input_attributes():
    text = "input[type=email][name=login_email] input[type=password][name=login_password]"
    fields = login_agent.extract_form_fields(text)
    assert "login_email" in fields
    assert "login_password" in fields


def test_map_fields_to_credentials_maps_email_and_password():
    fields = ["Email", "Password"]
    credentials = {"email": "a@b.com", "password": "hunter2"}
    mapping = login_agent.map_fields_to_credentials(fields, credentials)
    assert mapping == {"Email": "a@b.com", "Password": "hunter2"}


def test_map_fields_to_credentials_confirm_password_precedence():
    fields = ["Password", "Confirm Password"]
    credentials = {"password": "hunter2", "confirm_password": "hunter2"}
    mapping = login_agent.map_fields_to_credentials(fields, credentials)
    assert mapping["Password"] == "hunter2"
    assert mapping["Confirm Password"] == "hunter2"


def test_map_fields_to_credentials_falls_back_to_email_for_username_field():
    fields = ["Username"]
    credentials = {"email": "a@b.com"}
    mapping = login_agent.map_fields_to_credentials(fields, credentials)
    assert mapping["Username"] == "a@b.com"


def test_map_fields_to_credentials_skips_unclassified_fields():
    fields = ["Promo Code"]
    credentials = {"email": "a@b.com", "password": "hunter2"}
    mapping = login_agent.map_fields_to_credentials(fields, credentials)
    assert mapping == {}


# ── detect_login_failure ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "observation,expected",
    [
        ("Incorrect password. Please try again.", "invalid_credentials"),
        ("Your account has been locked due to too many failed attempts.", "account_locked"),
        ("Too many attempts, please try again later.", "too_many_attempts"),
        ("We don't recognize this device. Verify it's you.", "unrecognized_device"),
    ],
)
def test_detect_login_failure_matches_known_patterns(observation, expected):
    assert login_agent.detect_login_failure(observation) == expected


def test_detect_login_failure_none_on_clean_page():
    assert login_agent.detect_login_failure("Welcome back! Your dashboard is ready.") is None
    assert login_agent.detect_login_failure("") is None
    assert login_agent.detect_login_failure(None) is None


# ── build_login_field_guidance ───────────────────────────────────────────────

def test_build_login_field_guidance_never_leaks_raw_secret_value():
    mapping = {"Email": "a@b.com", "Password": "hunter2"}
    guidance = login_agent.build_login_field_guidance(mapping)
    assert "hunter2" not in guidance
    assert "a@b.com" not in guidance
    assert "Email" in guidance
    assert "Password" in guidance
    assert "LOGIN_FORM_DETECTED" in guidance


def test_build_login_field_guidance_empty_for_no_mapping():
    assert login_agent.build_login_field_guidance({}) == ""


# ── handle_login_form_observation ────────────────────────────────────────────

def test_handle_login_form_observation_injects_field_guidance_once():
    state = login_agent.LoginFormState()
    observation = 'Sign in to your account. textbox "Email" textbox "Password" type="password"'
    credentials = {"email": "a@b.com", "password": "hunter2"}

    result = login_agent.handle_login_form_observation(observation, credentials, state, "example.com")
    assert "[LOGIN_FORM_DETECTED]" in result
    assert state.guidance_injected is True

    result2 = login_agent.handle_login_form_observation(observation, credentials, state, "example.com")
    assert result2.count("[LOGIN_FORM_DETECTED]") == 0


def test_handle_login_form_observation_retries_once_then_escalates_on_failure():
    state = login_agent.LoginFormState()
    credentials = {"email": "a@b.com", "password": "hunter2"}
    fail_observation = 'Incorrect password. textbox "Email" textbox "Password" type="password"'

    result = login_agent.handle_login_form_observation(fail_observation, credentials, state, "example.com")
    assert "[LOGIN_REJECTED: invalid_credentials]" in result
    assert state.retries == 1

    with pytest.raises(ObstacleInputNeeded) as exc_info:
        login_agent.handle_login_form_observation(fail_observation, credentials, state, "example.com")
    assert exc_info.value.match.category == "login"
    assert exc_info.value.match.obstacle_type == "invalid_credentials"
    assert exc_info.value.match.requires_human_input is True


def test_handle_login_form_observation_injects_spec_guidance_once():
    state = login_agent.LoginFormState()
    observation = 'Sign in to your account. textbox "Email" textbox "Password" type="password"'
    credentials = {"email": "a@b.com", "password": "hunter2"}

    result = login_agent.handle_login_form_observation(
        observation, credentials, state, "example.com",
        spec_guidance="\n\n[LOGIN_AGENT_SPEC]\nDecision Tree: ...",
    )
    assert "[LOGIN_AGENT_SPEC]" in result
    assert state.spec_injected is True


# ── ObstacleMatch/build_input_form integration for the "login" category ────

def test_build_input_form_for_login_asks_for_corrected_value():
    match = ObstacleMatch(category="login", obstacle_type="invalid_credentials", requires_human_input=True)
    form = build_input_form(match, "example.com")
    assert form["title"] == "Login Issue"
    field = form["sections"][0]["fields"][0]
    assert field["type"] == "text"
    assert form["obstacle_category"] == "login"
