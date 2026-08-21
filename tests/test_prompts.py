"""Tests for prompt builders"""
from src.prompts import build_evil_user_story_prompt, build_relevance_prompt, build_verification_test_prompt
from tests.test_context import build_context
from src.validation import ValidationError
import pytest

def test_evil_user_story_prompt_delimits_untrusted_content():
    context = build_context()
    prompt = build_evil_user_story_prompt(context)
    assert context.card_scenario in prompt
    assert "BEGIN UNTRUSTED" in prompt and "END UNTRUSTED" in prompt
    assert "evil_user_story" in prompt

def test_verification_test_prompt_uses_card_requirement_not_threat_field():
    """Regression test for the #5 bug: must source from the mapped card's
    requirement, never from a nonexistent threat['requirement'] field."""
    context = build_context()
    prompt = build_verification_test_prompt(context)
    assert context.card_requirement in prompt
    assert context.threat_mitigation in prompt

def test_relevance_prompt_includes_linked_issues_and_milestone():
    context = build_context()
    linked_issues = [{"number": 5, "title": "Verification test generation", "body": "Implement #5."}]
    prompt = build_relevance_prompt(context, linked_issues)
    assert context.milestone_title in prompt
    assert "LINKED ISSUE #5" in prompt
    assert '"score"' in prompt and '"explanation"' in prompt

def test_relevance_prompt_handles_no_linked_issues():
    context = build_context()
    prompt = build_relevance_prompt(context, [])
    assert "no linked GitHub issues" in prompt

def test_relevance_prompt_caps_linked_issues():
    context = build_context()
    linked_issues = [{"number": i, "title": f"Issue {i}", "body": "Body"} for i in range(15)]
    prompt = build_relevance_prompt(context, linked_issues)
    assert "LINKED ISSUE #9" in prompt
    assert "LINKED ISSUE #10" not in prompt

def test_relevance_prompt_truncates_long_bodies():
    context = build_context()
    long_body = "x" * 4000
    linked_issues = [{"number": 1, "title": "Long issue", "body": long_body}]
    prompt = build_relevance_prompt(context, linked_issues)
    assert "[truncated]" in prompt
    assert long_body not in prompt
    assert len(prompt) < 4000

def test_relevance_prompt_under_budget_succeeds():
    context = build_context()
    linked_issues = [{"number": 1, "title": "Normal issue", "body": "Normal body"}]
    prompt = build_relevance_prompt(context, linked_issues)
    assert prompt is not None

def test_relevance_prompt_over_budget_raises_validation_error():
    """Craft many max-size issues to push the prompt over the token budget."""
    context = build_context()
    linked_issues = [
        {"number": i, "title": f"Issue {i}", "body": "x" * 1000}
        for i in range(10)
    ]
    with pytest.raises(ValidationError, match="Relevance prompt exceeds token budget"):
        build_relevance_prompt(context, linked_issues)

def test_oversized_content_never_reaches_call_ai_model():
    """Verify that oversized prompts raise ValidationError before they could be sent to the model."""
    context = build_context()
    linked_issues = [
        {"number": i, "title": f"Issue {i}", "body": "A" * 1000}
        for i in range(10)
    ]
    with pytest.raises(ValidationError):
        build_relevance_prompt(context, linked_issues)