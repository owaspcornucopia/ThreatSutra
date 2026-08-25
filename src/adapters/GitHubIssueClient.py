"""
Fetches GitHub issues linked to a threat.For relevance scoring, the system must analyze the actual
linked GitHub issues, not just the threat and card data. This client fetches only the required data (title and body) from each issue
to support that analysis. It does not fetch comments or extra metadata.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.validation import validate_github_issue_reference

ISSUE_URL_PATTERN = re.compile(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)")
DEFAULT_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)

class GitHubIssueClient:
    """Fetches and validates referenced GitHub issues, by URL, with per-instance caching."""
    def __init__(self, token: str = None, timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 session: requests.Session = None, allowed_repos=None):
        self.allowed_repos = frozenset(allowed_repos) if allowed_repos else frozenset()
        self.token = token or os.environ.get("GITHUB_API")
        self.timeout = timeout
        self._cache = {}
        self.session = session or requests.Session()
        retry = Retry(
            total=RETRY_TOTAL,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_issue(self, issue_url: str) -> dict:
        """Fetches one issue's title and body by its GitHub URL. Read-only - never comments.Includes an allowlist check for the repository."""
        if issue_url in self._cache:
            return dict(self._cache[issue_url])
        match = ISSUE_URL_PATTERN.match(issue_url)
        if not match:
            raise ValueError(f"'{issue_url}' is not a recognized GitHub issue URL.")
        repo, number = match.group(1), match.group(2)
        if self.allowed_repos and repo not in self.allowed_repos:
            raise ValueError(
                f"Repository '{repo}' is not in the configured allow-list "
                f"({sorted(self.allowed_repos)}). To read issues from additional "
                f"repositories, add them to allowed_repos.")
        url = f"https://api.github.com/repos/{repo}/issues/{number}"
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not fetch GitHub issue '{issue_url}': {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"GitHub issue response for '{issue_url}' was not valid JSON.") from exc
        issue = {
            "number": payload.get("number"),
            "title": payload.get("title") or "",
            "body": payload.get("body") or "",
            "url": issue_url,
        }
        validate_github_issue_reference(issue)
        issue["provenance"] = {
            "source_type": "github_issue",
            "location": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.sha256(
                json.dumps(issue, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        }
        self._cache[issue_url] = issue
        return dict(issue)

    def get_issues(self, issue_urls) -> list:
        """Fetches every linked issue. A single missing/inaccessible issue fails the whole
        batch closed - relevance scoring must not silently proceed on partial data."""
        return [self.get_issue(url) for url in issue_urls]