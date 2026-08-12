"""
threat_dragon.py

Reads and parses Threat Dragon threat models. This module loads Threat Dragon JSON files and extracts structured
threat information for use throughout the ThreatSutra pipeline.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from src.validation import validate_threat, validate_threat_dragon_document

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DFD_PATH = os.path.join(PROJECT_ROOT, "ThreatDragonModels", "DFD_ThreatSutra.json")

class ThreatDragonReader:        #Reads validated threat records out of a Threat Dragon model file.
    def __init__(self, path: str = DFD_PATH):
        self.path = path

    def read_threat_source(self) -> dict:
        """
        Reads, validates, and normalizes the tracked Threat Dragon document. Issue #2/#9: the outer document is validated before traversal, and
        each threat gets an explicit source_location plus provenance(content hash, retrieval time) so #11 can build a traceable context.
        """
        if not os.path.isfile(self.path):
            raise FileNotFoundError(
                f"Threat Dragon model was not found at '{self.path}'. "
                "Expected ThreatDragonModels/DFD_ThreatSutra.json under the project root."
            )
        try:
            with open(self.path, "rb") as f:
                raw_bytes = f.read()
        except OSError as exc:
            raise RuntimeError(f"Could not read Threat Dragon model '{self.path}': {exc}") from exc
        try:
            model = json.loads(raw_bytes.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"Threat Dragon model '{self.path}' is not UTF-8 encoded.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Threat Dragon model '{self.path}' is not valid JSON: {exc.msg}.") from exc
        validate_threat_dragon_document(model)
        threats = []
        for diagram_index, diagram in enumerate(model["detail"]["diagrams"]):
            for cell_index, cell in enumerate(diagram.get("cells", [])):
                 cell_data = cell.get("data", {})
                 for threat_index, threat in enumerate(cell_data.get("threats", [])):
                    validate_threat(threat)
                    threat.append({
                        **threat,
                        "source_location": {
                        "diagram_index": diagram_index,
                        "diagram_title": diagram.get("title", ""),
                        "cell_index": cell_index,
                        "cell_name": cell_data.get("name", ""),
                        "threat_index": threat_index,}
                    })
        return {
             "summary": {
                "title": model["summary"]["title"],
                "description": model["summary"]["description"],
            },
            "threats": threats,
            "provenance": {
                "source_type": "threat_dragon",
                "location": os.path.abspath(self.path),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "content_hash": hashlib.sha256(raw_bytes).hexdigest(),
            },
        }

    def read_threats(self) -> list:
        """Returns just the threat list, preserving the original public API used by existing callers."""
        return self.read_threat_source()["threats"]            

