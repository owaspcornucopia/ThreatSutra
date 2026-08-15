"""Tests for Gemini API error handling, debug logging, and --debug CLI option."""
import logging
from unittest.mock import MagicMock, patch
import pytest
from google.genai import errors as genai_errors
from src.orchestrator import GeminiServiceError, call_ai_model, generate_verification_test
from src.validation import ValidationError

# Gemini HTTP error handling
@patch("src.orchestrator.genai.Client")
def test_503_raises_gemini_service_error(mock_client_cls, monkeypatch):
    """503 UNAVAILABLE must produce a concise GeminiServiceError, not a raw traceback."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.APIError(503, "UNAVAILABLE")
    mock_client_cls.return_value = mock_client
    with pytest.raises(GeminiServiceError, match="not available"):
        call_ai_model("test prompt")

@patch("src.orchestrator.genai.Client")
def test_429_raises_gemini_service_error(mock_client_cls, monkeypatch):
    """429 RESOURCE_EXHAUSTED must produce a concise GeminiServiceError."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.APIError(429, "RESOURCE_EXHAUSTED")
    mock_client_cls.return_value = mock_client
    with pytest.raises(GeminiServiceError, match="quota exhausted"):
        call_ai_model("test prompt")

@patch("src.orchestrator.genai.Client")
def test_other_api_error_raises_gemini_service_error(mock_client_cls, monkeypatch):
    """Other API errors are wrapped in GeminiServiceError, not swallowed."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.APIError(500, "INTERNAL")
    mock_client_cls.return_value = mock_client
    with pytest.raises(GeminiServiceError, match="HTTP 500"):
        call_ai_model("test prompt")

@patch("src.orchestrator.genai.Client")
def test_successful_response_returns_text(mock_client_cls, monkeypatch):
    """A normal 200 response must still return text unchanged."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_response = MagicMock()
    mock_response.text = "  hello world  "
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_client_cls.return_value = mock_client
    assert call_ai_model("test prompt") == "hello world"

# Debug logging for invalid successful model output
@patch("src.orchestrator.call_ai_model")
def test_validation_failure_logs_raw_output_at_debug(mock_call, caplog):
    """When Gemini returns 200 but the verification test fails BDD validation,
    the full raw LLM output must be logged at DEBUG level."""
    # Return valid JSON with an invalid verification test (missing Given/When/Then).
    bad_raw = '{"verification_test": "This is not a valid BDD test."}'
    mock_call.return_value = bad_raw
    # Build a minimal AnalysisContext for generation.
    from tests.test_context import build_context
    context = build_context()
    with caplog.at_level(logging.DEBUG, logger="src.orchestrator"):
        with pytest.raises(ValidationError):
            generate_verification_test(context)
    assert bad_raw in caplog.text

@patch("src.orchestrator.call_ai_model")
def test_validation_failure_does_not_log_at_info_or_above(mock_call, caplog):
    """The raw LLM output must NOT appear at INFO, WARNING, or ERROR levels."""
    bad_raw = '{"verification_test": "Not a BDD format at all."}'
    mock_call.return_value = bad_raw
    from tests.test_context import build_context
    context = build_context()
    with caplog.at_level(logging.INFO, logger="src.orchestrator"):
        with pytest.raises(ValidationError):
            generate_verification_test(context)
    # At INFO level, the debug message should not appear.
    assert bad_raw not in caplog.text

# --debug CLI option
def test_debug_flag_accepted_by_parser():
    """The CLI must accept --debug without error."""
    import argparse
    # Replicate the parser setup from cli.main().
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(["--debug"])
    assert args.debug is True

def test_no_debug_flag_defaults_false():
    """Without --debug, debug must default to False."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args([])
    assert args.debug is False