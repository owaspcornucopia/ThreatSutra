"""
cornucopia.py 
Client for retrieving OWASP Cornucopia cards. Uses the Cornucopia API to retrieve all standards for a given edition
and performs card lookups from the cached response. Cards are located by matching the supplied identifier against the
returned standards. 
"""
import hashlib
import json
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.validation import validate_card, validate_cornucopia_response
BASE_URL = "https://cornucopia.owasp.org/api"
DEFAULT_LANGUAGE = "en"
REQUEST_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
# Every edition the API supports. See EDITION_BY_THREAT_TYPE in
# orchestrator.py for how a threat's `type` field selects one of these.
SUPPORTED_EDITIONS = {"webapp", "mobileapp", "companion", "dbd", "eop"}

class CornucopiaClient:
    """Retrieves and caches validated Cornucopia cards by edition, with retries and provenance."""

    def __init__(self, base_url: str = BASE_URL, language: str = DEFAULT_LANGUAGE,
                 timeout: int = REQUEST_TIMEOUT_SECONDS, session: requests.Session = None):
        self.base_url = base_url
        self.language = language
        self.timeout = timeout
        self._cards_by_edition = {}  # edition -> standards list, cached per instance
        self._provenance_by_edition = {}
        self.session = session or requests.Session()
        retry = Retry(total=RETRY_TOTAL, backoff_factor=RETRY_BACKOFF_FACTOR, status_forcelist=RETRY_STATUS_CODES, allowed_methods=frozenset({"GET"}),raise_on_status=False,)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_cards(self, edition: str) -> list:
        """
        Returns every card for one edition. Results are cached per client instance, so looking up several cards from the same
        edition only fetches that edition once. Issue #3: Full response envelope is validated (not just individual
       cards later), transient failures are retried, and retrieval metadata is kept for #11 provenance.
        """
        if edition not in SUPPORTED_EDITIONS:
            raise ValueError(f"Unknown Cornucopia edition '{edition}'.")
        if edition in self._cards_by_edition:
            return self._cards_by_edition[edition]
        url = f"{self.base_url}/cre/{edition}/{self.language}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not fetch Cornucopia edition '{edition}' from {url}: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Cornucopia API response for edition '{edition}' from {url} was not valid JSON.") from exc
        validate_cornucopia_response(payload)
        standards = payload["standards"]
        self._cards_by_edition[edition] = standards
        self._provenance_by_edition[edition] = {
            "source_type": "cornucopia_api",
            "location": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
            "api_version": payload["meta"]["version"],
        }
        return standards

    def get_card_provenance(self, edition: str) -> dict:
        """Returns retrieval metadata for a previously (or now) fetched Cornucopia edition. Used by #11."""
        self.get_cards(edition)
        return dict(self._provenance_by_edition[edition])

    def find_card(self, edition: str, card_id: str) -> dict:
        """
        Returns the Cornucopia card whose section identifier matches the supplied Threat Dragon card number.
        Raises a RuntimeError if no card is found.
        """
        if not card_id:
            raise ValueError("card_id is required to look up a Cornucopia card.")
        for card in self.get_cards(edition):
            if card.get("sectionID") == card_id:
                validate_card(card)
                return card
        raise RuntimeError(f"No card '{card_id}' found in Cornucopia edition '{edition}'.") 