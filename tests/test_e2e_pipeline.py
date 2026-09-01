"""End-to-end mocked pipeline tests (Issue #13).
Proves that the stages are correctly wired together from DFD input through
review record and export, with no network access."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import requests
from src.adapters.GitHubIssueExporter import GitHubIssueExporter
from src.orchestrator import run_pipeline
from src.validation import ValidationError

class FakeReader:
    """Deterministic reader replacing ThreatDragonReader for E2E tests."""

    def read_threat_source(self):
        return {
            "summary": {
                "description": "See https://github.com/owaspcornucopia/ThreatSutra/milestone/1",
            },
            "provenance": {
                "source_type": "threat_dragon",
                "location": "test.json",
                "retrieved_at": "2026-08-06T00:00:00+00:00",
                "content_hash": "a" * 64,
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
            ],
        }


def _make_mock_clients():
    milestone_client = MagicMock()
    milestone_client.get_milestones.return_value = [
        {"number": 1, "title": "Phase 1", "description": "Phase.", "state": "open"}
    ]
    milestone_client.get_provenance.return_value = {
        "source_type": "github_milestones",
        "location": "loc",
        "retrieved_at": "2026-08-06T00:00:00+00:00",
        "content_hash": "b" * 64,
    }
    cornucopia_client = MagicMock()
    cornucopia_client.find_card.return_value = {
        "sectionID": "LLM9",
        "name": "LLM9",
        "description": "Card desc.",
        "section": "LLM Top 10",
    }
    cornucopia_client.get_card_provenance.return_value = {
        "source_type": "cornucopia_api",
        "location": "loc",
        "retrieved_at": "2026-08-06T00:00:00+00:00",
        "content_hash": "c" * 64,
        "api_version": "1.0",
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
            "content_hash": "d" * 64,
        },
    }
    return milestone_client, cornucopia_client, explanation_client


def test_e2e_approved_artifact_exported_with_persisted_representation(tmp_path, monkeypatch):
    """E2E: DFD input → pipeline → artifact → approve → persist → re-read → export.
    Verifies the exporter receives the exact representation that was persisted to disk
    and that source identifiers survive end-to-end."""
    monkeypatch.setenv("GITHUB_API", "fake-token-for-e2e")

    reader = FakeReader()
    milestone_client, cornucopia_client, explanation_client = _make_mock_clients()
    # Step 1–5: Run pipeline to get AnalysisContext
    contexts = run_pipeline(
        reader=reader,
        milestone_client=milestone_client,
        cornucopia_client=cornucopia_client,
        explanation_client=explanation_client,
    )
    assert len(contexts) == 1
    context = contexts[0]
    # Step 6: Simulate artifact (skip real LLM call)
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "As an attacker, I want to inject code, so that I steal data.",
        "source_threat_id": context.threat_id,
        "source_card_id": context.card_id,
        "source_milestone_number": context.milestone_number,
        "model": "gemini-test",
        "prompt_template_version": "1.0",
    }
    # Step 7–8: Simulate review (approve) and persist to disk
    review_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "approve",
        **artifact,
        "relevance": {
            "score": 8,
            "color": "green",
            "explanation": "Relevant",
            "assessed_issue_urls": [],
        },
        "provenance": [
            {
                "source_type": p.source_type,
                "location": p.location,
                "content_hash": p.content_hash,
                "version": p.version,
            }
            for p in context.provenance
        ],
    }
    review_path = tmp_path / "review_e2e.json"
    review_path.write_text(json.dumps(review_record, indent=2))
    # Step 9: Re-read from disk (as the real CLI does)
    with open(review_path, "r", encoding="utf-8") as f:
        persisted_record = json.load(f)
    # Step 10: Export with mock GitHub POST
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "number": 42,
        "html_url": "https://github.com/owner/repo/issues/42",
    }
    mock_resp.raise_for_status = MagicMock()
    mock_session.post.return_value = mock_resp
    markers_dir = tmp_path / "markers"
    exporter = GitHubIssueExporter(
        repo="owaspcornucopia/ThreatSutra",
        dry_run=False,
        markers_dir=str(markers_dir),
        session=mock_session,
    )
    result = exporter.export(persisted_record)
    # Verify: export happened and source identifiers survived
    assert result["status"] == "created"
    assert result["marker"]["github_issue_number"] == 42
    assert result["marker"]["source_threat_id"] == context.threat_id
    assert result["marker"]["source_card_id"] == context.card_id
    assert result["marker"]["artifact_type"] == "evil_user_story"
    # Verify: the POST body contains the artifact text
    _, kwargs = mock_session.post.call_args
    assert artifact["text"] in kwargs["json"]["body"]
    # Verify: marker is persisted to disk
    key = exporter._idempotency_key(persisted_record)
    marker_path = exporter._marker_path(key)
    assert marker_path.exists()
    saved_marker = json.loads(marker_path.read_text())
    assert saved_marker["github_issue_url"] == "https://github.com/owner/repo/issues/42"

def test_e2e_rejected_artifact_not_exported(tmp_path, monkeypatch):
    """E2E: Rejected review must not reach the exporter (validate_review_record blocks it)."""
    monkeypatch.setenv("GITHUB_API", "fake-token-for-e2e")

    reader = FakeReader()
    milestone_client, cornucopia_client, explanation_client = _make_mock_clients()

    contexts = run_pipeline(
        reader=reader,
        milestone_client=milestone_client,
        cornucopia_client=cornucopia_client,
        explanation_client=explanation_client,
    )
    context = contexts[0]
    review_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "reject",
        "artifact_type": "evil_user_story",
        "text": "As an attacker, I want to inject code, so that I steal data.",
        "source_threat_id": context.threat_id,
        "source_card_id": context.card_id,
        "source_milestone_number": context.milestone_number,
    }
    mock_session = MagicMock(spec=requests.Session)
    markers_dir = tmp_path / "markers"
    exporter = GitHubIssueExporter(
        repo="owaspcornucopia/ThreatSutra",
        dry_run=False,
        markers_dir=str(markers_dir),
        session=mock_session,
    )
    with pytest.raises(ValidationError, match="decision must be 'approve'"):
        exporter.export(review_record)

    mock_session.post.assert_not_called()
    assert list(markers_dir.iterdir()) == []


def test_e2e_provenance_survives_pipeline():
    """E2E: all four provenance sources make it into the AnalysisContext."""
    reader = FakeReader()
    milestone_client, cornucopia_client, explanation_client = _make_mock_clients()

    contexts = run_pipeline(
        reader=reader,
        milestone_client=milestone_client,
        cornucopia_client=cornucopia_client,
        explanation_client=explanation_client,
    )
    context = contexts[0]
    source_types = {p.source_type for p in context.provenance}
    assert source_types == {
        "threat_dragon",
        "cornucopia_api",
        "cornucopia_explanation",
        "github_milestones",
    }


def test_e2e_duplicate_export_returns_already_exported(tmp_path, monkeypatch):
    """E2E: exporting the same approved artifact twice returns already_exported."""
    monkeypatch.setenv("GITHUB_API", "fake-token-for-e2e")

    reader = FakeReader()
    milestone_client, cornucopia_client, explanation_client = _make_mock_clients()
    contexts = run_pipeline(
        reader=reader,
        milestone_client=milestone_client,
        cornucopia_client=cornucopia_client,
        explanation_client=explanation_client,
    )
    context = contexts[0]
    review_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "approve",
        "artifact_type": "evil_user_story",
        "text": "As an attacker, I want to inject code, so that I steal data.",
        "source_threat_id": context.threat_id,
        "source_card_id": context.card_id,
        "source_milestone_number": context.milestone_number,
        "model": "gemini-test",
        "prompt_template_version": "1.0",
    }
    mock_session = MagicMock(spec=requests.Session)
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"number": 42, "html_url": "http://gh/42"}
    mock_resp.raise_for_status = MagicMock()
    mock_session.post.return_value = mock_resp

    exporter = GitHubIssueExporter(
        repo="owaspcornucopia/ThreatSutra",
        dry_run=False,
        markers_dir=str(tmp_path),
        session=mock_session,
    )
    result1 = exporter.export(review_record)
    assert result1["status"] == "created"
    result2 = exporter.export(review_record)
    assert result2["status"] == "already_exported"
    # POST should only have been called once
    mock_session.post.assert_called_once()
