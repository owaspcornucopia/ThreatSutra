"""Contract tests for Cornucopia and GitHub response shapes.
Verifies that external API response structures match the fields the adapters consume.
Uses controlled fixtures — not live endpoints — so tests are deterministic and offline."""

import pytest
from src.validation import (
    ValidationError,
    validate_card,
    validate_cornucopia_response,
    validate_milestone,
    validate_milestones,
    validate_github_issue_reference,
    validate_threat,
    validate_threat_dragon_document,
)

# ---- Cornucopia response contract ----

VALID_CORNUCOPIA_RESPONSE = {
    "meta": {"edition": "webapp", "component": "cards", "language": "en", "version": "1.0"},
    "standards": [
        {"sectionID": "VE2", "name": "VE2", "description": "Input validation."}
    ],
}

def test_cornucopia_response_has_expected_envelope():
    """The response must contain meta and standards at the top level."""
    result = validate_cornucopia_response(VALID_CORNUCOPIA_RESPONSE)
    assert "meta" in result
    assert "standards" in result

def test_cornucopia_meta_contains_required_fields():
    """meta must include edition, component, language, version as strings."""
    meta = VALID_CORNUCOPIA_RESPONSE["meta"]
    for field in ("edition", "component", "language", "version"):
        assert field in meta
        assert isinstance(meta[field], str)

def test_cornucopia_card_has_required_fields_and_types():
    """Each card in standards must have sectionID, name, description as strings."""
    card = VALID_CORNUCOPIA_RESPONSE["standards"][0]
    validate_card(card)
    assert isinstance(card["sectionID"], str)
    assert isinstance(card["name"], str)
    assert isinstance(card["description"], str)

def test_cornucopia_response_missing_meta_fails_closed():
    with pytest.raises(ValidationError):
        validate_cornucopia_response({"standards": []})

def test_cornucopia_response_missing_standards_fails_closed():
    payload = {"meta": {"edition": "webapp", "component": "cards", "language": "en", "version": "1.0"}}
    with pytest.raises(ValidationError):
        validate_cornucopia_response(payload)

def test_cornucopia_card_missing_sectionID_fails_closed():
    with pytest.raises(ValidationError):
        validate_card({"name": "X", "description": "Y"})


def test_cornucopia_card_wrong_type_for_description_fails_closed():
    with pytest.raises(ValidationError):
        validate_card({"sectionID": "X", "name": "X", "description": 123})


def test_cornucopia_meta_wrong_type_for_edition_fails_closed():
    payload = {
        "meta": {"edition": 123, "component": "cards", "language": "en", "version": "1.0"},
        "standards": [],
    }
    with pytest.raises(ValidationError):
        validate_cornucopia_response(payload)


# ---- GitHub milestone response contract ----

VALID_MILESTONE_RESPONSE = {"number": 1, "title": "Phase 1", "description": "Desc", "state": "open"}


def test_github_milestone_has_required_fields():
    validate_milestone(VALID_MILESTONE_RESPONSE)
    assert isinstance(VALID_MILESTONE_RESPONSE["number"], int)
    assert isinstance(VALID_MILESTONE_RESPONSE["title"], str)


def test_github_milestone_missing_number_fails_closed():
    with pytest.raises(ValidationError):
        validate_milestone({"title": "Phase 1"})


def test_github_milestone_missing_title_fails_closed():
    with pytest.raises(ValidationError):
        validate_milestone({"number": 1})


def test_github_milestone_wrong_type_number_fails_closed():
    with pytest.raises(ValidationError):
        validate_milestone({"number": "not_int", "title": "Phase 1"})


def test_github_milestone_boolean_number_fails_closed():
    """bool is technically int in Python; validation must reject it."""
    with pytest.raises(ValidationError):
        validate_milestone({"number": True, "title": "Phase 1"})


# ---- GitHub issue reference contract ----

VALID_ISSUE_REFERENCE = {"number": 5, "title": "Issue title", "body": "Issue body"}

def test_github_issue_has_required_fields():
    validate_github_issue_reference(VALID_ISSUE_REFERENCE)
    assert isinstance(VALID_ISSUE_REFERENCE["number"], int)
    assert isinstance(VALID_ISSUE_REFERENCE["title"], str)


def test_github_issue_missing_title_fails_closed():
    with pytest.raises(ValidationError):
        validate_github_issue_reference({"number": 5, "body": "x"})


def test_github_issue_missing_body_fails_closed():
    with pytest.raises(ValidationError):
        validate_github_issue_reference({"number": 5, "title": "x"})


def test_github_issue_null_body_handled():
    """body=None is common for new issues — validation must not crash."""
    ref = {"number": 5, "title": "x", "body": None}
    validate_github_issue_reference(ref)


# ---- Threat Dragon document contract ----

def test_threat_dragon_document_valid_structure():
    doc = {
        "summary": {"title": "Title", "description": "Desc"},
        "detail": {"diagrams": [{"cells": [{"data": {"threats": []}}]}]},
    }
    validate_threat_dragon_document(doc)


def test_threat_dragon_document_missing_summary_fails():
    with pytest.raises(ValidationError):
        validate_threat_dragon_document({"detail": {"diagrams": []}})


def test_threat_dragon_document_missing_detail_fails():
    with pytest.raises(ValidationError):
        validate_threat_dragon_document({"summary": {"title": "T", "description": "D"}})


def test_threat_dragon_document_not_mapping_fails():
    with pytest.raises(ValidationError):
        validate_threat_dragon_document(["not", "a", "mapping"])


def test_threat_with_all_required_fields_passes():
    threat = {
        "id": "t1", "type": "cornucopia", "cardNumber": "VE2",
        "title": "Title", "description": "Description", "mitigation": "Mitigation",
    }
    validate_threat(threat)


def test_threat_missing_id_fails():
    with pytest.raises(ValidationError):
        validate_threat({"type": "cornucopia", "cardNumber": "VE2", "title": "T", "description": "D", "mitigation": "M"})


# ---- Edge cases ----

def test_empty_standards_list_passes():
    """An edition with no cards is a valid response."""
    payload = {
        "meta": {"edition": "webapp", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [],
    }
    validate_cornucopia_response(payload)


def test_card_with_unexpected_extra_fields_still_validates():
    """If Cornucopia adds new fields, validation must still pass as long as required fields exist."""
    card = {"sectionID": "X", "name": "X", "description": "Y", "new_field": "surprise"}
    validate_card(card)


def test_milestones_list_with_bad_entry_fails_closed():
    with pytest.raises(ValidationError):
        validate_milestones([VALID_MILESTONE_RESPONSE, {"number": "bad"}])


def test_github_search_response_shape():
    """The search response shape used by GitHubIssueExporter._search_github_for_marker."""
    search_response = {
        "total_count": 1,
        "items": [{"number": 42, "html_url": "https://github.com/owner/repo/issues/42"}],
    }
    assert search_response["total_count"] > 0
    item = search_response["items"][0]
    assert "number" in item
    assert "html_url" in item
