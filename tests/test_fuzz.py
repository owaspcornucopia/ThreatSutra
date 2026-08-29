"""Deterministic fuzz/property tests for malformed input handling.
Uses explicit lists of known-bad inputs instead of hypothesis (no new dependency).
Decision: Using deterministic generators to avoid adding hypothesis as a dependency.
If Johan approves, switch to hypothesis for broader coverage.
Commit note: "fuzz tests use deterministic generators — switch to hypothesis later if approved"
"""

import json
import pytest
from src.adapters.GitHubIssueClient import GitHubIssueClient
from src.validation import (
    ValidationError,
    extract_model_json_fields,
    extract_model_text_field,
    sanitize_text,
    validate_card,
    validate_evil_user_story,
    validate_export_artifact,
    validate_milestone,
    validate_review_record,
    validate_threat,
    validate_verification_test,
)

# ---- Malformed JSON payloads ----

MALFORMED_JSON_STRINGS = [
    "",
    "{",
    '{"unclosed',
    "null",
    "true",
    "42",
    '"just a string"',
    "[1, 2, 3]",
    '{"key": undefined}',
    "{key: 'no quotes'}",
    '{"a": "b",}',
    "\x00",
    "\n\n\n",
]

@pytest.mark.parametrize("bad_json", MALFORMED_JSON_STRINGS)
def test_extract_model_text_field_rejects_malformed_json(bad_json):
    with pytest.raises(ValidationError):
        extract_model_text_field(bad_json, "evil_user_story")


@pytest.mark.parametrize("bad_json", MALFORMED_JSON_STRINGS)
def test_extract_model_json_fields_rejects_malformed_json(bad_json):
    with pytest.raises(ValidationError):
        extract_model_json_fields(bad_json, ("score", "explanation"))


# ---- Control characters ----

CONTROL_CHAR_STRINGS = [
    "\x00hidden",
    "\x01SOH",
    "\x02STX",
    "\x07BELL",
    "\x08BACKSPACE",
    "\x0bVTAB",
    "\x0cFORMFEED",
    "\x0eSHIFTOUT",
    "\x1bESCAPE",
    "normal\x00hidden",
    "before\x1b[31mred\x1b[0mafter",
]


@pytest.mark.parametrize("bad_text", CONTROL_CHAR_STRINGS)
def test_validate_threat_rejects_control_characters(bad_text):
    threat = {
        "id": "t1",
        "type": "cornucopia",
        "cardNumber": "VE2",
        "title": bad_text,
        "description": "Desc",
        "mitigation": "Mitig",
    }
    with pytest.raises(ValidationError, match="control characters"):
        validate_threat(threat)


@pytest.mark.parametrize("bad_text", CONTROL_CHAR_STRINGS)
def test_validate_card_rejects_control_characters(bad_text):
    card = {"sectionID": "X", "name": bad_text, "description": "Y"}
    with pytest.raises(ValidationError, match="control characters"):
        validate_card(card)


# ---- Oversized fields ----


def test_oversized_threat_title_rejected():
    threat = {
        "id": "t1",
        "type": "cornucopia",
        "cardNumber": "VE2",
        "title": "A" * 7000,
        "description": "Desc",
        "mitigation": "Mitig",
    }
    with pytest.raises(ValidationError, match="over the"):
        validate_threat(threat)


def test_oversized_card_description_rejected():
    card = {"sectionID": "X", "name": "X", "description": "A" * 7000}
    with pytest.raises(ValidationError, match="over the"):
        validate_card(card)


def test_oversized_milestone_title_rejected():
    with pytest.raises(ValidationError, match="over the"):
        validate_milestone({"number": 1, "title": "A" * 7000})


def test_oversized_evil_user_story_rejected():
    huge = "As an attacker, I want to " + "x" * 7000 + ", so that y."
    with pytest.raises(ValidationError):
        validate_evil_user_story(huge)


def test_oversized_verification_test_rejected():
    huge = "Given " + "x" * 7000 + ", When y, Then z."
    with pytest.raises(ValidationError):
        validate_verification_test(huge)


# ---- Invalid URLs ----

INVALID_ISSUE_URLS = [
    "not-a-url",
    "http://github.com/owner/repo/issues/5",
    "https://github.com/owner/repo/issues/",
    "https://github.com/owner/repo/issues/abc",
    "https://github.com/owner/issues/5",
    "https://github.com/owner/repo/issues/5?query=1",
    "https://github.com/owner/repo/issues/5#fragment",
    "https://github.com/owner/repo/pull/5",
    "https://gitlab.com/owner/repo/issues/5",
    "https://github.com/owner/repo/issues/5/comments",
    "",
    "javascript:alert(1)",
    "ftp://github.com/owner/repo/issues/5",
]


@pytest.mark.parametrize("bad_url", INVALID_ISSUE_URLS)
def test_github_issue_client_rejects_invalid_url(bad_url):
    from unittest.mock import MagicMock
    session = MagicMock()
    client = GitHubIssueClient(session=session, allowed_repos=["owner/repo"])
    with pytest.raises(ValueError):
        client.get_issue(bad_url)


# ---- Malformed LLM output ----

MALFORMED_LLM_OUTPUTS = [
    '{"evil_user_story": null}',
    '{"evil_user_story": 123}',
    '{"evil_user_story": ""}',
    '{"evil_user_story": "   "}',
    '{"evil_user_story": "text", "extra": "field"}',
    '{"wrong_key": "text"}',
    "{}",
    '{"evil_user_story": {"nested": "object"}}',
]


@pytest.mark.parametrize("bad_output", MALFORMED_LLM_OUTPUTS)
def test_extract_model_text_field_rejects_malformed_llm_output(bad_output):
    with pytest.raises(ValidationError):
        extract_model_text_field(bad_output, "evil_user_story")


# ---- Sanitize text edge cases ----


def test_sanitize_strips_all_control_characters():
    for code in range(32):
        char = chr(code)
        result = sanitize_text(f"before{char}after")
        if char in "\t\n":
            assert char in result
        else:
            assert char not in result


def test_sanitize_preserves_normal_unicode():
    text = "Hello, 世界! Ñoño. Ü. €100."
    assert sanitize_text(text) == text


def test_sanitize_non_string_returns_empty():
    assert sanitize_text(None) == ""
    assert sanitize_text(123) == ""


# ---- validate_review_record fuzz ----

INVALID_REVIEW_RECORDS = [
    {},
    {"decision": "approve"},
    {"decision": "approve", "artifact_type": "evil_user_story"},
    {
        "decision": "reject",
        "artifact_type": "evil_user_story",
        "text": "t",
        "source_threat_id": "x",
        "source_card_id": "y",
        "source_milestone_number": 1,
        "timestamp": "t",
    },
    {
        "decision": "approve",
        "artifact_type": "bad_type",
        "text": "t",
        "source_threat_id": "x",
        "source_card_id": "y",
        "source_milestone_number": 1,
        "timestamp": "t",
    },
]


@pytest.mark.parametrize("bad_record", INVALID_REVIEW_RECORDS)
def test_validate_review_record_rejects_bad_input(bad_record):
    with pytest.raises(ValidationError):
        validate_review_record(bad_record)


# ---- validate_export_artifact fuzz ----

INVALID_EXPORT_ARTIFACTS = [
    {},
    {"artifact_type": "evil_user_story"},
    {
        "artifact_type": "unknown",
        "text": "t",
        "source_threat_id": "x",
        "source_card_id": "y",
        "source_milestone_number": 1,
    },
    "not a dict",
    None,
]


@pytest.mark.parametrize("bad_artifact", INVALID_EXPORT_ARTIFACTS)
def test_validate_export_artifact_rejects_bad_input(bad_artifact):
    with pytest.raises(ValidationError):
        validate_export_artifact(bad_artifact)


# ---- Evil user story format fuzz ----

MALFORMED_EVIL_USER_STORIES = [
    "Missing the required format entirely.",
    "As a hacker, I want to hack",  # missing "so that" and period
    "As a , I want to , so that .",  # empty placeholders
    "as an attacker, i want to hack, so that i win.",  # lowercase "as" still matches regex
    "As an attacker, I want to hack, so that I win",  # missing trailing period
    "As an attacker,\nI want to hack,\nso that I win.",  # multi-line
]


@pytest.mark.parametrize("bad_story", MALFORMED_EVIL_USER_STORIES)
def test_validate_evil_user_story_rejects_bad_format(bad_story):
    with pytest.raises(ValidationError):
        validate_evil_user_story(bad_story)


# ---- Verification test format fuzz ----

MALFORMED_VERIFICATION_TESTS = [
    "Missing the required format entirely.",
    "Given setup, When action",  # missing "Then"
    "Given , When , Then .",  # empty placeholders
    "Given setup,\nWhen action,\nThen outcome.",  # multi-line
    "Given setup, When action, Then outcome",  # missing trailing period
]

@pytest.mark.parametrize("bad_test", MALFORMED_VERIFICATION_TESTS)
def test_validate_verification_test_rejects_bad_format(bad_test):
    with pytest.raises(ValidationError):
        validate_verification_test(bad_test)


# ---- Mixed type attacks ----


def test_threat_with_integer_title_fails():
    threat = {
        "id": "t1",
        "type": "cornucopia",
        "cardNumber": "VE2",
        "title": 12345,
        "description": "Desc",
        "mitigation": "Mitig",
    }
    with pytest.raises(ValidationError, match="must be text"):
        validate_threat(threat)


def test_card_with_list_description_fails():
    card = {"sectionID": "X", "name": "X", "description": ["a", "b"]}
    with pytest.raises(ValidationError, match="must be text"):
        validate_card(card)


def test_milestone_with_none_title_fails():
    with pytest.raises(ValidationError):
        validate_milestone({"number": 1, "title": None})
