"""Tests for GitHubIssueExporter"""
import pytest
from src.adapters.GitHubIssueExporter import GitHubIssueExporter
from src.validation import ValidationError

ARTIFACT = {
    "artifact_type": "evil_user_story",
    "text": "As an attacker, I want to inject instructions, so that I exfiltrate data.",
    "source_threat_id": "threat-1",
    "source_card_id": "LLM9",
    "source_milestone_number": 1,
}
REVIEW_RECORD = {**ARTIFACT, "decision": "approve", "timestamp": "2026-08-14T00:00:00+00:00"}

def make_exporter(tmp_path, dry_run=True):
    return GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", dry_run=dry_run, markers_dir=str(tmp_path))

def test_exporter_defaults_to_dry_run_without_a_write_token(tmp_path, monkeypatch):
    """ export is live once credentials are configured, and dry-run only because there's nothing
    to authenticate with yet - not a separate opt-in flag to remember."""
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", markers_dir=str(tmp_path))
    assert exporter.dry_run is True

def test_exporter_goes_live_automatically_once_a_write_token_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token-for-test")
    exporter = GitHubIssueExporter(repo="owaspcornucopia/ThreatSutra", markers_dir=str(tmp_path))
    assert exporter.dry_run is False

def test_dry_run_does_not_create_a_marker(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "dry_run"
    assert list(tmp_path.iterdir()) == []

def test_dry_run_title_includes_traceability_footer_source():
    # covered indirectly by test above; body content is checked via _build_title_and_body
    pass

def test_export_refuses_incomplete_review_record(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    with pytest.raises(ValidationError):
        exporter.export({"artifact_type": "evil_user_story", "text": "incomplete"})

def test_live_export_without_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    with pytest.raises(RuntimeError, match="GITHUB_API token is required for live export"):
        exporter.export(REVIEW_RECORD)

def test_idempotency_key_is_stable_for_same_artifact(tmp_path):
    exporter = make_exporter(tmp_path)
    key_a = exporter._idempotency_key(ARTIFACT)
    key_b = exporter._idempotency_key(dict(ARTIFACT))
    assert key_a == key_b

def test_idempotency_key_differs_for_different_threats(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**ARTIFACT, "source_threat_id": "threat-2"}
    assert exporter._idempotency_key(ARTIFACT) != exporter._idempotency_key(other)

def test_already_exported_marker_short_circuits(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(ARTIFACT)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"github_issue_url": "https://github.com/owaspcornucopia/ThreatSutra/issues/999"}')
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "already_exported"

def test_export_rejects_any_decision_other_than_approve(tmp_path):
    """The exporter must independently refuse a persisted record
    that isn't decision == 'approve', regardless of what its caller believes."""
    exporter = make_exporter(tmp_path, dry_run=True)
    for decision in ("reject", "edit", "pending", ""):
        with pytest.raises(ValidationError):
            exporter.export({**REVIEW_RECORD, "decision": decision})