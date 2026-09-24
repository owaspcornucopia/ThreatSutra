"""Tests for GitHubIssueExporter"""
import json
import sys
import pytest
import requests
from src.adapters.GitHubIssueExporter import GitHubIssueExporter, ExportLock, MARKER_SCHEMA_VERSION
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
    # No .json marker file should remain; .lock files are expected OS-lock artifacts
    assert list(tmp_path.glob("*.json")) == []

def test_dry_run_title_includes_traceability_footer_source(tmp_path):
    """Issue #13: the body must contain the traceability footer with source threat, card, and milestone."""
    exporter = make_exporter(tmp_path, dry_run=True)
    result = exporter.export(REVIEW_RECORD)
    body = result["body"]
    assert "Source threat:" in body
    assert "Source card:" in body
    assert "Milestone:" in body
    assert "threatsutra-marker:" in body
    assert "human review gate" in body

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
    # A valid completed marker must include all required fields to pass validation
    completed_marker = json.dumps({
        "idempotency_key": key,
        "github_issue_number": 999,
        "github_issue_url": "https://github.com/owaspcornucopia/ThreatSutra/issues/999",
        "schema_version": MARKER_SCHEMA_VERSION,
    })
    marker_path.write_text(completed_marker)
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "already_exported"

def test_export_rejects_any_decision_other_than_approve(tmp_path):
    """The exporter must independently refuse a persisted record
    that isn't decision == 'approve', regardless of what its caller believes."""
    exporter = make_exporter(tmp_path, dry_run=True)
    for decision in ("reject", "edit", "pending", ""):
        with pytest.raises(ValidationError):
            exporter.export({**REVIEW_RECORD, "decision": decision})

def test_revised_text_produces_same_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "text": "Revised text"}
    assert exporter._idempotency_key(REVIEW_RECORD) == exporter._idempotency_key(other)

def test_revised_milestone_produces_different_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "source_milestone_number": 2}
    assert exporter._idempotency_key(REVIEW_RECORD) != exporter._idempotency_key(other)

def test_revised_template_version_produces_same_idempotency_key(tmp_path):
    exporter = make_exporter(tmp_path)
    other = {**REVIEW_RECORD, "prompt_template_version": "v2"}
    assert exporter._idempotency_key(REVIEW_RECORD) == exporter._idempotency_key(other)

def test_pre_post_marker_recovers_immediately(tmp_path, monkeypatch):
    """A marker with phase 'pre_post' means the previous process definitely
    crashed before attempting POST. It immediately retries without searching."""
    from datetime import datetime, timezone
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text(f'{{"status": "pending", "phase": "pre_post", "created_at": "{datetime.now(timezone.utc).isoformat()}", "schema_version": "2"}}')
    
    class MockSession:
        def post(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": 88, "html_url": "http://gh/88"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "created"
    assert result["marker"]["github_issue_number"] == 88

def test_post_attempted_marker_reconciles(tmp_path, monkeypatch):
    """A marker with phase 'post_attempted' means a POST might have happened.
    It MUST search GitHub first to reconcile."""
    from datetime import datetime, timezone
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text(f'{{"status": "pending", "phase": "post_attempted", "created_at": "{datetime.now(timezone.utc).isoformat()}", "schema_version": "2"}}')
    
    class MockSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 1, "items": [{"number": 99, "html_url": "http://gh/99"}]}
            return R()
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
    result = exporter._search_github_for_marker("key123")
    assert result == {"found": False}

def test_github_search_with_hit_returns_found_true(tmp_path):
    """ search that finds a match returns {"found": True, "issue": {...}}."""
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = "fake"
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 1, "items": [{"number": 42, "html_url": "http://gh/42"}]}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    result = exporter._search_github_for_marker("key123")
    assert result["found"] is True
    assert result["issue"]["github_issue_number"] == 42

def test_export_with_stale_marker_not_on_github(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')
    # Mock search returns zero results, then POST succeeds
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def post(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"number": 99, "html_url": "http://gh/99"}
                status_code = 201
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter.export(REVIEW_RECORD)
    # Search found zero results → stale marker deleted → retry → POST succeeds
    assert result["status"] == "created"

def test_recover_pending_marker_missing_date(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending"}')
    # Missing date triggers timed_out=True. dry_run search returns None (unknown state),
    # so reconciliation preserves the marker and returns error_recoverable.
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert marker_path.exists()

def test_recover_pending_marker_corrupted_json(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("{not valid json")
    # Corrupted marker goes to _reconcile_with_github. dry_run search → None → error_recoverable
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert marker_path.exists()

def test_recover_pending_marker_invalid_date(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    
    # Test 1: Bad date string (ValueError)
    marker_path.write_text('{"status": "pending", "created_at": "bad-date-string"}')
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    
    # Test 2: Integer timestamp instead of ISO string (TypeError during parse)
    marker_path.unlink()
    marker_path.write_text('{"status": "pending", "created_at": 1234567890}')
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    
    # Test 3: Timezone-naive ISO string (TypeError during subtraction)
    marker_path.unlink()
    marker_path.write_text('{"status": "pending", "created_at": "2026-08-30T12:00:00"}')
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"

def test_search_github_for_marker_request_exception(tmp_path):
    """Issue #26: network error during search returns None (distinct from {"found": False})."""
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = "fake"
    class MockSession:
        def get(self, *args, **kwargs):
            raise requests.RequestException("Network error")
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    # Network failure returns None (unknown remote state)
    assert exporter._search_github_for_marker("key123") is None

def test_export_no_token_cleans_up_marker(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    with pytest.raises(RuntimeError, match="token is required"):
        exporter.export(REVIEW_RECORD)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    # The pending marker should be cleaned up before raising (no POST attempted)
    assert not marker_path.exists()

def test_marker_body_contains_idempotency_marker(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    result = exporter.export(REVIEW_RECORD)
    assert f"<!-- threatsutra-marker:{key} -->" in result["body"]

def test_failed_github_post_preserves_pending_marker(tmp_path, monkeypatch):
    """Issue #26: after a failed POST, the pending marker must be preserved because the
    POST may have succeeded (network error on response). Future recovery will reconcile."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)

    class MockSession:
        def post(self, *args, **kwargs):
            raise requests.RequestException("GitHub is down")
        def mount(self, *args, **kwargs):
            pass

    exporter.session = MockSession()

    with pytest.raises(RuntimeError, match="GitHub is down"):
        exporter.export(REVIEW_RECORD)

    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    assert marker_path.exists()
    saved = json.loads(marker_path.read_text())
    assert saved["status"] == "pending"
    assert "schema_version" in saved
    assert saved["schema_version"] == "2"
    assert "created_at" in saved
    # Ensure it looks like an ISO format timestamp
    from datetime import datetime
    assert datetime.fromisoformat(saved["created_at"])

# new tests for schema_version, crash recovery, search distinction ----

def test_pending_marker_includes_schema_version(tmp_path, monkeypatch):
    """Issue #26: every pending marker must include schema_version and created_at."""
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    # export will fail because no token, but the pending marker is written first
    with pytest.raises(RuntimeError):
        exporter.export(REVIEW_RECORD)
    # In this case the marker is cleaned up before raise.  Use dry_run instead:
    exporter2 = make_exporter(tmp_path, dry_run=True)
    # Peek at the pending marker by intercepting before unlink
    key = exporter2._idempotency_key(REVIEW_RECORD)
    marker_path = exporter2._marker_path(key)
    pending_content = json.dumps({
        "status": "pending",
        "created_at": "2026-08-28T00:00:00+00:00",
        "schema_version": MARKER_SCHEMA_VERSION,
    })
    marker_path.write_text(pending_content)
    data = json.loads(marker_path.read_text())
    assert data["schema_version"] == MARKER_SCHEMA_VERSION
    assert "created_at" in data
    assert data["status"] == "pending"

def test_malformed_marker_before_recovery_does_not_crash(tmp_path):
    """ malformed JSON (or valid JSON that isn't a dict) doesn't crash."""
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    
    # Test 1: Completely invalid JSON
    marker_path.write_text("THIS IS NOT JSON AT ALL!!!")
    # dry_run recovery: malformed → reconcile → search(dry_run) returns None → error_recoverable
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"

    # Test 2: Valid JSON but not a dictionary (Issue #4)
    marker_path.unlink()
    marker_path.write_text('["this", "is", "a", "list"]')
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"

def test_search_failure_preserves_pending_marker(tmp_path, monkeypatch):
    """  if search fails with a network error, the pending marker must be preserved."""
    from datetime import datetime, timezone, timedelta
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')

    class MockSession:
        def get(self, *args, **kwargs):
            raise requests.RequestException("DNS failure")
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert result["reason"] == "search_failed"
    # Marker MUST still exist
    assert marker_path.exists()

def test_search_success_zero_results_deletes_stale_marker(tmp_path, monkeypatch):
    """Issue #26: search succeeds with zero results → safe to delete stale marker and retry."""
    from datetime import datetime, timezone, timedelta
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')

    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter._reconcile_with_github(marker_path, key, REVIEW_RECORD)
    assert result is None
    # After reconciliation, marker exists with fresh pending status
    assert marker_path.exists()
    fresh = json.loads(marker_path.read_text())
    assert fresh["status"] == "pending"
    assert fresh["schema_version"] == MARKER_SCHEMA_VERSION

def test_search_success_with_hit_reconciles(tmp_path, monkeypatch):
    """ search succeeds and finds issue → write completed marker."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = "fake"
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending"}')

    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self):
                    return {"total_count": 1, "items": [{"number": 77, "html_url": "http://gh/77"}]}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter._reconcile_with_github(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "already_exported"
    assert result["marker"]["github_issue_number"] == 77
    # Marker on disk should be the completed marker
    saved = json.loads(marker_path.read_text())
    assert saved["schema_version"] == MARKER_SCHEMA_VERSION

def test_unsupported_schema_version_triggers_reconciliation(tmp_path):
    """ unsupported schema version marker → reconcile via GitHub search."""
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending", "schema_version": "999", "created_at": "2026-01-01T00:00:00+00:00"}')
    # dry_run → search returns None → error_recoverable, marker preserved
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert marker_path.exists()

def test_completed_marker_includes_schema_version(tmp_path, monkeypatch):
    """ completed markers must persist schema_version."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    from unittest.mock import MagicMock
    session = MagicMock(spec=requests.Session)
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 201
    resp.json.return_value = {"number": 42, "html_url": "http://gh/42"}
    resp.raise_for_status = MagicMock()
    session.post.return_value = resp
    exporter = GitHubIssueExporter(repo="owner/repo", dry_run=False, markers_dir=str(tmp_path), session=session)
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "created"
    assert result["marker"]["schema_version"] == MARKER_SCHEMA_VERSION
    key = exporter._idempotency_key(REVIEW_RECORD)
    saved = json.loads(exporter._marker_path(key).read_text())
    assert saved["schema_version"] == MARKER_SCHEMA_VERSION

def test_dry_run_search_returns_none(tmp_path):
    """Issue #26: dry_run search returns None (unknown remote state), not {"found": False}."""
    exporter = make_exporter(tmp_path, dry_run=True)
    result = exporter._search_github_for_marker("key123")
    assert result is None

def test_no_token_search_returns_none(tmp_path, monkeypatch):
    """Issue #26: no-token search returns None (unknown remote state), not {"found": False}."""
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = None
    result = exporter._search_github_for_marker("key123")
    assert result is None

def test_malformed_marker_with_search_failure_returns_error_recoverable(tmp_path, monkeypatch):
    """ malformed marker in FileExistsError path + search failure →
    recovery returns error_recoverable through the except JSONDecodeError branch."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("CORRUPT MARKER FILE")

    class MockSession:
        def get(self, *args, **kwargs):
            raise requests.RequestException("DNS failure")
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert result["reason"] == "search_failed"
    # Marker must still exist (preserved for future recovery)
    assert marker_path.exists()

def test_malformed_marker_with_search_zero_results_retries_and_creates(tmp_path, monkeypatch):
    """Covers lines 225-226: malformed marker in except JSONDecodeError, search succeeds
    with zero results → recovery returns None → overwrite with fresh pending → POST succeeds."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("CORRUPT MARKER FILE")

    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def post(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"number": 88, "html_url": "http://gh/88"}
                status_code = 201
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "created"
    assert result["marker"]["github_issue_number"] == 88

@pytest.mark.parametrize("mock_response_data", [
    [],  # Not a dict (line 109)
    {"total_count": 1, "items": {}},  # items not a list (line 117)
    {"total_count": 1, "items": []},  # items empty (line 117)
    {"total_count": 1, "items": ["not an object"]},  # item not dict (line 121)
    {"total_count": 1, "items": [{"number": 1}]},  # missing html_url (line 126)
    {"total_count": 1, "items": [{"html_url": "url"}]},  # missing number (line 126)
])
def test_search_github_for_marker_bad_shapes(tmp_path, monkeypatch, mock_response_data):
    """Issue #26: Handle unexpected GitHub API JSON shapes defensively."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    
    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return mock_response_data
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter._search_github_for_marker("key123")
    assert result is None

def test_concurrent_race_in_reconcile_returns_error_recoverable(tmp_path, monkeypatch):
    """Issue #56: If another process holds the ExportLock for this key,
    export() must get error_recoverable/concurrent_lock immediately."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending"}')

    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    # Simulate: another process already holds the OS lock
    blocker = ExportLock(exporter._lock_path(key))
    blocker.acquire()
    try:
        result = exporter.export(REVIEW_RECORD)
        assert result["status"] == "error_recoverable"
        assert result["reason"] == "concurrent_lock"
    finally:
        blocker.release()

def test_concurrent_lock_sequential_interleave(tmp_path, monkeypatch):
    """Issue #56: Two sequential calls — the first export() acquires the
    ExportLock and proceeds; while the lock is held, the second export()
    gets error_recoverable/concurrent_lock."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)

    # Simulate: first process already holds the ExportLock
    blocker = ExportLock(exporter._lock_path(key))
    blocker.acquire()
    try:
        # Second process: lock is held, cannot proceed
        result = exporter.export(REVIEW_RECORD)
        assert result["status"] == "error_recoverable"
        assert result["reason"] == "concurrent_lock"
    finally:
        blocker.release()

    # After release, export should proceed (dry_run=False needs a mock session for POST)
    class MockSession:
        def post(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": 42, "html_url": "http://gh/42"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    result2 = exporter.export(REVIEW_RECORD)
    assert result2["status"] == "created"

def test_interleaved_recovery_thread_safety(tmp_path):
    """Issue #56: Thread-level test — two threads both try to export the same
    artifact.  The ExportLock ensures only one acquires the OS lock and
    proceeds to POST; the other must get concurrent_lock immediately."""
    import threading
    from datetime import datetime, timezone, timedelta

    post_count = [0]
    post_lock = threading.Lock()
    results = [None, None]
    barrier = threading.Barrier(2)

    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    # Pre-create stale marker
    setup = GitHubIssueExporter(
        repo="owaspcornucopia/ThreatSutra", token="fake-token",
        dry_run=False, markers_dir=str(tmp_path),
    )
    key = setup._idempotency_key(REVIEW_RECORD)
    marker_path = setup._marker_path(key)
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')

    class CountingSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return R()
        def post(self, *args, **kwargs):
            with post_lock:
                post_count[0] += 1
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": 42, "html_url": "http://gh/42"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass

    def worker(idx):
        exp = GitHubIssueExporter(
            repo="owaspcornucopia/ThreatSutra", token="fake-token",
            dry_run=False, markers_dir=str(tmp_path),
            session=CountingSession(),
        )
        barrier.wait()
        try:
            results[idx] = exp.export(REVIEW_RECORD)
        except (RuntimeError, ValidationError, requests.RequestException) as exc:
            results[idx] = {"status": "error", "reason": str(exc)}

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    statuses = [r["status"] for r in results]
    # At most one POST must have been made
    assert post_count[0] == 1, f"Expected exactly 1 POST, got {post_count[0]}"
    assert statuses.count("created") == 1
    assert statuses.count("already_exported") + statuses.count("error_recoverable") == 1

@pytest.mark.parametrize("incomplete_marker", [
    {},  # Empty dict
    {"status": "completed"},  # Missing all required fields
    {"github_issue_url": "http://gh/1"},  # Missing number, key, schema
    {"github_issue_number": 1, "github_issue_url": "http://gh/1"},  # Missing key, schema
    # Type validation — these have all keys but wrong types/values:
    {"github_issue_number": "1", "github_issue_url": "http://gh/1",
     "schema_version": "2", "idempotency_key": "k"},  # number is str not int
    {"github_issue_number": 1, "github_issue_url": "",
     "schema_version": "2", "idempotency_key": "k"},  # empty URL
    {"github_issue_number": 1, "github_issue_url": "http://gh/1",
     "schema_version": "999", "idempotency_key": "k"},  # wrong schema version
])
def test_incomplete_completed_marker_triggers_reconciliation(tmp_path, incomplete_marker):
    """Issue #26: A completed marker with missing required fields or wrong types
    must NOT be accepted as already_exported. It must trigger reconciliation."""
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text(json.dumps(incomplete_marker))
    # dry_run → reconciliation → search returns None → error_recoverable
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"

def test_search_github_invalid_json_body_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)

    class MockSession:
        def get(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): raise ValueError("Invalid JSON")
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter._search_github_for_marker("key123")
    assert result is None

def test_post_invalid_json_response_preserves_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)

    class MockSession:
        def post(self, *args, **kwargs):
            class MockResponse:
                def raise_for_status(self): pass
                def json(self): raise ValueError("Invalid JSON")
                status_code = 201
            return MockResponse()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()

    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert result["reason"] == "invalid_post_response"

def test_idempotency_key_revision_policy(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    record1 = {**REVIEW_RECORD, "text": "A", "model": "gemini-1.5", "prompt_template_version": "v1"}
    record2 = {**REVIEW_RECORD, "text": "B", "model": "gemini-1.5-pro", "prompt_template_version": "v2"}
    assert exporter._idempotency_key(record1) == exporter._idempotency_key(record2)

    record3 = {**REVIEW_RECORD, "source_threat_id": "different"}
    assert exporter._idempotency_key(record1) != exporter._idempotency_key(record3)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits not enforced on Windows; ACL is the relevant mechanism")
def test_export_lock_file_permissions(tmp_path):
    """Issue #56: Lock file must be created with restrictive 0o600 permissions on POSIX."""
    import stat
    lock_path = tmp_path / "perm_test.lock"
    lock = ExportLock(lock_path)
    lock.acquire()
    try:
        mode = stat.S_IMODE(lock_path.stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
    finally:
        lock.release()


def test_export_lock_release_is_idempotent(tmp_path):
    """Calling release() twice must not raise."""
    lock = ExportLock(tmp_path / "idempotent.lock")
    lock.acquire()
    lock.release()
    lock.release()  # must be a no-op


def test_export_lock_context_manager(tmp_path):
    """ExportLock as context manager must acquire on enter and release on exit."""
    lock_path = tmp_path / "ctx.lock"
    with ExportLock(lock_path) as lock:
        assert lock.held
    assert not lock.held


def test_export_lock_contention(tmp_path):
    """Two ExportLock instances on the same path — second must raise LockException."""
    import portalocker.exceptions
    lock_path = tmp_path / "contention.lock"
    a = ExportLock(lock_path)
    a.acquire()
    try:
        b = ExportLock(lock_path)
        with pytest.raises(portalocker.exceptions.LockException):
            b.acquire()
    finally:
        a.release()


# ---- Coverage tests for error/edge branches ----

def test_export_lock_acquire_fdopen_failure(tmp_path, monkeypatch):
    """Cover line 64: os.close(fd) when fdopen itself fails."""
    lock_path = tmp_path / "fdopen_fail.lock"
    # Make os.fdopen raise so the raw fd path (line 64) is hit
    monkeypatch.setattr("os.fdopen", lambda fd, *a, **k: (_ for _ in ()).throw(OSError("fdopen failed")))
    lock = ExportLock(lock_path)
    with pytest.raises(OSError, match="fdopen failed"):
        lock.acquire()
    assert lock._file is None


def test_export_lock_release_unlock_failure(tmp_path, monkeypatch):
    """Cover lines 78-79: portalocker.unlock raises during release."""
    import portalocker
    lock_path = tmp_path / "unlock_fail.lock"
    lock = ExportLock(lock_path)
    lock.acquire()
    # Monkeypatch portalocker.unlock to raise
    monkeypatch.setattr(portalocker, "unlock", lambda f: (_ for _ in ()).throw(OSError("unlock failed")))
    # release() should log warning but not raise, and should close the file
    lock.release()
    assert lock._file is None


def test_atomic_write_exception_cleans_temp(tmp_path):
    """Cover lines 164-167: _atomic_write exception branch cleans up temp file."""
    from unittest.mock import patch
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    # Write existing content
    marker_path.write_text('{"old": true}')
    with patch("os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            exporter._atomic_write(marker_path, '{"new": true}')
    # Original content preserved, no temp files left
    assert marker_path.read_text() == '{"old": true}'
    assert list(tmp_path.glob(".tmp_*")) == []


def test_search_invalid_total_count_returns_none(tmp_path, monkeypatch):
    """Cover line 211: _search_github_for_marker returns None for non-int total_count."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    class MockSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"total_count": "not_an_int"}
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    result = exporter._search_github_for_marker(key)
    assert result is None


def test_reconcile_atomic_write_oserror(tmp_path, monkeypatch):
    """Cover lines 285-286: _reconcile_with_github returns io_error when _atomic_write raises OSError."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    # Pre-create a stale pending marker without phase (triggers reconcile)
    marker_path.write_text(json.dumps({"status": "pending", "created_at": "2020-01-01T00:00:00+00:00"}))
    # Mock search to return 0 results (so reconcile tries to write fresh pending)
    class MockSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    # Patch _atomic_write to raise OSError only when writing the fresh pending marker
    original_aw = type(exporter)._atomic_write
    call_count = [0]
    def failing_aw(self, path, content):
        call_count[0] += 1
        if '"phase": "pre_post"' in content:
            raise OSError("disk full")
        return original_aw(self, path, content)
    monkeypatch.setattr(type(exporter), "_atomic_write", failing_aw)
    result = exporter._reconcile_with_github(marker_path, key, REVIEW_RECORD)
    assert result == {"status": "error_recoverable", "reason": "io_error"}


def test_post_response_non_dict_body(tmp_path, monkeypatch):
    """Cover line 431: POST response.json() returns a non-dict (e.g., list)."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    class MockSession:
        def post(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return ["not", "a", "dict"]
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert result["reason"] == "invalid_post_response"


def test_post_response_invalid_number_or_url(tmp_path, monkeypatch):
    """Cover line 441: POST response has invalid number or html_url."""
    monkeypatch.setenv("GITHUB_API", "fake-token")
    exporter = make_exporter(tmp_path, dry_run=False)
    class MockSession:
        def post(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": "not_int", "html_url": "http://gh/1"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass
    exporter.session = MockSession()
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "error_recoverable"
    assert result["reason"] == "invalid_post_response"


# ---- Cross-process regression test (Issue #56) ----
def _mp_worker_export_crash(markers_dir, review_record, ready_flag_path, crash_phase, post_count_path):
    import time
    from pathlib import Path
    from src.adapters.GitHubIssueExporter import GitHubIssueExporter

    class CrashSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self): return {"total_count": 0}
            return R()
        def post(self, *args, **kwargs):
            with open(post_count_path, "a") as f:
                f.write("POST\n")
            if crash_phase == "post_attempted":
                Path(ready_flag_path).write_text("ready")
                time.sleep(999) # block forever until SIGKILL
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": 99, "html_url": "http://gh/99"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass

    class CrashExporter(GitHubIssueExporter):
        def _atomic_write(self, path: Path, content: str) -> None:
            super()._atomic_write(path, content)
            if crash_phase == "pre_post" and '"phase": "pre_post"' in content:
                Path(ready_flag_path).write_text("ready")
                time.sleep(999) # block forever until SIGKILL

    exp = CrashExporter(
        repo="owaspcornucopia/ThreatSutra", token="fake-token",
        dry_run=False, markers_dir=markers_dir,
        session=CrashSession(),
    )
    exp.export(review_record)

def _mp_worker_export_recover(markers_dir, review_record, result_path, post_count_path, crash_phase):
    import json as _json
    from pathlib import Path
    from src.adapters.GitHubIssueExporter import GitHubIssueExporter
    class StubSession:
        def get(self, *args, **kwargs):
            class R:
                def raise_for_status(self): pass
                def json(self):
                    if crash_phase == "post_attempted":
                        return {"total_count": 1, "items": [{"number": 99, "html_url": "http://gh/99"}]}
                    return {"total_count": 0}
            return R()
        def post(self, *args, **kwargs):
            with open(post_count_path, "a") as f:
                f.write("POST\n")
            class R:
                def raise_for_status(self): pass
                def json(self): return {"number": 99, "html_url": "http://gh/99"}
                status_code = 201
            return R()
        def mount(self, *args, **kwargs): pass
    exp = GitHubIssueExporter(
        repo="owaspcornucopia/ThreatSutra", token="fake-token",
        dry_run=False, markers_dir=markers_dir, session=StubSession()
    )
    result = exp.export(review_record)
    Path(result_path).write_text(_json.dumps(result))

def test_cross_process_export_lock_crash_recovery_post_attempted(tmp_path):
    import multiprocessing, time, json, sys
    for _ in range(20):
        # Clean state for each iteration
        for child in tmp_path.iterdir():
            if child.is_file():
                child.unlink()
        
        ready_flag = tmp_path / "a_ready.flag"
        result_b_path = tmp_path / "result_b.json"
        post_count_path = tmp_path / "post_count.txt"
        post_count_path.write_text("")
        
        proc_a = multiprocessing.Process(
            target=_mp_worker_export_crash,
            args=(str(tmp_path), REVIEW_RECORD, str(ready_flag), "post_attempted", str(post_count_path)),
        )
        proc_a.start()
        
        for _ in range(100):
            if ready_flag.exists():
                break
            time.sleep(0.05)
        assert ready_flag.exists()
        
        proc_a.kill()
        proc_a.join(timeout=10)
        if sys.platform != "win32":
            assert proc_a.exitcode < 0
        
        proc_b = multiprocessing.Process(
            target=_mp_worker_export_recover,
            args=(str(tmp_path), REVIEW_RECORD, str(result_b_path), str(post_count_path), "post_attempted"),
        )
        proc_b.start()
        proc_b.join(timeout=10)
        
        result_b = json.loads(result_b_path.read_text())
        assert result_b["status"] == "already_exported"
        
        post_lines = [line for line in post_count_path.read_text().splitlines() if line]
        assert len(post_lines) == 1, f"Expected 1 POST, got {len(post_lines)}"

def test_cross_process_export_lock_crash_recovery_pre_post(tmp_path):
    import multiprocessing, time, json, sys
    for _ in range(20):
        for child in tmp_path.iterdir():
            if child.is_file():
                child.unlink()
        
        ready_flag = tmp_path / "a_ready.flag"
        result_b_path = tmp_path / "result_b.json"
        post_count_path = tmp_path / "post_count.txt"
        post_count_path.write_text("")
        
        proc_a = multiprocessing.Process(
            target=_mp_worker_export_crash,
            args=(str(tmp_path), REVIEW_RECORD, str(ready_flag), "pre_post", str(post_count_path)),
        )
        proc_a.start()
        
        for _ in range(100):
            if ready_flag.exists():
                break
            time.sleep(0.05)
        assert ready_flag.exists()
        
        proc_a.kill()
        proc_a.join(timeout=10)
        if sys.platform != "win32":
            assert proc_a.exitcode < 0
        
        proc_b = multiprocessing.Process(
            target=_mp_worker_export_recover,
            args=(str(tmp_path), REVIEW_RECORD, str(result_b_path), str(post_count_path), "pre_post"),
        )
        proc_b.start()
        proc_b.join(timeout=10)
        
        result_b = json.loads(result_b_path.read_text())
        assert result_b["status"] == "created"
        
        post_lines = [line for line in post_count_path.read_text().splitlines() if line]
        assert len(post_lines) == 1, f"Expected 1 POST, got {len(post_lines)}"
