"""
Fetches and extracts detailed Cornucopia card content.
The Cornucopia API only gives basic info like ID and description.
But for generation (issues #5, #6, #11), we also need:
- Scenario
- What can go wrong
- Mitigation / requirement
This data exists only in each card’s explanation.md in the Cornucopia repo.
So this adapter fetches that file, extracts only the needed sections,
and returns clean structured data (not raw Markdown).
"""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.validation import validate_explanation_sections

REPOSITORY = "OWASP/cornucopia"
BRANCH = "master"
API_BASE_URL = f"https://api.github.com/repos/{REPOSITORY}"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}"
REQUEST_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
MAX_REPOSITORY_TREE_ENTRIES = 100000

# Confirmed edition -> repository directory mapping (webapp confirmed via
# public source; companion confirmed via mentor-provided screenshot in the
# Codex conversation). Add new editions here if the DFD ever uses them.
EDITION_DIRECTORY_BY_EDITION = {
    "webapp": "webapp-cards-3.0-en",
    "companion": "companion-cards-1.0-en",
}

class CornucopiaExplanationClient:
    """Retrieves validated explanation sections for one mapped Cornucopia card."""
    def __init__(self, timeout: int = REQUEST_TIMEOUT_SECONDS, session: requests.Session = None):
        self.timeout = timeout
        self._tree = None
        self._explanations = {}
        self.session = session or requests.Session()
        retry = Retry(
            total=RETRY_TOTAL,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get_tree(self) -> list:
        """Fetches (once) and caches the full OWASP/cornucopia repository tree, used to
        locate each card's explanation.md without guessing folder-slug conventions."""
        if self._tree is not None:
            return self._tree
        url = f"{API_BASE_URL}/git/trees/{BRANCH}?recursive=1"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not retrieve Cornucopia repository tree from {url}: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Cornucopia repository tree from {url} was not valid JSON.") from exc
        if not isinstance(payload, dict) or payload.get("truncated") is True:
            raise RuntimeError("Cornucopia repository tree is truncated or malformed; cannot safely locate card explanations.")
        tree = payload.get("tree")
        if not isinstance(tree, list) or len(tree) > MAX_REPOSITORY_TREE_ENTRIES:
            raise RuntimeError("Cornucopia repository tree response was not a usable list.")
        self._tree = tree
        return self._tree

    def _find_explanation_path(self, edition: str, card_id: str) -> str:
        directory = EDITION_DIRECTORY_BY_EDITION.get(edition)
        if not directory:
            raise ValueError(f"No explanation repository directory is configured for edition '{edition}'.")
        prefix = f"cornucopia.owasp.org/data/cards/{directory}/"
        suffix = f"/{card_id}/explanation.md"
        matches = [
            entry["path"] for entry in self._get_tree()
            if entry.get("type") == "blob" and entry.get("path", "").startswith(prefix)
            and entry.get("path", "").endswith(suffix)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one explanation.md for card '{card_id}' in "
                f"Cornucopia edition '{edition}', found {len(matches)}."
            )
        return matches[0]
    @staticmethod
    def _parse_sections(markdown: str) -> dict:
        """Extracts only the named sections we need - the rest of the Markdown is discarded."""
        headings = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown, re.MULTILINE))
        expected = {
            "scenario": "scenario",
            "what_can_go_wrong": "what can go wrong",
            "requirement": "what are we going to do about it",
        }
        sections = {}
        for index, match in enumerate(headings):
            level = len(match.group(1))
            heading = match.group(2).strip().lower().rstrip(":?")
            section_name = next(
                (name for name, expected_heading in expected.items()
                 if heading == expected_heading or heading.startswith(f"{expected_heading}:")),
                None,
            )
            if not section_name:
                continue
            end = len(markdown)
            for following in headings[index + 1:]:
                if len(following.group(1)) <= level:
                    end = following.start()
                    break
            sections[section_name] = markdown[match.end():end].strip()
        if "requirement" in sections:
            # Cornucopia documents controls under "What are we going to do about
            # it?" - it is both the requirement source (#5) and mitigation guidance.
            sections["mitigation"] = sections["requirement"]
        return sections

    def get_explanation(self, edition: str, card_id: str) -> dict:
        """Returns validated scenario/what_can_go_wrong/requirement/mitigation text plus provenance."""
        cache_key = (edition, card_id)
        if cache_key in self._explanations:
            return dict(self._explanations[cache_key])
        path = self._find_explanation_path(edition, card_id)
        url = f"{RAW_BASE_URL}/{quote(path, safe='/')}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not retrieve Cornucopia explanation for card '{card_id}': {exc}") from exc
        markdown = response.text
        sections = self._parse_sections(markdown)
        validate_explanation_sections(sections)
        result = {
            "scenario": sections["scenario"],
            "what_can_go_wrong": sections["what_can_go_wrong"],
            "requirement": sections["requirement"],
            "mitigation": sections["mitigation"],
            "provenance": {
                "source_type": "cornucopia_explanation",
                "location": url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "content_hash": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                "source_heading": "What are we going to do about it?",
            },
        }
        self._explanations[cache_key] = result
        return dict(result)