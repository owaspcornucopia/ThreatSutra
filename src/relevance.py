"""
Handles relevance scoring and reviewer visibility. Each threat is scored (1–10) against the current milestone using AI,
based on threat data and related GitHub issues. The score is shown to the reviewer (green/yellow/red) as guidance only — not a blocking check.
Used by the review stage to support human decision-making.
"""
from dataclasses import dataclass
from typing import Tuple
from src.adapters.GitHubIssueClient import GitHubIssueClient
from src.context import AnalysisContext
from src.prompts import build_relevance_prompt
from src.validation import (
    extract_model_json_fields,
    relevance_color_for_score,
    validate_relevance_assessment,
)

@dataclass(frozen=True)
class RelevanceAssessment:
    score: int
    color: str
    explanation: str
    assessed_issue_urls: Tuple[str, ...]

def assess_relevance(context: AnalysisContext, call_ai_model, issue_client: GitHubIssueClient = None) -> RelevanceAssessment:
    """
    Fetches the threat's linked GitHub issues and scores their relevance to the milestone. `call_ai_model` is 
    injected (rather than imported from orchestrator) to avoid a circular import and to keep this testable without a live model call.
    """
    issue_client = issue_client or GitHubIssueClient()
    linked_issues = issue_client.get_issues(context.linked_issue_urls)
    prompt = build_relevance_prompt(context, linked_issues)
    response_text = call_ai_model(prompt)
    payload = extract_model_json_fields(response_text, ("score", "explanation"))
    validate_relevance_assessment(payload)
    return RelevanceAssessment(
        score=payload["score"],
        color=relevance_color_for_score(payload["score"]),
        explanation=payload["explanation"].strip(),
        assessed_issue_urls=tuple(context.linked_issue_urls),
    )