#Tests for ThreatDragonReader
import pytest

from src.adapters.ThreatDragonReader import ThreatDragonReader
from src.context import extract_milestone_number
from src.validation import ValidationError, validate_threat_dragon_document


def test_read_threat_source_against_tracked_model():
    """Issue #9's acceptance check: the reader must extract every threat from
    the repository's actual tracked DFD, not sample fixtures."""
    source = ThreatDragonReader().read_threat_source()
    assert len(source["threats"]) == 9
    assert source["summary"]["title"] == "ThreatSutra"

def test_each_threat_has_source_location_and_required_fields():
    source = ThreatDragonReader().read_threat_source()
    for threat in source["threats"]:
        assert "source_location" in threat
        for field in ("id", "cardNumber", "title", "description", "mitigation"):
            assert threat.get(field)

def test_provenance_is_present_and_hashed():
    source = ThreatDragonReader().read_threat_source()
    provenance = source["provenance"]
    assert provenance["source_type"] == "threat_dragon"
    assert len(provenance["content_hash"]) == 64  # sha256 hex digest

def test_missing_file_raises_clear_error(tmp_path):
    reader = ThreatDragonReader(path=str(tmp_path / "does_not_exist.json"))
    with pytest.raises(FileNotFoundError):
        reader.read_threat_source()

def test_malformed_document_is_rejected():
    with pytest.raises(ValidationError):
        validate_threat_dragon_document({"summary": {"title": "x"}})  # missing detail/diagrams

def test_document_that_is_not_a_mapping_is_rejected():
    with pytest.raises(ValidationError):
        validate_threat_dragon_document(["not", "a", "mapping"])

def test_extract_milestone_number_from_real_summary():
    source = ThreatDragonReader().read_threat_source()
    assert extract_milestone_number(source["summary"]["description"]) == 1

def test_extract_milestone_number_requires_exactly_one_url():
    with pytest.raises(ValidationError):
        extract_milestone_number("no milestone url here")
    with pytest.raises(ValidationError):
        extract_milestone_number(
            "https://github.com/owaspcornucopia/ThreatSutra/milestone/1 "
            "https://github.com/owaspcornucopia/ThreatSutra/milestone/2"
        )

def test_read_threats_returns_threat_list():
    """Line 74: read_threats() returns just the threats list."""
    reader = ThreatDragonReader()
    threats = reader.read_threats()
    assert isinstance(threats, list)
    assert len(threats) > 0

def test_os_error_reading_model(tmp_path):
    """Lines 33-34: OSError when reading the file."""
    from unittest.mock import patch
    real_file = tmp_path / "model.json"
    real_file.write_text("{}")
    reader = ThreatDragonReader(str(real_file))
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        with pytest.raises(RuntimeError, match="Could not read"):
            reader.read_threat_source()

def test_unicode_decode_error(tmp_path):
    """Lines 37-38: UnicodeDecodeError from non-UTF-8 file."""
    bad_file = tmp_path / "model.json"
    bad_file.write_bytes(b'\xff\xfe' + b'\x00' * 10)
    reader = ThreatDragonReader(str(bad_file))
    with pytest.raises(RuntimeError, match="not UTF-8"):
        reader.read_threat_source()

def test_json_decode_error(tmp_path):
    """Lines 39-40: JSONDecodeError from invalid JSON file."""
    bad_file = tmp_path / "model.json"
    bad_file.write_text("this is not valid json at all", encoding="utf-8")
    reader = ThreatDragonReader(str(bad_file))
    with pytest.raises(RuntimeError, match="not valid JSON"):
        reader.read_threat_source()