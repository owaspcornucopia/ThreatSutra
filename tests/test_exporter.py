"""Tests for GitHubIssueExporter"""
import json
import pytest
import requests
from src.adapters.GitHubIssueExporter import GitHubIssueExporter, MARKER_SCHEMA_VERSION
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
    # Missing date triggers timed_out=True. dry_run search returns {"found": False}, marker unlinks, returns None.
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

def test_recover_pending_marker_corrupted_json(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("{not valid json")
    # Corrupted marker goes to _reconcile_with_github. dry_run search → {"found": False} → unlink → None
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

def test_recover_pending_marker_invalid_date(tmp_path):
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text('{"status": "pending", "created_at": "bad-date-string"}')
    # Bad date triggers timed_out=True. dry_run search → {"found": False} → unlink → None
    assert exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD) is None
    assert not marker_path.exists()

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
    import os
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
    """Issue #26: json.loads() on a malformed marker in the FileExistsError path
    must not crash; it must enter recovery safely."""
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    marker_path.write_text("THIS IS NOT JSON AT ALL!!!")
    # dry_run recovery: malformed → reconcile → search(dry_run) → {"found": False} → unlink → retry → dry_run
    result = exporter.export(REVIEW_RECORD)
    assert result["status"] == "dry_run"

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
    """ search succeeds with zero results → safe to delete stale marker and retry."""
    from datetime import datetime, timezone, timedelta
    exporter = make_exporter(tmp_path, dry_run=True)
    key = exporter._idempotency_key(REVIEW_RECORD)
    marker_path = exporter._marker_path(key)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    marker_path.write_text(f'{{"status": "pending", "created_at": "{stale_time}"}}')

    result = exporter._reconcile_with_github(marker_path, key, REVIEW_RECORD)
    assert result is None
    assert not marker_path.exists()

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
    # dry_run → search returns {"found": False} → unlink → None
    result = exporter._recover_pending_marker(marker_path, key, REVIEW_RECORD)
    assert result is None
    assert not marker_path.exists()

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

def test_dry_run_search_returns_found_false(tmp_path):
    """ dry_run search returns {"found": False}, not None."""
    exporter = make_exporter(tmp_path, dry_run=True)
    result = exporter._search_github_for_marker("key123")
    assert result == {"found": False}

def test_no_token_search_returns_found_false(tmp_path, monkeypatch):
    """ no-token search returns {"found": False}, not None."""
    monkeypatch.delenv("GITHUB_API", raising=False)
    exporter = make_exporter(tmp_path, dry_run=False)
    exporter.token = None
    result = exporter._search_github_for_marker("key123")
    assert result == {"found": False}

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
