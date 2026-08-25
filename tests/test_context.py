"""Tests for the AnalysisContext mapping layer."""
import pytest

from src.context import build_analysis_context, select_milestone
from src.validation import ValidationError

THREAT = {
    "id": "b95bf6e0-a923-40ee-b9f6-87ac1846e975",
    "number": 3,
    "type": "cornucopia-companion",
    "cardNumber": "LLM9",
    "title": "Deckard can embed malicious instructions in external content",
    "description": "This threat is related to the AI orchestrator.",
    "mitigation": "Treat external content as untrusted evidence, never instructions.",
}
THREAT_PROVENANCE = {
    "source_type": "threat_dragon", "location": "ThreatDragonModels/DFD_ThreatSutra.json",
    "retrieved_at": "2026-08-06T00:00:00+00:00", "content_hash": "a" * 64,
}
CARD = {"sectionID": "LLM9", "name": "LLM9", "description": "Indirect prompt injection.", "section": "LLM Top 10"}
CARD_PROVENANCE = {
    "source_type": "cornucopia_api", "location": "https://cornucopia.owasp.org/api/cre/companion/en",
    "retrieved_at": "2026-08-06T00:00:00+00:00", "content_hash": "b" * 64, "api_version": "1.0",
}
EXPLANATION = {
    "scenario": "An attacker embeds instructions in a document the model later reads.",
    "what_can_go_wrong": "The model follows the embedded instructions instead of the user's.",
    "requirement": "The system must treat external content as data, never as instructions.",
    "mitigation": "The system must treat external content as data, never as instructions.",
    "provenance": {
        "source_type": "cornucopia_explanation", "location": "https://raw.githubusercontent.com/OWASP/cornucopia/...",
        "retrieved_at": "2026-08-06T00:00:00+00:00", "content_hash": "c" * 64,
    },
}
MILESTONE = {"number": 1, "title": "Phase 1", "description": "AI-assisted requirement generation.", "state": "open"}
MILESTONE_PROVENANCE = {
    "source_type": "github_milestones", "location": "https://api.github.com/repos/owaspcornucopia/ThreatSutra/milestones",
    "retrieved_at": "2026-08-06T00:00:00+00:00", "content_hash": "d" * 64,
}

def build_context(**overrides):
    kwargs = dict(
        threat=THREAT, threat_provenance=THREAT_PROVENANCE, card=CARD, card_provenance=CARD_PROVENANCE,
        explanation=EXPLANATION, milestone=MILESTONE, milestone_provenance=MILESTONE_PROVENANCE,
    )
    kwargs.update(overrides)
    return build_analysis_context(**kwargs)

def test_context_joins_all_sources_correctly():
    context = build_context()
    assert context.threat_id == THREAT["id"]
    assert context.card_id == CARD["sectionID"]
    assert context.milestone_number == 1
    assert context.card_requirement == EXPLANATION["requirement"]

def test_context_extracts_linked_issue_urls():
    threat = {**THREAT, "description": (
        "See https://github.com/owaspcornucopia/ThreatSutra/issues/5 and "
        "https://github.com/owaspcornucopia/ThreatSutra/issues/6"
    )}
    context = build_context(threat=threat)
    assert context.linked_issue_urls == (
        "https://github.com/owaspcornucopia/ThreatSutra/issues/5",
        "https://github.com/owaspcornucopia/ThreatSutra/issues/6",
    )

def test_context_carries_provenance_for_every_source():
    context = build_context()
    assert len(context.provenance) == 4
    source_types = {p.source_type for p in context.provenance}
    assert source_types == {"threat_dragon", "cornucopia_api", "cornucopia_explanation", "github_milestones"}

def test_context_rejects_invalid_threat():
    with pytest.raises(ValidationError):
        build_context(threat={"id": "x"})  # missing required fields

def test_context_enforces_token_budget():
    huge_text = "A" * 30000
    with pytest.raises(ValidationError):
        build_context(threat={**THREAT, "description": huge_text})

def test_select_milestone_found():
    assert select_milestone([MILESTONE, {"number": 2, "title": "Phase 2"}], 1) == MILESTONE

def test_select_milestone_fails_closed_when_missing():
    with pytest.raises(ValidationError):
        select_milestone([{"number": 2, "title": "Phase 2"}], 1)