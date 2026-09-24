"""
Exports approved artifacts as GitHub issues. Export happens only after human approval and when a write token is provided.
Without a write token, it automatically behaves as dry-run.
"""
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import portalocker
import portalocker.exceptions
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.validation import (
    sanitize_text,
    validate_export_artifact,
    validate_review_record,
)

DEFAULT_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
EXPORT_MARKERS_DIRNAME = "export_markers"
MARKER_SCHEMA_VERSION = "2"

ARTIFACT_TITLES = {
    "evil_user_story": "Evil user story",
    "verification_test": "Verification test",
}


class ExportLock:
    """Cross-platform per-key file lock using portalocker.

    Ownership is the open file handle itself — never a flag or a timestamp.
    The OS kernel releases the lock automatically if the process crashes.
    Release only operates on the same handle that acquired the lock.
    """

    def __init__(self, path: Path):
        self.path = path
        self._file = None

    def acquire(self) -> None:
        """Acquire an exclusive, non-blocking OS lock.

        Raises portalocker.exceptions.LockException if another process holds it.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            self._file = os.fdopen(fd, "a+")
            portalocker.lock(self._file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except BaseException:
            # If fdopen succeeded, close it (which also closes fd).
            # If fdopen failed, close the raw fd directly.
            if self._file is not None:
                self._file.close()
            else:
                os.close(fd)
            self._file = None
            raise

    def release(self) -> None:
        """Release the OS lock and close the file handle.

        Safe to call even if no lock is held (no-op).
        """
        if self._file is None:
            return 
        try:
            try:
                portalocker.unlock(self._file)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning("Failed to release lock at %s: %s", self.path, exc)
        finally:
            self._file.close()
            self._file = None

    @property
    def held(self) -> bool:
        """True if this instance currently holds the lock."""
        return self._file is not None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


class GitHubIssueExporter:
    """
    Creates one GitHub issue per approved artifact, idempotently. Runs live automatically once a write token is configured; otherwise
    runs in dry-run so nothing is silently skipped or misconfigured. Pass dry_run explicitly to force one mode regardless of token (ex: tests).
    """
    def __init__(self, repo: str, token: str = None, dry_run: bool = None,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS, session: requests.Session = None,
                 markers_dir: str = None):
        self.repo = repo
        # Deliberately a *separate* credential from GITHUB_API (read-only milestone/issue access) - least privilege for the write path.
        self.token = token or os.environ.get("GITHUB_API")
        """
         dry_run=None (the default) means "decide from whether a write token is configured" - this is what makes export actually live
        once credentials are provided, with no separate flag to remember to flip.
        """
        self.dry_run = (not self.token) if dry_run is None else dry_run
        self.timeout = timeout
        project_root = Path(__file__).resolve().parents[2]
        self.markers_dir = Path(markers_dir) if markers_dir else project_root / "outputs" / EXPORT_MARKERS_DIRNAME
        self.markers_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        retry = Retry(
            total=RETRY_TOTAL,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=frozenset({"POST"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _idempotency_key(self, review_record: dict) -> str:
        """Computes a stable export identity for one artifact.

        Revision policy (intentional product decision):
        The key is derived from (artifact_type, source_threat_id, source_card_id,
        source_milestone_number, MARKER_SCHEMA_VERSION).  Generated text, model
        name, and prompt-template version are deliberately excluded so that a
        later run can recover an interrupted export even when model output
        differs.  This also means a *revised* approved artefact for the same
        threat/card/milestone will resolve to the same key and short-circuit
        against the existing marker.  If revised content must produce a
        separate GitHub issue, the data model needs an additional revision
        identifier in the key basis.
        """
        basis = (
            f"{review_record['artifact_type']}:{review_record['source_threat_id']}:"
            f"{review_record['source_card_id']}:{review_record['source_milestone_number']}:"
            f"{MARKER_SCHEMA_VERSION}"
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def _marker_path(self, key: str) -> Path:
        return self.markers_dir / f"{key}.json"

    def _lock_path(self, key: str) -> Path:
        """Path for the per-key exclusive lock file."""
        return self.markers_dir / f"{key}.lock"

    def _atomic_write(self, path: Path, content: str) -> None:
        fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def _build_title_and_body(self, artifact: dict, key: str) -> tuple:
        label = ARTIFACT_TITLES[artifact["artifact_type"]]
        title = sanitize_text(f"[ThreatSutra] {label}: {artifact['text']}"[:250])
        body = sanitize_text(
            f"{artifact['text']}\n\n"
            "---\n"
            "_Generated by ThreatSutra and approved through the human review gate "
            " Not directly authored by a maintainer._\n\n"
            f"- Source threat: `{artifact['source_threat_id']}`\n"
            f"- Source card: `{artifact['source_card_id']}`\n"
            f"- Milestone: #{artifact['source_milestone_number']}\n"
            f"<!-- threatsutra-marker:{key} -->\n"
        )
        return title, body

    def _search_github_for_marker(self, key: str) -> dict | None:
        """
        Searches GitHub for an issue containing the given marker.
        Returns (three-state distinction):
          {"found": True, "issue": {...}}  – search succeeded, marker found on GitHub
          {"found": False}                 – search succeeded with zero results
          None                             – search failed, dry-run, or no token (remote state unknown)
        """
        if self.dry_run or not self.token:
            return None

        url = "https://api.github.com/search/issues"
        params = {"q": f"repo:{self.repo} is:issue in:body threatsutra-marker:{key}"}
        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}"}

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            try:
                data = response.json()
            except (ValueError, TypeError):
                return None  # HTTP 200 but body is not valid JSON — unknown state
            if not isinstance(data, dict):
                return None  # Invalid response format, treat as unknown

            total_count = data.get("total_count")
            if not isinstance(total_count, int) or isinstance(total_count, bool) or total_count < 0:
                return None
            if total_count == 0:
                return {"found": False}

            items = data.get("items", [])
            if not isinstance(items, list) or not items:
                return None  # Bad shape: claims count > 0 but no items array

            issue = items[0]
            if not isinstance(issue, dict):
                return None  # Bad shape: item is not an object

            number = issue.get("number")
            html_url = issue.get("html_url")
            if number is None or html_url is None:
                return None  # Missing essential fields

            return {
                "found": True,
                "issue": {
                    "github_issue_number": number,
                    "github_issue_url": html_url,
                },
            }
        except requests.RequestException:
            return None

    def _reconcile_with_github(self, marker_path: Path, key: str, review_record: dict) -> dict | None:
        """Reconciles a stale, malformed, or unsupported-version pending marker with GitHub.

        IMPORTANT: The caller MUST already hold the ExportLock for this key.
        This method does NOT acquire or release any lock.

        Returns:
          dict  – a terminal result (already_exported / error_recoverable).
          None  – search confirmed no remote issue exists; the stale marker has
                  been overwritten with a fresh pending marker.  The caller
                  should proceed to POST.
        """
        search_result = self._search_github_for_marker(key)

        if search_result is None:
            # Search failed — cannot determine remote state.
            # Preserve the marker so a future run can retry.
            return {"status": "error_recoverable", "reason": "search_failed"}

        if search_result.get("found"):
            github_data = search_result["issue"]
            marker = {
                "idempotency_key": key,
                "artifact_type": review_record["artifact_type"],
                "source_threat_id": review_record["source_threat_id"],
                "source_card_id": review_record["source_card_id"],
                "github_issue_number": github_data["github_issue_number"],
                "github_issue_url": github_data["github_issue_url"],
                "model": review_record.get("model"),
                "prompt_template_version": review_record.get("prompt_template_version"),
                "relevance": review_record.get("relevance"),
                "provenance": review_record.get("provenance"),
                "schema_version": MARKER_SCHEMA_VERSION,
            }
            self._atomic_write(marker_path, json.dumps(marker, indent=2))
            return {"status": "already_exported", "marker": marker}

        # Search succeeded, no match — overwrite the stale marker with a fresh
        # pending marker so the caller can POST.
        pending_content = json.dumps({
            "status": "pending",
            "phase": "pre_post",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": MARKER_SCHEMA_VERSION,
        })
        try:
            self._atomic_write(marker_path, pending_content)
        except OSError:
            return {"status": "error_recoverable", "reason": "io_error"}
        return None

    def _recover_pending_marker(self, marker_path: Path, key: str, review_record: dict) -> dict | None:
        """
        Attempts to recover a pending marker that might be stuck due to an interrupted export.
        Distinguishes malformed markers, unsupported versions, fresh in-flight markers,
        and stale markers — and only deletes after successful remote reconciliation.

        IMPORTANT: The caller MUST already hold the ExportLock for this key.
        """
        try:
            existing_marker = json.loads(marker_path.read_text())
            if not isinstance(existing_marker, dict):
                raise ValueError("JSON is valid but not a dictionary")
        except (json.JSONDecodeError, OSError, ValueError):
            # Malformed, non-dict, or unreadable marker — try remote reconciliation before deleting
            return self._reconcile_with_github(marker_path, key, review_record)

        # Handle unsupported schema versions explicitly
        marker_version = existing_marker.get("schema_version")
        if marker_version and marker_version != MARKER_SCHEMA_VERSION:
            return self._reconcile_with_github(marker_path, key, review_record)

        phase = existing_marker.get("phase")
        if phase == "pre_post":
            # The previous process crashed before POST. Safe to immediately retry.
            return None

        # phase is "post_attempted" or missing (legacy/corrupt). 
        # Ambiguous state! Must search GitHub.
        return self._reconcile_with_github(marker_path, key, review_record)

    def export(self, review_record: dict) -> dict:
        """
        Exports one artifact from its persisted review record. Note that:the exporter validates the record and independently checks
        decision == 'approve' itself, rather than trusting its caller. Returns a result dict describing what happened (dry_run /
        already_exported / created) - never raises for the "already exported" case, since that is the expected idempotent path.
        """
        validate_review_record(review_record)
        artifact = {
            "artifact_type": review_record["artifact_type"],
            "text": review_record["text"],
            "source_threat_id": review_record["source_threat_id"],
            "source_card_id": review_record["source_card_id"],
            "source_milestone_number": review_record["source_milestone_number"],
        }
        validate_export_artifact(artifact)
        key = self._idempotency_key(review_record)
        marker_path = self._marker_path(key)

        # --- Acquire per-key OS lock for the ENTIRE export window ---
        lock = ExportLock(self._lock_path(key))
        try:
            lock.acquire()
        except portalocker.exceptions.LockException:
            return {"status": "error_recoverable", "reason": "concurrent_lock"}

        try:
            # Check if a marker already exists on disk.
            if marker_path.exists():
                try:
                    marker_data = json.loads(marker_path.read_text())
                    if not isinstance(marker_data, dict):
                        raise ValueError("JSON is valid but not a dictionary")
                except (json.JSONDecodeError, OSError, ValueError):
                    # Malformed, non-dict, or unreadable existing marker — attempt recovery
                    recovered = self._recover_pending_marker(marker_path, key, review_record)
                    if recovered is not None:
                        return recovered
                    # Recovery returned None → proceed to POST
                else:
                    if marker_data.get("status") == "pending":
                        recovered = self._recover_pending_marker(marker_path, key, review_record)
                        if recovered is not None:
                            return recovered
                        # Recovery returned None → proceed to POST
                    else:
                        # Validate completed marker before accepting — a corrupt marker
                        # like {} or one missing required fields must NOT short-circuit
                        # as "already_exported" with no issue URL.  Also validate types
                        # and schema version to reject adversarial or incompatible data.
                        is_valid = (
                            isinstance(marker_data.get("github_issue_number"), int)
                            and isinstance(marker_data.get("github_issue_url"), str)
                            and marker_data["github_issue_url"]  # non-empty
                            and marker_data.get("schema_version") == MARKER_SCHEMA_VERSION
                            and marker_data.get("idempotency_key") == key
                        )
                        if is_valid:
                            return {"status": "already_exported", "marker": marker_data}
                        # Incomplete completed marker — reconcile with GitHub.
                        recovered = self._reconcile_with_github(marker_path, key, review_record)
                        if recovered is not None:
                            return recovered
                        # Reconcile returned None → proceed to POST
            else:
                # No marker exists — write a fresh pending marker.
                pending_content = json.dumps({
                    "status": "pending",
                    "phase": "pre_post",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "schema_version": MARKER_SCHEMA_VERSION,
                })
                self._atomic_write(marker_path, pending_content)

            # --- POST the GitHub issue ---
            title, body = self._build_title_and_body(artifact, key)
            if self.dry_run:
                marker_path.unlink(missing_ok=True)
                return {"status": "dry_run", "title": title, "body": body}
            if not self.token:
                marker_path.unlink(missing_ok=True)
                raise RuntimeError(
                    "GITHUB_API token is required for live export (see .env.example)."
                )

            attempted_content = json.dumps({
                "status": "pending",
                "phase": "post_attempted",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": MARKER_SCHEMA_VERSION,
            })
            self._atomic_write(marker_path, attempted_content)

            url = f"https://api.github.com/repos/{self.repo}/issues"
            headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}"}
            try:
                response = self.session.post(url, headers=headers, json={"title": title, "body": body}, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                # Preserve the pending marker: the POST may have succeeded despite the
                # client-side error.  A future run will reconcile via _search_github_for_marker.
                safe_msg = str(exc).replace(self.token, "***") if self.token else str(exc)
                raise RuntimeError(f"Could not create GitHub issue for export: {safe_msg}") from None

            # --- Validate the POST response before writing a completed marker ---
            try:
                created = response.json()
            except (ValueError, TypeError):
                # POST succeeded but response body is not valid JSON.
                # Preserve the pending marker for future reconciliation.
                return {"status": "error_recoverable", "reason": "invalid_post_response"}

            if not isinstance(created, dict):
                return {"status": "error_recoverable", "reason": "invalid_post_response"}

            number = created.get("number")
            html_url = created.get("html_url")
            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or not isinstance(html_url, str)
                or not html_url
            ):
                return {"status": "error_recoverable", "reason": "invalid_post_response"}

            marker = {
                "idempotency_key": key,
                "artifact_type": artifact["artifact_type"],
                "source_threat_id": artifact["source_threat_id"],
                "source_card_id": artifact["source_card_id"],
                "github_issue_number": number,
                "github_issue_url": html_url,
                "model": review_record.get("model"),
                "prompt_template_version": review_record.get("prompt_template_version"),
                "relevance": review_record.get("relevance"),
                "provenance": review_record.get("provenance"),
                "schema_version": MARKER_SCHEMA_VERSION,
            }
            self._atomic_write(marker_path, json.dumps(marker, indent=2))
            return {"status": "created", "marker": marker}
        finally:
            lock.release()