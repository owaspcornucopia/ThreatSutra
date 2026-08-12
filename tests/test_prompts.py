"""Tests for prompt builders"""
from src.prompts import build_evil_user_story_prompt, build_relevance_prompt, build_verification_test_prompt
from tests.test_context import build_context

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