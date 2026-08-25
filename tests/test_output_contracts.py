"""Tests for output contracts and display safety. """
import pytest

from src.validation import (
    MAX_FIELD_LENGTH,
    MAX_ISSUE_BODY_LENGTH,
    MAX_LIST_LENGTH,
    MAX_TOTAL_LENGTH,
    ValidationError,
    _validate_list,
    _validate_text,
    _validate_total_length,
    extract_model_json_fields,
    extract_model_text_field,
    is_valid_card,
    is_valid_milestone,
    is_valid_threat,
    neutralize_for_display,
    relevance_color_for_score,
    sanitize_text,
    validate_card,
    validate_context_budget,
    validate_cornucopia_response,
    validate_evil_user_story,
    validate_export_artifact,
    validate_github_issue_reference,
    validate_milestone,
    validate_milestones,
    validate_relevance_assessment,
    validate_review_record,
    validate_threat_dragon_document,
    validate_threats,
    validate_verification_test,
)

VALID_THREAT = {
    "id": "t1", "type": "cornucopia-companion", "cardNumber": "LLM9",
    "title": "Title", "description": "Desc", "mitigation": "Mitig",}
VALID_CARD = {"sectionID": "LLM9", "name": "LLM9", "description": "Card desc."}
VALID_MILESTONE = {"number": 1, "title": "Phase 1"}

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

def test_validate_text_none_required():
    with pytest.raises(ValidationError):
        _validate_text(None, "field", "test source", required=True)

def test_validate_text_not_string():
    with pytest.raises(ValidationError):
        _validate_text(123, "field", "test source")

def test_validate_text_empty_required():
    with pytest.raises(ValidationError):
        _validate_text("  ", "field", "test source", required=True)

def test_validate_text_control_chars():
    with pytest.raises(ValidationError):
        _validate_text("\x01", "field", "test source")

def test_validate_text_over_max_length():
    with pytest.raises(ValidationError):
        _validate_text("a" * (MAX_FIELD_LENGTH + 1), "field", "test source")

def test_validate_total_length_exceeded():
    with pytest.raises(ValidationError):
        _validate_total_length(MAX_TOTAL_LENGTH + 1, "test source")

def test_validate_list_not_a_list():
    with pytest.raises(ValidationError):
        _validate_list("not a list", "field")

def test_validate_list_over_max():
    with pytest.raises(ValidationError):
        _validate_list([1] * (MAX_LIST_LENGTH + 1), "field")

def test_sanitize_text_non_string():
    assert sanitize_text(123) == ""

def test_validate_card_links_not_list():
    bad_card = VALID_CARD.copy()
    bad_card["links"] = "not a list"
    with pytest.raises(ValidationError):
        validate_card(bad_card)

def test_validate_milestone_non_int_number():
    bad_milestone = VALID_MILESTONE.copy()
    bad_milestone["number"] = "1"
    with pytest.raises(ValidationError):
        validate_milestone(bad_milestone)

def test_validate_threats_list():
    assert validate_threats([VALID_THREAT]) == [VALID_THREAT]

def test_validate_threats_bad_entry():
    with pytest.raises(ValidationError):
        validate_threats([VALID_THREAT, "not a threat"])

def test_validate_milestones_bad_entry():
    with pytest.raises(ValidationError):
        validate_milestones([VALID_MILESTONE, "not a milestone"])

def test_validate_cornucopia_response_bad_card():
    response = {"cards": [{"invalid": "card"}]}
    with pytest.raises(ValidationError):
        validate_cornucopia_response(response)

def test_validate_context_budget_over_limit():
    with pytest.raises(ValidationError):
        validate_context_budget("a" * (MAX_TOTAL_LENGTH + 1))

def test_verify_test_multiline_rejected():
    with pytest.raises(ValidationError):
        validate_verification_test("Given a\nWhen b\nThen c")

def test_extract_model_text_field_strips_json_fence():
    raw = '```json\n{"evil_user_story": "As a bot, I want to X, so that Y."}\n```'
    assert extract_model_text_field(raw, "evil_user_story") == "As a bot, I want to X, so that Y."

def test_relevance_color_out_of_range():
    with pytest.raises(ValidationError):
        relevance_color_for_score(0)
    with pytest.raises(ValidationError):
        relevance_color_for_score(11)

def test_validate_relevance_assessment_non_int_score():
    with pytest.raises(ValidationError):
        validate_relevance_assessment({"score": "8", "explanation": "x"})

def test_validate_relevance_assessment_bool_score():
    with pytest.raises(ValidationError):
        validate_relevance_assessment({"score": True, "explanation": "x"})

def test_validate_github_issue_ref_missing_field():
    with pytest.raises(ValidationError):
        validate_github_issue_reference({"title": "x"})

def test_validate_github_issue_ref_body_too_long():
    with pytest.raises(ValidationError):
        validate_github_issue_reference({"number": 1, "title": "t", "body": "a" * (MAX_ISSUE_BODY_LENGTH + 1), "url": "u"})

def test_neutralize_for_display_none():
    assert neutralize_for_display(None) == ""

def test_validate_export_artifact_bad_type():
    with pytest.raises(ValidationError):
        validate_export_artifact({"artifact_type": "unknown", "text": "a", "source_threat_id": "b", "source_card_id": "c", "source_milestone_number": 1})

def test_validate_review_record_bad_artifact_type():
    with pytest.raises(ValidationError):
        validate_review_record({"artifact_type": "unknown", "verdict": "accept"})

def test_extract_json_fields_fence_stripped():
    raw = '```json\n{"score": 8, "explanation": "x"}\n```'
    payload = extract_model_json_fields(raw, ("score", "explanation"))
    assert payload["score"] == 8

def test_extract_json_fields_invalid_json():
    with pytest.raises(ValidationError):
        extract_model_json_fields("not json", ("score", "explanation"))

def test_is_valid_threat_true():
    assert is_valid_threat(VALID_THREAT)

def test_is_valid_threat_false():
    assert not is_valid_threat({"id": "t1"})

def test_is_valid_card_true():
    assert is_valid_card(VALID_CARD)

def test_is_valid_card_false():
    assert not is_valid_card({"name": "only name"})

def test_is_valid_milestone_true():
    assert is_valid_milestone(VALID_MILESTONE)

def test_is_valid_milestone_false():
    assert not is_valid_milestone({"number": "1"})

def test_validate_text_none_optional():
    """Line 52: _validate_text with None and required=False returns 0."""
    result = _validate_text(None, "optional_field", "test", required=False)
    assert result == 0

def test_validate_threat_dragon_document_bad_threat():
    """Lines 184-185: A bad threat inside a valid document structure raises."""
    doc = {
        "summary": {"title": "Test", "description": "Desc"},
        "detail": {
            "diagrams": [{
                "cells": [{
                    "data": {
                        "threats": [{"id": "t1"}]  
                    }
                }]
            }]
        }
    }
    with pytest.raises(ValidationError, match="Threat Dragon threat at diagram"):
        validate_threat_dragon_document(doc)

def test_validate_cornucopia_response_with_invalid_card():
    """Lines 207-208: A bad card inside a valid response envelope raises."""
    payload = {
        "meta": {"edition": "webapp", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [{"sectionID": "LLM9"}]  
    }
    with pytest.raises(ValidationError, match="Cornucopia card at position"):
        validate_cornucopia_response(payload)

def test_validate_context_budget_exceeds_token_limit():
    """Line 237: context with huge text exceeds MAX_CONTEXT_TOKENS."""
    # MAX_CONTEXT_TOKENS=3000, CHARS_PER_TOKEN_ESTIMATE=3, so 9001+ chars exceeds
    huge_fields = {"field1": "a" * 5000, "field2": "b" * 5000}
    with pytest.raises(ValidationError, match="token limit"):
        validate_context_budget(huge_fields)

def test_validate_relevance_explanation_too_long():
    """Line 302: explanation exceeds MAX_FIELD_LENGTH."""
    payload = {"score": 5, "explanation": "x" * (MAX_FIELD_LENGTH + 1)}
    with pytest.raises(ValidationError):
        validate_relevance_assessment(payload)

def test_validate_review_record_invalid_artifact_type():
    """Line 355: review record with valid decision but bad artifact_type."""
    record = {
        "decision": "approve",
        "artifact_type": "unknown_type",
        "text": "Some text",
        "source_threat_id": "t1",
        "source_card_id": "LLM9",
        "source_milestone_number": 1,
        "timestamp": "2026-08-18T00:00:00+00:00",
    }
    with pytest.raises(ValidationError, match="artifact_type must be"):
        validate_review_record(record)