"""Tests for output contracts and display safety. """
import pytest
from src.validation import (
    ValidationError,
    extract_model_json_fields,
    extract_model_text_field,
    neutralize_for_display,
    relevance_color_for_score,
    validate_evil_user_story,
    validate_export_artifact,
    validate_relevance_assessment,
    validate_verification_test,
)

def test_valid_evil_user_story_passes():
    text = "As an attacker, I want to inject instructions, so that I exfiltrate data."
    assert validate_evil_user_story(text) == text

@pytest.mark.parametrize("bad_text", [
    "Not in the right format at all.",
    "As an attacker, I want to inject instructions, so that I exfiltrate data.\nExtra line.",
])
def test_invalid_evil_user_story_rejected(bad_text):
    with pytest.raises(ValidationError):
        validate_evil_user_story(bad_text)

def test_valid_verification_test_passes():
    text = "Given untrusted input, When it is processed, Then it is rejected."
    assert validate_verification_test(text) == text

def test_invalid_verification_test_rejected():
    with pytest.raises(ValidationError):
        validate_verification_test("This is not Given/When/Then formatted.")

def test_extract_model_text_field_happy_path():
    assert extract_model_text_field('{"evil_user_story": "As a bot, I want to X, so that Y."}', "evil_user_story") == \
        "As a bot, I want to X, so that Y."

@pytest.mark.parametrize("bad_response", [
    "not json at all",
    '{"wrong_field": "value"}',
    '{"evil_user_story": "a", "extra_field": "b"}',
])
def test_extract_model_text_field_rejects_malformed_output(bad_response):
    with pytest.raises(ValidationError):
        extract_model_text_field(bad_response, "evil_user_story")

def test_extract_model_json_fields_happy_path():
    payload = extract_model_json_fields('{"score": 7, "explanation": "Related to the milestone."}', ("score", "explanation"))
    assert payload["score"] == 7

def test_extract_model_json_fields_rejects_missing_field():
    with pytest.raises(ValidationError):
        extract_model_json_fields('{"score": 7}', ("score", "explanation"))

@pytest.mark.parametrize("score,expected_color", [(10, "green"), (8, "green"), (7, "yellow"), (5, "yellow"), (4, "red"), (1, "red")])
def test_relevance_color_thresholds_match_dfd_spec(score, expected_color):
    """Issue #12's color thresholds come directly from the DFD's threat #8
    mitigation text: green 8-10, yellow 5-8, red 1-4."""
    assert relevance_color_for_score(score) == expected_color

def test_validate_relevance_assessment_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        validate_relevance_assessment({"score": 11, "explanation": "x"})
    with pytest.raises(ValidationError):
        validate_relevance_assessment({"score": 0, "explanation": "x"})

def test_neutralize_for_display_strips_ansi_and_control_sequences():
    hostile = "\x1b[31mFAKE ERROR\x1b[0m normal text\x07\x1b]0;evil title\x07"
    cleaned = neutralize_for_display(hostile)
    assert "\x1b" not in cleaned
    assert "\x07" not in cleaned
    assert "normal text" in cleaned

def test_neutralize_for_display_preserves_newlines_and_tabs():
    text = "line one\nline two\ttabbed"
    assert neutralize_for_display(text) == text

def test_validate_export_artifact_requires_traceability_fields():
    with pytest.raises(ValidationError):
        validate_export_artifact({"artifact_type": "evil_user_story", "text": "As a bot, I want to X, so that Y."})

def test_validate_export_artifact_accepts_complete_artifact():
    artifact = {
        "artifact_type": "verification_test", "text": "Given X, When Y, Then Z.",
        "source_threat_id": "t1", "source_card_id": "c1", "source_milestone_number": 1,
    }
    assert validate_export_artifact(artifact) == artifact