"""
Defines the AnalysisContext used across the pipeline. It combines one threat, its mapped Cornucopia card, related explanation data,
and milestone info into a single validated structure used for generation and review.
"""
import re
from dataclasses import dataclass

from src.validation import (
    ValidationError,
    sanitize_text,
    validate_card,
    validate_context_budget,
    validate_explanation_sections,
    validate_milestone,
    validate_threat,
)

MILESTONE_URL_PATTERN = re.compile(r"https://github\.com/owaspcornucopia/ThreatSutra/milestone/(\d+)")
ISSUE_URL_PATTERN = re.compile(r"https://github\.com/owaspcornucopia/ThreatSutra/issues/\d+")

@dataclass(frozen=True)
class SourceProvenance:
    source_type: str
    location: str
    retrieved_at: str
    content_hash: str
    version: str = ""

@dataclass(frozen=True)
class AnalysisContext:
    threat_id: str
    threat_number: int | None
    threat_title: str
    threat_description: str
    threat_mitigation: str
    card_id: str
    card_section: str
    card_description: str
    card_scenario: str
    card_what_can_go_wrong: str
    card_requirement: str
    card_mitigation: str
    milestone_number: int
    milestone_title: str
    milestone_description: str
    linked_issue_urls: tuple[str, ...]
    provenance: tuple[SourceProvenance, ...]
    estimated_tokens: int

def extract_milestone_number(summary_description: str) -> int:
    #Reads the single GitHub milestone the DFD declares.
    matches = sorted(set(MILESTONE_URL_PATTERN.findall(summary_description)))
    if len(matches) != 1:
        raise ValidationError(
            "Threat Dragon summary must contain exactly one ThreatSutra GitHub milestone URL."
        )
    return int(matches[0])

def select_milestone(milestones: list, milestone_number: int) -> dict:
    #Selects the DFD-declared milestone from the fetched list, or fails closed if it isn't found.
    for milestone in milestones:
        if milestone.get("number") == milestone_number:
            return milestone
    raise ValidationError(
        f"GitHub milestone #{milestone_number} was declared by the Threat Dragon model "
        "but was not returned by the GitHub API."
    )

def _linked_issue_urls(description: str) -> tuple[str, ...]:
    """Keeps linked GitHub Issue URLs as traceability/provenance only - their bodies are
    not fetched. Full issue-content retrieval and relevance screening happen separately, in the 
    relevance-scoring stage (src/relevance.py)."""
    return tuple(dict.fromkeys(ISSUE_URL_PATTERN.findall(description)))

def _provenance(source: dict, version: str = "") -> SourceProvenance:
    return SourceProvenance(
        source_type=source["source_type"],
        location=source["location"],
        retrieved_at=source["retrieved_at"],
        content_hash=source["content_hash"],
        version=version,
    )

def build_analysis_context(
    threat: dict,
    threat_provenance: dict,
    card: dict,
    card_provenance: dict,
    explanation: dict,
    milestone: dict,
    milestone_provenance: dict,
) -> AnalysisContext:
    """Builds one bounded, traceable AnalysisContext from validated external sources."""
    validate_threat(threat)
    validate_card(card)
    validate_explanation_sections(explanation)
    validate_milestone(milestone)
    milestone_description = milestone.get("description") or ""
    text_fields = {
        "threat_title": threat["title"],
        "threat_description": threat["description"],
        "threat_mitigation": threat["mitigation"],
        "card_description": card["description"],
        "card_scenario": explanation["scenario"],
        "card_what_can_go_wrong": explanation["what_can_go_wrong"],
        "card_requirement": explanation["requirement"],
        "card_mitigation": explanation["mitigation"],
        "milestone_title": milestone["title"],
        "milestone_description": milestone_description,
    }
    estimated_tokens = validate_context_budget(text_fields)
    return AnalysisContext(
        threat_id=threat["id"],
        threat_number=threat.get("number"),
        threat_title=sanitize_text(threat["title"]).strip(),
        threat_description=sanitize_text(threat["description"]).strip(),
        threat_mitigation=sanitize_text(threat["mitigation"]).strip(),
        card_id=card["sectionID"],
        card_section=sanitize_text(card.get("section", "")).strip(),
        card_description=sanitize_text(card["description"]).strip(),
        card_scenario=sanitize_text(explanation["scenario"]).strip(),
        card_what_can_go_wrong=sanitize_text(explanation["what_can_go_wrong"]).strip(),
        # Intentionally sourced from the documented "What are we going to do about it?" explanation section - the API/DFD have no separate field.
        card_requirement=sanitize_text(explanation["requirement"]).strip(),
        card_mitigation=sanitize_text(explanation["mitigation"]).strip(),
        milestone_number=milestone["number"],
        milestone_title=sanitize_text(milestone["title"]).strip(),
        milestone_description=sanitize_text(milestone_description).strip(),
        linked_issue_urls=_linked_issue_urls(threat["description"]),
        provenance=(
            _provenance(threat_provenance),
            _provenance(card_provenance, card_provenance.get("api_version", "")),
            _provenance(explanation["provenance"], explanation["provenance"].get("version", "")),
            _provenance(milestone_provenance),
        ),
        estimated_tokens=estimated_tokens,
    )