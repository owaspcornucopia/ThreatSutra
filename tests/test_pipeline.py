from unittest.mock import MagicMock
import pytest
from src.context import AnalysisContext
from src.orchestrator import run_pipeline


class FakeThreatDragonReader:
    def read_threat_source(self):
        return {
            "summary": {"description": "See https://github.com/owaspcornucopia/ThreatSutra/milestone/1"},
            "provenance": {
                "source_type": "threat_dragon",
                "location": "loc",
                "retrieved_at": "2026-08-06T00:00:00+00:00",
                "content_hash": "a"
            },
            "threats": [
                {
                    "id": "t1",
                    "number": 1,
                    "type": "cornucopia-companion",
                    "cardNumber": "LLM9",
                    "title": "Title",
                    "description": "Desc",
                    "mitigation": "Mitig",
                }
            ]
        }

def test_run_pipeline():
    reader = FakeThreatDragonReader()
    milestone_client = MagicMock()
    milestone_client.get_milestones.return_value = [
        {"number": 1, "title": "Phase 1", "description": "Phase.", "state": "open"}
    ]
    milestone_client.get_provenance.return_value = {
        "source_type": "github_milestones",
        "location": "loc",
        "retrieved_at": "2026-08-06T00:00:00+00:00",
        "content_hash": "b"
    }
    
    cornucopia_client = MagicMock()
    cornucopia_client.find_card.return_value = {
        "sectionID": "LLM9", "name": "LLM9", "description": "Card desc.", "section": "LLM Top 10"
    }
    cornucopia_client.get_card_provenance.return_value = {
        "source_type": "cornucopia_api",
        "location": "loc",
        "retrieved_at": "2026-08-06T00:00:00+00:00",
        "content_hash": "c",
        "api_version": "1.0"
    }
    
    explanation_client = MagicMock()
    explanation_client.get_explanation.return_value = {
        "scenario": "Scen",
        "what_can_go_wrong": "Wrong",
        "requirement": "Req",
        "mitigation": "Mitig",
        "provenance": {
            "source_type": "cornucopia_explanation",
            "location": "loc",
            "retrieved_at": "2026-08-06T00:00:00+00:00",
            "content_hash": "d"
        }
    }
    
    results = run_pipeline(
        reader=reader,
        milestone_client=milestone_client,
        cornucopia_client=cornucopia_client,
        explanation_client=explanation_client
    )
    
    assert len(results) == 1
    ctx = results[0]
    assert isinstance(ctx, AnalysisContext)
    assert ctx.threat_id == "t1"
    assert ctx.card_id == "LLM9"
    assert ctx.milestone_number == 1

def test_resolve_edition_unknown_type():
    """Line 58: unknown threat type raises ValueError."""
    from src.orchestrator import resolve_edition
    with pytest.raises(ValueError, match="Unknown Threat Dragon threat type"):
        resolve_edition({"type": "totally_unknown"})

def test_call_ai_model_no_api_key(monkeypatch):
    """Line 68: missing GEMINI_API_KEY raises RuntimeError."""
    from src.orchestrator import call_ai_model
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        call_ai_model("test prompt")

def test_generate_evil_user_story(monkeypatch):
    """Lines 95-103: generate_evil_user_story returns a proper artifact dict."""
    from src.orchestrator import generate_evil_user_story
    from tests.test_context import build_context
    valid_response = '{"evil_user_story": "As an attacker, I want to inject code, so that I steal data."}'
    monkeypatch.setattr("src.orchestrator.call_ai_model", lambda prompt: valid_response)
    context = build_context()
    result = generate_evil_user_story(context)
    assert result["artifact_type"] == "evil_user_story"
    assert result["text"] == "As an attacker, I want to inject code, so that I steal data."
    assert result["source_threat_id"] == context.threat_id

def test_generate_verification_test(monkeypatch):
    """Line 123: generate_verification_test returns a proper artifact dict."""
    from src.orchestrator import generate_verification_test
    from tests.test_context import build_context
    valid_response = '{"verification_test": "Given a prompt, When code is injected, Then it is rejected."}'
    monkeypatch.setattr("src.orchestrator.call_ai_model", lambda prompt: valid_response)
    context = build_context()
    result = generate_verification_test(context)
    assert result["artifact_type"] == "verification_test"
    assert result["text"] == "Given a prompt, When code is injected, Then it is rejected."
    assert result["source_threat_id"] == context.threat_id

def test_generate_evil_user_story_validation_failure(monkeypatch):
    """Lines 100-102: generate_evil_user_story re-raises ValidationError after debug logging."""
    from src.orchestrator import generate_evil_user_story
    from src.validation import ValidationError
    from tests.test_context import build_context
    bad_response = '{"evil_user_story": "This is not in the correct format at all."}'
    monkeypatch.setattr("src.orchestrator.call_ai_model", lambda prompt: bad_response)
    context = build_context()
    with pytest.raises(ValidationError):
        generate_evil_user_story(context)
