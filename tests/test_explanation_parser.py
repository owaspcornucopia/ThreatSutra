"""Tests for CornucopiaExplanationClient's Markdown section parser."""
import pytest

from src.adapters.CornucopiaExplanationClient import CornucopiaExplanationClient
from src.validation import ValidationError, validate_explanation_sections

REPRESENTATIVE_CARD_MARKDOWN = """
# VEK
## Scenario
Kyle sends a malicious payload that the application fails to reject.
## What can go wrong?
The payload is processed as if it were legitimate input.
## What are we going to do about it?
Validate all input against an explicit allow-list before processing it.
"""
def test_parses_all_required_sections_from_a_representative_card():
    sections = CornucopiaExplanationClient._parse_sections(REPRESENTATIVE_CARD_MARKDOWN)
    assert sections["scenario"].startswith("Kyle sends")
    assert sections["what_can_go_wrong"].startswith("The payload")
    assert sections["requirement"].startswith("Validate all input")
    assert sections["mitigation"] == sections["requirement"]
    validate_explanation_sections(sections)  # must not raise

def test_renamed_heading_fails_safely_instead_of_silently_omitting_a_section():
    # Upstream heading changes must fail loudly, not silently produce an incomplete/empty section that reaches generation.
    markdown = REPRESENTATIVE_CARD_MARKDOWN.replace("What are we going to do about it?", "Recommended controls")
    sections = CornucopiaExplanationClient._parse_sections(markdown)
    with pytest.raises(ValidationError):
        validate_explanation_sections(sections)

def test_missing_scenario_heading_fails_safely():
    markdown = REPRESENTATIVE_CARD_MARKDOWN.replace("## Scenario", "## Overview")
    sections = CornucopiaExplanationClient._parse_sections(markdown)
    with pytest.raises(ValidationError):
        validate_explanation_sections(sections)