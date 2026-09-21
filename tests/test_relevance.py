from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from src.adapters.GitHubIssueClient import GitHubIssueClient
from src.relevance import RelevanceAssessment, assess_relevance
from tests.test_context import build_context


def test_assess_relevance_returns_assessment():
    mock_call_ai_model = Mock(return_value='{"score": 8, "explanation": "Highly relevant."}')
    mock_issue_client = Mock(spec=GitHubIssueClient)
    mock_issue_client.get_issues.return_value = []
    context = build_context()   
    assessment = assess_relevance(context, mock_call_ai_model, mock_issue_client)    
    assert assessment.score == 8
    assert assessment.color == "green"
    assert assessment.explanation == "Highly relevant."
    assert assessment.assessed_issue_urls == tuple(context.linked_issue_urls)

def test_assess_relevance_with_linked_issues():
    mock_call_ai_model = Mock(return_value='{"score": 5, "explanation": "Some relevance."}')
    mock_issue_client = Mock(spec=GitHubIssueClient)
    mock_issue_client.get_issues.return_value = [{"title": "Issue 1", "body": "Body 1", "number": 1, "url": "url1"}]   
    context = build_context()
    assessment = assess_relevance(context, mock_call_ai_model, mock_issue_client)
    assert assessment.score == 5
    assert assessment.assessed_issue_urls == tuple(context.linked_issue_urls)

def test_assess_relevance_requires_issue_client():
    """Issue #26: assess_relevance must raise if no issue_client is provided (deny-by-default)."""
    mock_call_ai_model = Mock(return_value='{"score": 3, "explanation": "Low."}')
    context = build_context()
    with pytest.raises(ValueError, match="issue_client is required"):
        assess_relevance(context, mock_call_ai_model)

def test_assess_relevance_propagates_ai_error():
    mock_call_ai_model = Mock(side_effect=RuntimeError("AI failed"))
    mock_issue_client = Mock(spec=GitHubIssueClient)
    mock_issue_client.get_issues.return_value = []
    context = build_context()
    with pytest.raises(RuntimeError, match="AI failed"):
        assess_relevance(context, mock_call_ai_model, mock_issue_client)

def test_relevance_assessment_frozen():
    assessment = RelevanceAssessment(score=10, color="green", explanation="Test", assessed_issue_urls=("url1",))
    with pytest.raises(FrozenInstanceError):
        assessment.score = 5
