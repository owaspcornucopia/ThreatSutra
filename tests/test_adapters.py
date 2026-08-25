from unittest.mock import MagicMock

import pytest
import requests

from src.adapters.CornucopiaClient import CornucopiaClient
from src.adapters.CornucopiaExplanationClient import CornucopiaExplanationClient
from src.adapters.GitHubIssueClient import GitHubIssueClient
from src.adapters.GitHubIssueExporter import GitHubIssueExporter
from src.adapters.GitHubMilestoneClient import GitHubMilestoneClient


def make_mock_response(status_code=200, json_data=None, text="", links=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.text = text
    resp.links = links or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp

def test_cornucopia_valid_response():
    session = MagicMock(spec=requests.Session)
    json_data = {
        "meta": {"edition": "companion", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [
            {"sectionID": "LLM9", "name": "LLM9", "description": "Card desc."}
        ]
    }
    session.get.return_value = make_mock_response(json_data=json_data)
    client = CornucopiaClient(session=session)
    card = client.find_card("companion", "LLM9")
    assert card["sectionID"] == "LLM9"
    assert card["description"] == "Card desc."

def test_cornucopia_invalid_json():
    session = MagicMock(spec=requests.Session)
    resp = make_mock_response(text="not json")
    resp.json.side_effect = requests.exceptions.JSONDecodeError("msg", "doc", 0)
    session.get.return_value = resp
    client = CornucopiaClient(session=session)
    with pytest.raises(RuntimeError):
        client.find_card("companion", "LLM9")

def test_cornucopia_non_200():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = make_mock_response(status_code=500)
    client = CornucopiaClient(session=session)
    with pytest.raises(RuntimeError):
        client.find_card("companion", "LLM9")

def test_cornucopia_missing_card():
    session = MagicMock(spec=requests.Session)
    json_data = {
        "meta": {"edition": "companion", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [
            {"sectionID": "LLM1", "name": "LLM1", "description": "Other."}
        ]
    }
    session.get.return_value = make_mock_response(json_data=json_data)
    client = CornucopiaClient(session=session)
    with pytest.raises(RuntimeError, match="No card"):
        client.find_card("companion", "LLM9")

def test_cornucopia_cache_prevents_second_get():
    session = MagicMock(spec=requests.Session)
    json_data = {
        "meta": {"edition": "companion", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [
            {"sectionID": "LLM9", "name": "LLM9", "description": "Card desc."}
        ]
    }
    session.get.return_value = make_mock_response(json_data=json_data)
    client = CornucopiaClient(session=session)
    client.find_card("companion", "LLM9")
    client.find_card("companion", "LLM9")
    session.get.assert_called_once()

def test_explanation_tree_lookup():
    session = MagicMock(spec=requests.Session)
    tree_data = {"tree": [{"path": "cornucopia.owasp.org/data/cards/companion-cards-1.0-en/Prompting/LLM9/explanation.md", "type": "blob"}], "truncated": False}
    md_text = "# VEK\n## Scenario\nAn attacker embeds instructions.\n## What can go wrong?\nThe model follows them.\n## What are we going to do about it?\nTreat external content as data."
    
    def side_effect(url, **kwargs):
        if "trees" in url:
            return make_mock_response(json_data=tree_data)
        else:
            return make_mock_response(text=md_text)
            
    session.get.side_effect = side_effect
    client = CornucopiaExplanationClient(session=session)
    exp = client.get_explanation("companion", "LLM9")
    assert exp["scenario"] == "An attacker embeds instructions."
    assert exp["what_can_go_wrong"] == "The model follows them."
    assert exp["requirement"] == "Treat external content as data."
    assert exp["mitigation"] == "Treat external content as data."

def test_explanation_missing_heading():
    session = MagicMock(spec=requests.Session)
    tree_data = {"tree": [{"path": "cornucopia.owasp.org/data/cards/companion-cards-1.0-en/Prompting/LLM9/explanation.md", "type": "blob"}], "truncated": False}
    md_text = "# VEK\n## Scenario\nAn attacker embeds instructions."
    
    def side_effect(url, **kwargs):
        if "trees" in url:
            return make_mock_response(json_data=tree_data)
        else:
            return make_mock_response(text=md_text)
            
    session.get.side_effect = side_effect
    client = CornucopiaExplanationClient(session=session)
    with pytest.raises(ValueError):
        client.get_explanation("companion", "LLM9")

def test_explanation_invalid_tree():
    session = MagicMock(spec=requests.Session)
    tree_data = {"tree": [], "truncated": True}
    session.get.return_value = make_mock_response(json_data=tree_data)
    client = CornucopiaExplanationClient(session=session)
    with pytest.raises(RuntimeError):
        client.get_explanation("companion", "LLM9")

def test_explanation_cache_prevents_repeated_fetch():
    session = MagicMock(spec=requests.Session)
    tree_data = {"tree": [{"path": "cornucopia.owasp.org/data/cards/companion-cards-1.0-en/Prompting/LLM9/explanation.md", "type": "blob"}], "truncated": False}
    md_text = "# VEK\n## Scenario\nAn attacker embeds instructions.\n## What can go wrong?\nThe model follows them.\n## What are we going to do about it?\nTreat external content as data."
    
    def side_effect(url, **kwargs):
        if "trees" in url:
            return make_mock_response(json_data=tree_data)
        else:
            return make_mock_response(text=md_text)
            
    session.get.side_effect = side_effect
    client = CornucopiaExplanationClient(session=session)
    client.get_explanation("companion", "LLM9")
    client.get_explanation("companion", "LLM9")
    assert session.get.call_count == 2 

def test_milestone_one_page():
    session = MagicMock(spec=requests.Session)
    json_data = [{"number": 1, "title": "Phase 1", "description": "First phase.", "state": "open"}]
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubMilestoneClient("repo/name", session=session)
    milestones = client.get_milestones()
    assert len(milestones) == 1
    assert milestones[0]["number"] == 1

def test_milestone_multiple_pages():
    session = MagicMock(spec=requests.Session)
    page1 = [{"number": 1, "title": "Phase 1", "description": "First phase.", "state": "open"}]
    page2 = [{"number": 2, "title": "Phase 2", "description": "Second phase.", "state": "open"}]
    
    resp1 = make_mock_response(json_data=page1, links={"next": {"url": "http://page2"}})
    resp2 = make_mock_response(json_data=page2)
    session.get.side_effect = [resp1, resp2]
    
    client = GitHubMilestoneClient("repo/name", session=session)
    milestones = client.get_milestones()
    assert len(milestones) == 2
    assert milestones[0]["number"] == 1
    assert milestones[1]["number"] == 2

def test_milestone_invalid_payload():
    session = MagicMock(spec=requests.Session)
    session.get.return_value = make_mock_response(json_data={"not": "a list"})
    client = GitHubMilestoneClient("repo/name", session=session)
    with pytest.raises(RuntimeError):
        client.get_milestones()

def test_milestone_timeout():
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("Timeout")
    client = GitHubMilestoneClient("repo/name", session=session)
    with pytest.raises(RuntimeError):
        client.get_milestones()

def test_milestone_missing():
    session = MagicMock(spec=requests.Session)
    json_data = [{"number": 1, "title": "Phase 1", "description": "First phase.", "state": "open"}]
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubMilestoneClient("repo/name", session=session)
    milestones = client.get_milestones()
    assert milestones[0]["number"] == 1

def test_issue_valid():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)
    issue = client.get_issue("https://github.com/repo/name/issues/5")
    assert issue["number"] == 5
    assert issue["body"] == "Issue body"

def test_issue_invalid_url():
    session = MagicMock(spec=requests.Session)
    client = GitHubIssueClient(session=session)
    with pytest.raises(ValueError):
        client.get_issue("not-a-github-url")

def test_issue_body_none():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": None, "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)
    issue = client.get_issue("https://github.com/repo/name/issues/5")
    assert issue["body"] == ""

def test_issue_cache_reuse():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)
    client.get_issue("https://github.com/repo/name/issues/5")
    client.get_issue("https://github.com/repo/name/issues/5")
    session.get.assert_called_once()

def test_issue_timeout():
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("Timeout")
    client = GitHubIssueClient(session=session)
    with pytest.raises(RuntimeError):
        client.get_issue("https://github.com/repo/name/issues/5")

def test_issue_client_allows_all_when_no_allowlist():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)  # no allowed_repos
    issue = client.get_issue("https://github.com/evil-org/evil-repo/issues/5")
    assert issue["number"] == 5

def test_issue_client_rejects_disallowed_repo():
    session = MagicMock(spec=requests.Session)
    client = GitHubIssueClient(session=session, allowed_repos=["owaspcornucopia/ThreatSutra"])
    with pytest.raises(ValueError, match="is not in the configured allow-list"):
        client.get_issue("https://github.com/evil-org/evil-repo/issues/5")

def test_issue_client_allows_configured_repo():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session, allowed_repos=["owaspcornucopia/ThreatSutra"])
    issue = client.get_issue("https://github.com/owaspcornucopia/ThreatSutra/issues/5")
    assert issue["number"] == 5

EXPORTER_REVIEW_RECORD = {
    "artifact_type": "evil_user_story",
    "text": "As an attacker, I want to inject instructions, so that I exfiltrate data.",
    "source_threat_id": "threat-1",
    "source_card_id": "LLM9",
    "source_milestone_number": 1,
    "decision": "approve",
    "timestamp": "2026-08-14T00:00:00+00:00",
}

def test_exporter_successful_post(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    session = MagicMock(spec=requests.Session)
    resp = make_mock_response(status_code=201, json_data={"number": 42, "html_url": "http://new-issue/42"})
    session.post.return_value = resp
    exporter = GitHubIssueExporter(repo="owner/repo", dry_run=False, markers_dir=str(tmp_path), session=session)
    result = exporter.export(EXPORTER_REVIEW_RECORD)
    assert result["status"] == "created"
    session.post.assert_called_once()

def test_exporter_github_post_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_API", "fake-token")
    session = MagicMock(spec=requests.Session)
    session.post.side_effect = requests.RequestException("GitHub is down")
    exporter = GitHubIssueExporter(repo="owner/repo", dry_run=False, markers_dir=str(tmp_path), session=session)
    with pytest.raises(RuntimeError, match="GitHub is down"):
        exporter.export(EXPORTER_REVIEW_RECORD)

# --- Additional coverage tests ---

def test_cornucopia_unsupported_edition():
    session = MagicMock(spec=requests.Session)
    client = CornucopiaClient(session=session)
    with pytest.raises(ValueError, match="Unknown Cornucopia edition"):
        client.find_card("nonexistent_edition", "LLM9")

def test_cornucopia_empty_card_id():
    session = MagicMock(spec=requests.Session)
    client = CornucopiaClient(session=session)
    with pytest.raises(ValueError, match="card_id is required"):
        client.find_card("companion", "")

def test_cornucopia_get_card_provenance():
    session = MagicMock(spec=requests.Session)
    json_data = {
        "meta": {"edition": "companion", "component": "cards", "language": "en", "version": "1.0"},
        "standards": [
            {"sectionID": "LLM9", "name": "LLM9", "description": "Card desc."}
        ]
    }
    session.get.return_value = make_mock_response(json_data=json_data)
    client = CornucopiaClient(session=session)
    prov = client.get_card_provenance("companion")
    assert prov["source_type"] == "cornucopia_api"
    assert "api_version" in prov

def test_milestone_with_token(monkeypatch):
    monkeypatch.setenv("GITHUB_API", "test-token")
    session = MagicMock(spec=requests.Session)
    json_data = [{"number": 1, "title": "Phase 1", "description": "First phase.", "state": "open"}]
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubMilestoneClient("repo/name", session=session)
    milestones = client.get_milestones()
    assert len(milestones) == 1

def test_milestone_invalid_json():
    session = MagicMock(spec=requests.Session)
    resp = make_mock_response(text="not json")
    resp.json.side_effect = ValueError("No JSON")
    session.get.return_value = resp
    client = GitHubMilestoneClient("repo/name", session=session)
    with pytest.raises(RuntimeError, match="not valid JSON"):
        client.get_milestones()

def test_milestone_get_provenance_before_fetch():
    session = MagicMock(spec=requests.Session)
    client = GitHubMilestoneClient("repo/name", session=session)
    with pytest.raises(RuntimeError, match="unavailable before"):
        client.get_provenance()

def test_milestone_get_provenance_after_fetch():
    session = MagicMock(spec=requests.Session)
    json_data = [{"number": 1, "title": "Phase 1", "description": "First.", "state": "open"}]
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubMilestoneClient("repo/name", session=session)
    client.get_milestones()
    prov = client.get_provenance()
    assert prov["source_type"] == "github_milestones"

def test_issue_client_with_token(monkeypatch):
    monkeypatch.setenv("GITHUB_API", "test-token")
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)
    issue = client.get_issue("https://github.com/repo/name/issues/5")
    assert issue["number"] == 5

def test_issue_client_invalid_json():
    session = MagicMock(spec=requests.Session)
    resp = make_mock_response(text="not json")
    resp.json.side_effect = ValueError("No JSON")
    session.get.return_value = resp
    client = GitHubIssueClient(session=session)
    with pytest.raises(RuntimeError, match="not valid JSON"):
        client.get_issue("https://github.com/repo/name/issues/5")

def test_issue_client_get_issues():
    session = MagicMock(spec=requests.Session)
    json_data = {"number": 5, "title": "Issue title", "body": "Issue body", "html_url": "http://issue/5"}
    session.get.return_value = make_mock_response(json_data=json_data)
    client = GitHubIssueClient(session=session)
    issues = client.get_issues(["https://github.com/repo/name/issues/5"])
    assert len(issues) == 1

# --- CornucopiaExplanationClient coverage tests ---

def test_explanation_tree_cache_hit():
    """Line 63: second call returns cached tree."""
    session = MagicMock(spec=requests.Session)
    client = CornucopiaExplanationClient(session=session)
    client._tree = [{"type": "blob", "path": "some/path"}]
    result = client._get_tree()
    assert result == [{"type": "blob", "path": "some/path"}]
    session.get.assert_not_called()

def test_explanation_tree_request_error():
    """Lines 69-70: RequestException from _get_tree."""
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("network failure")
    client = CornucopiaExplanationClient(session=session)
    with pytest.raises(RuntimeError, match="Could not retrieve"):
        client._get_tree()

def test_explanation_tree_invalid_json():
    """Lines 71-72: ValueError from response.json() in _get_tree."""
    session = MagicMock(spec=requests.Session)
    resp = make_mock_response(text="not json")
    resp.json.side_effect = ValueError("No JSON")
    session.get.return_value = resp
    client = CornucopiaExplanationClient(session=session)
    with pytest.raises(RuntimeError, match="not valid JSON"):
        client._get_tree()

def test_explanation_tree_not_usable_list():
    """Line 77: tree is not a list."""
    session = MagicMock(spec=requests.Session)
    session.get.return_value = make_mock_response(json_data={"truncated": False, "tree": "not a list"})
    client = CornucopiaExplanationClient(session=session)
    with pytest.raises(RuntimeError, match="not a usable list"):
        client._get_tree()

def test_explanation_unsupported_edition():
    """Line 84: no directory configured for edition."""
    session = MagicMock(spec=requests.Session)
    client = CornucopiaExplanationClient(session=session)
    client._tree = []
    with pytest.raises(ValueError, match="No explanation repository directory"):
        client._find_explanation_path("nonexistent", "LLM9")

def test_explanation_no_match_found():
    """Line 93: no matching explanation.md in tree."""
    session = MagicMock(spec=requests.Session)
    client = CornucopiaExplanationClient(session=session)
    client._tree = [{"type": "blob", "path": "some/other/file.md"}]
    with pytest.raises(RuntimeError, match="Expected exactly one"):
        client._find_explanation_path("companion", "LLM9")

def test_explanation_fetch_error():
    """Lines 140-141: RequestException from get_explanation fetch."""
    session = MagicMock(spec=requests.Session)
    client = CornucopiaExplanationClient(session=session)
    client._tree = [{
        "type": "blob",
        "path": "cornucopia.owasp.org/data/cards/companion-cards-1.0-en/some-folder/LLM9/explanation.md"
    }]
    session.get.side_effect = requests.RequestException("download failed")
    with pytest.raises(RuntimeError, match="Could not retrieve Cornucopia explanation"):
        client.get_explanation("companion", "LLM9")
