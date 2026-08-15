"""
Retrieves GitHub milestone information.

This module provides read-only access to GitHub milestone data used as
project context during the ThreatSutra analysis pipeline.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.validation import validate_milestones

DEFAULT_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)

class GitHubMilestoneClient:
    """Fetches validated milestones for one GitHub repository."""
    def __init__(self, repo: str, token: str = None, timeout: int = DEFAULT_TIMEOUT_SECONDS, session: requests.Session = None):
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_API")
        self.timeout = timeout
        self._provenance = None
        self.session = session or requests.Session()
        retry = Retry(total=RETRY_TOTAL, backoff_factor=RETRY_BACKOFF_FACTOR, status_forcelist=RETRY_STATUS_CODES, allowed_methods=frozenset({"GET"}),raise_on_status=False,)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_milestones(self, state: str = "open") -> list:
        """
        Returns every matching milestone, paginated and validated. Milestone data is required context for generation, so failures raise 
        instead of silently returning [] — a missing milestone must stop the pipeline with a clear error, not continue with empty context."
        """
        url = f"https://api.github.com/repos/{self.repo}/milestones"
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        milestones = []
        params = {"state": state, "per_page": 100}
        while url:
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                page = response.json()
            except requests.RequestException as exc:
                raise RuntimeError(f"Could not fetch GitHub milestones for '{self.repo}': {exc}") from exc
            except ValueError as exc:
                raise RuntimeError(f"GitHub milestones response for '{self.repo}' was not valid JSON.") from exc
            if not isinstance(page, list):
                raise RuntimeError(f"GitHub milestones response for '{self.repo}' was not a JSON list.")
            milestones.extend(page)
            url = response.links.get("next", {}).get("url")
            params = None
        validate_milestones(milestones)
        self._provenance = {
            "source_type": "github_milestones",
            "location": f"https://api.github.com/repos/{self.repo}/milestones?state={state}",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.sha256(
                json.dumps(milestones, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        }
        return milestones

    def get_provenance(self) -> dict:
        """Returns provenance after get_milestones() has completed. Raises if called before get_milestones()."""
        if self._provenance is None:
            raise RuntimeError("Milestone provenance is unavailable before fetching milestones.")
        return dict(self._provenance)    
