import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from src.adapters.GitHubIssueExporter import GitHubIssueExporter
from src.context import build_analysis_context
from tests.test_context import (
    CARD,
    CARD_PROVENANCE,
    EXPLANATION,
    MILESTONE,
    MILESTONE_PROVENANCE,
    THREAT,
    THREAT_PROVENANCE,
)


def build_fake_review_record(decision="approve"):
    context = build_analysis_context(
        threat=THREAT,
        threat_provenance=THREAT_PROVENANCE,
        card=CARD,
        card_provenance=CARD_PROVENANCE,
        explanation=EXPLANATION,
        milestone=MILESTONE,
        milestone_provenance=MILESTONE_PROVENANCE,
    )
    return {
        "artifact_type": "evil_user_story",
        "text": "As an attacker, I want to inject instructions, so that I exfiltrate data.",
        "source_threat_id": context.threat_id,
        "source_card_id": context.card_id,
        "source_milestone_number": context.milestone_number,
        "decision": decision,
        "timestamp": "2026-08-25T00:00:00+00:00",
        "model": "gemini-test",
        "prompt_template_version": "v1",
        "relevance": {"score": 9, "explanation": "Highly relevant", "color": "green", "assessed_issue_urls": []},
        "provenance": [
            {"source_type": "threat_dragon", "location": "loc1", "retrieved_at": "now", "content_hash": "h1", "version": ""},
        ]
    }

def make_mock_session(status_code=201, json_response=None):
    if json_response is None:
        json_response = {"number": 101, "html_url": "https://github.com/owaspcornucopia/ThreatSutra/issues/101"}
    session = MagicMock(spec=requests.Session)
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_response
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    session.post.return_value = resp
    session.get.return_value = resp
    return session

def test_full_flow_approved_export(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    record = build_fake_review_record("approve")
    
    session = make_mock_session()
    exporter = GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", dry_run=False, markers_dir=str(tmp_path), session=session)
    
    result = exporter.export(record)
    
    assert result["status"] == "created"
    assert result["marker"]["github_issue_number"] == 101
    
    # Verify marker is written to disk
    key = exporter._idempotency_key(record)
    marker_path = exporter._marker_path(key)
    assert marker_path.exists()
    
    saved_marker = json.loads(marker_path.read_text())
    assert saved_marker["github_issue_url"] == "https://github.com/owaspcornucopia/ThreatSutra/issues/101"
    
def test_full_flow_rejected_does_not_export(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    from src.validation import ValidationError
    
    record = build_fake_review_record("reject")
    session = make_mock_session()
    exporter = GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", dry_run=False, markers_dir=str(tmp_path), session=session)
    
    with pytest.raises(ValidationError, match="decision must be 'approve'"):
        exporter.export(record)
        
    session.post.assert_not_called()
    assert list(tmp_path.iterdir()) == []
    
def test_crash_between_github_and_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    record = build_fake_review_record("approve")
    
    session = make_mock_session()
    exporter = GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", dry_run=False, markers_dir=str(tmp_path), session=session)
    key = exporter._idempotency_key(record)
    marker_path = exporter._marker_path(key)
    
    # Monkeypatch write_text to simulate a crash exactly when the final marker is being written
    original_write_text = Path.write_text
    def failing_write_text(self, data, *args, **kwargs):
        if "github_issue_url" in data:
            raise OSError("Simulated crash writing final marker!")
        return original_write_text(self, data, *args, **kwargs)
        
    monkeypatch.setattr(Path, "write_text", failing_write_text)
    
    with pytest.raises(OSError, match="Simulated crash"):
        exporter.export(record)
        
    # The pending marker should still be there because the crash happened after GitHub call
    assert marker_path.exists()
    saved = json.loads(marker_path.read_text())
    assert saved["status"] == "pending"
    
    # Restore write_text for recovery phase
    monkeypatch.undo()
    
    # Simulate time passing so it's considered stale
    from datetime import datetime, timedelta, timezone
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(json.dumps({"status": "pending", "created_at": stale_time}))
    
    # Make session.get return the issue search hit to simulate that GitHub created the issue
    session.get.return_value.json.return_value = {
        "total_count": 1, 
        "items": [{"number": 101, "html_url": "https://github.com/owaspcornucopia/ThreatSutra/issues/101"}]
    }
    
    # Now try again - it should recover the pending marker via GitHub search
    result = exporter.export(record)
    assert result["status"] == "already_exported"
    assert result["marker"]["github_issue_number"] == 101
    
    # Verify final marker was written successfully
    saved_final = json.loads(marker_path.read_text())
    assert "github_issue_url" in saved_final
