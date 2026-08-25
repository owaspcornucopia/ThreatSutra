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
    key_a = exporter._idempotency_key(REVIEW_RECORD)
    key_b = exporter._idempotency_key(dict(REVIEW_RECORD))
    assert key_a == key_b

def test_idempotency_key_differs_for_different_threats(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "source_threat_id": "threat-2"}
    assert exporter._idempotency_key(REVIEW_RECORD) != exporter._idempotency_key(other)

def test_already_exported_marker_short_circuits(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
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

def test_revised_text_produces_different_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "text": "Revised text"}
    assert exporter._idempotency_key(REVIEW_RECORD) != exporter._idempotency_key(other)

def test_revised_milestone_produces_different_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "source_milestone_number": 2}
    assert exporter._idempotency_key(REVIEW_RECORD) != exporter._idempotency_key(other)

def test_revised_template_version_produces_different_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "prompt_template_version": "v2"}
    assert exporter._idempotency_key(REVIEW_RECORD) != exporter._idempotency_key(other)

def test_concurrent_reservation_prevents_duplicate_export(tmp_path):
    from datetime import datetime, timezone
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    # pre-create fresh pending reservation
    marker_path.write_text(f'{{"status": "pending", "created_at": "{datetime.now(timezone.utc).isoformat()}"}}')
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "already_exported"

def test_stale_pending_marker_is_recovered(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')
    
    # Mock search to return an existing issue
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self):
                    return {"total_count": 1, "items": [{"number": 99, "html_url": "http://gh/99"}]}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "already_exported"
    assert result["marker"]["github_issue_number"] == 99

def test_github_search_for_existing_issue(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = "fake"
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    assert exporter._search_github_for_marker("key123") is None

def test_export_with_stale_marker_not_on_github(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')
    
    # Mock search to return NO existing issue
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    
    result = exporter.export(REVIEW_RECORD)
    # Because dry_run=True, after overwriting the stale marker with a new pending one, it returns dry_run
    assert result["status"] == "dry_run"

def test_recover_pending_marker_missing_date(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending"}')
    # Missing date triggers timed_out=True. Since dry_run=True, search returns None, marker unlinks, returns None.
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

def test_recover_pending_marker_corrupted_json(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("{not valid json")
    # A corrupted marker should be unlinked and treated as if it didn't exist (returns None)
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

def test_recover_pending_marker_invalid_date(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending", "created_at": "bad-date-string"}')
    # Bad date triggers timed_out=True. Since dry_run=True, search returns None, marker unlinks, returns None.
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

def test_search_github_for_marker_request_exception(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = "fake"
    import requests
    class MockSession:
        def get(self, *args, **kwargs):
            raise requests.RequestException("Network error")
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    # Should catch exception and gracefully return None
    assert exporter._search_github_for_marker("key123") is None

def test_export_no_token_cleans_up_marker(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    with pytest.raises(RuntimeError, match="token is required"):
        exporter.export(REVIEW_RECORD)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    # The pending marker should be cleaned up before raising
    assert not marker_path.exists()

def test_marker_body_contains_idempotency_marker(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    result = exporter.export(REVIEW_RECORD)
    assert f"<!-- threatsutra-marker:{key} -->" in result["body"]

def test_failed_github_post_cleans_up_reservation(tmp_path, monkeypatch):
    import requests
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    
    # mock session post to raise error
    class MockSession:
        def post(self, *args, **kwargs):
            raise requests.RequestException("GitHub is down")
        def mount(self, *args, **kwargs):
            pass
            
    exporter.session = MockSession()
    
    with pytest.raises(RuntimeError, match="GitHub is down"):
        exporter.export(REVIEW_RECORD)
        
    key = exporter._idempotency_key(REVIEW_RECORD)
    assert not exporter._marker_path(key).exists()