import json
import os
import sys
from unittest.mock import MagicMock

import pytest

import src.cli
from src.cli import (
    ask_for_approval,
    edit_text,
    main,
    print_header,
    print_relevance,
    revalidate_edit,
    review_artifact,
    save_output,
)
from src.orchestrator import GeminiServiceError
from src.relevance import RelevanceAssessment
from src.validation import ValidationError
from tests.test_context import build_context


def test_print_header(capsys):
    print_header("Test Header")
    captured = capsys.readouterr()
    assert "Test Header" in captured.out
    assert "=" * 60 in captured.out

def test_ask_for_approval_approve(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert ask_for_approval() == "approve"

def test_ask_for_approval_reject(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert ask_for_approval() == "reject"

def test_ask_for_approval_edit(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "e")
    assert ask_for_approval() == "edit"


def test_ask_for_approval_retries_on_invalid_then_accepts(monkeypatch):
    inputs = iter(["x", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert ask_for_approval() == "approve"


def test_edit_text_returns_new_text(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "new text")
    assert edit_text("Label", "old text") == "new text"


def test_edit_text_keeps_original_on_empty_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: " ")
    assert edit_text("Label", "old text") == "old text"


def test_revalidate_edit_evil_user_story(monkeypatch):
    monkeypatch.setattr(src.cli, "validate_evil_user_story", lambda x: x + " validated")
    assert revalidate_edit("evil_user_story", "test") == "test validated"


def test_revalidate_edit_verification_test(monkeypatch):
    monkeypatch.setattr(src.cli, "validate_verification_test", lambda x: x + " validated")
    assert revalidate_edit("verification_test", "test") == "test validated"


def test_revalidate_edit_invalid_raises(monkeypatch):
    def mock_validate(x):
        raise ValidationError("Invalid")
    monkeypatch.setattr(src.cli, "validate_evil_user_story", mock_validate)
    with pytest.raises(ValidationError):
        revalidate_edit("evil_user_story", "test")


def test_save_output(monkeypatch, tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    fake_cli_py = src_dir / "cli.py"
    monkeypatch.setattr(src.cli, "__file__", str(fake_cli_py))
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "As a user, I want X so that Y",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
        "model": "gemini-1.5-pro",
        "prompt_template_version": "v1",
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=("url1",)
    )
    out_path = save_output(context, artifact, relevance, "approve")
    assert os.path.exists(out_path)
    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["decision"] == "approve"
    assert data["artifact_type"] == "evil_user_story"
    assert data["relevance"]["score"] == 8

def test_save_output_prevents_duplicate_filenames_via_milliseconds(monkeypatch, tmp_path):
    """Issue #13: Calling save_output very quickly must not result in identical filenames."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    fake_cli_py = src_dir / "cli.py"
    monkeypatch.setattr(src.cli, "__file__", str(fake_cli_py))
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "test",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    out_path_1 = save_output(context, artifact, relevance, "approve")
    out_path_2 = save_output(context, artifact, relevance, "approve")
    
    assert out_path_1 != out_path_2
    assert os.path.exists(out_path_1)
    assert os.path.exists(out_path_2)


def test_print_relevance_green(capsys):
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=("url1",)
    )
    print_relevance(relevance)
    captured = capsys.readouterr()
    assert "[RELEVANT]" in captured.out
    assert "8/10" in captured.out
    assert "url1" in captured.out


def test_print_relevance_yellow(capsys):
    relevance = RelevanceAssessment(
        score=5, color="yellow", explanation="Maybe", assessed_issue_urls=("url2",)
    )
    print_relevance(relevance)
    captured = capsys.readouterr()
    assert "[REVIEW]" in captured.out


def test_print_relevance_red_no_issues(capsys):
    relevance = RelevanceAssessment(
        score=2, color="red", explanation="Not relevant", assessed_issue_urls=()
    )
    print_relevance(relevance)
    captured = capsys.readouterr()
    assert "[LOW RELEVANCE]" in captured.out
    assert "2/10" in captured.out
    assert "url1" not in captured.out


def test_review_artifact_approve_dry_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    fake_cli_py = src_dir / "cli.py"
    monkeypatch.setattr(src.cli, "__file__", str(fake_cli_py))
    exporter = MagicMock()
    exporter.export.return_value = {
        "status": "dry_run",
        "title": "Test Title",
        "marker": {},
    }
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    captured = capsys.readouterr()
    assert "[DRY RUN] Would create GitHub issue" in captured.out
    exporter.export.assert_called_once()


def test_review_artifact_reject(monkeypatch, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "reject")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    exporter.export.assert_not_called()


def test_review_artifact_edit_valid(monkeypatch, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "edit")
    monkeypatch.setattr(src.cli, "edit_text", lambda l, t: "edited text")
    monkeypatch.setattr(src.cli, "revalidate_edit", lambda t, e: e)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    exporter.export.return_value = {
        "status": "exported",
        "marker": {"github_issue_url": "url"},
    }
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    exporter.export.assert_called_once()
    args, _ = exporter.export.call_args
    assert args[0]["text"] == "edited text"


def test_review_artifact_edit_invalid_falls_back_to_reject(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "edit")
    monkeypatch.setattr(src.cli, "edit_text", lambda l, t: "invalid text")
    def mock_revalidate(t, e):
        raise ValidationError("Bad text")
    monkeypatch.setattr(src.cli, "revalidate_edit", mock_revalidate)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    captured = capsys.readouterr()
    assert "Treating as 'reject'" in captured.out
    exporter.export.assert_not_called()

def test_review_artifact_already_exported(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    exporter.export.return_value = {
        "status": "already_exported",
        "marker": {"github_issue_url": "url123"},
    }
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    captured = capsys.readouterr()
    assert "Already exported as url123" in captured.out

def test_review_artifact_created(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    exporter.export.return_value = {
        "status": "created",
        "marker": {"github_issue_url": "url456"},
    }
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    captured = capsys.readouterr()
    assert "Exported as url456" in captured.out

def test_review_artifact_error_recoverable(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))
    exporter = MagicMock()
    exporter.export.return_value = {
        "status": "error_recoverable",
        "reason": "search_failed",
    }
    context = build_context()
    artifact = {
        "artifact_type": "evil_user_story",
        "text": "text",
        "source_threat_id": "T1",
        "source_card_id": "C1",
        "source_milestone_number": 1,
    }
    relevance = RelevanceAssessment(
        score=8, color="green", explanation="Relevant", assessed_issue_urls=()
    )
    review_artifact(context, artifact, relevance, exporter)
    captured = capsys.readouterr()
    assert "[RETRY]" in captured.out
    assert "search_failed" in captured.out

def test_main_gemini_service_error_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cli.py"])
    def mock_run():
        raise GeminiServiceError("API down")
    monkeypatch.setattr(src.cli, "run_pipeline", mock_run)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1

def test_main_gemini_service_error_in_loop(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cli.py"])
    context = build_context()
    monkeypatch.setattr(src.cli, "run_pipeline", lambda: [context])

    def mock_assess(*args):
        raise GeminiServiceError("Model error inside loop")
    monkeypatch.setattr(src.cli, "assess_relevance", mock_assess)
    monkeypatch.setattr(src.cli, "GitHubIssueExporter", MagicMock())
    monkeypatch.setattr(src.cli, "GitHubIssueClient", MagicMock())
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1

def test_main_dry_run_mode(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["cli.py", "--debug"])
    context = build_context()
    monkeypatch.setattr(src.cli, "run_pipeline", lambda: [context])
    monkeypatch.setattr(
        src.cli,
        "assess_relevance",
        lambda c, m, i: RelevanceAssessment(8, "green", "exp", ()),
    )
    monkeypatch.setattr(
        src.cli,
        "generate_evil_user_story",
        lambda c: {
            "artifact_type": "evil_user_story",
            "text": "e",
            "source_threat_id": "1",
            "source_card_id": "1",
            "source_milestone_number": 1,
        },
    )
    monkeypatch.setattr(
        src.cli,
        "generate_verification_test",
        lambda c: {
            "artifact_type": "verification_test",
            "text": "v",
            "source_threat_id": "1",
            "source_card_id": "1",
            "source_milestone_number": 1,
        },
    )
    mock_exporter = MagicMock()
    mock_exporter.dry_run = True
    mock_exporter.export.return_value = {
        "status": "dry_run",
        "title": "Test",
        "marker": {},
    }
    monkeypatch.setattr(src.cli, "GitHubIssueExporter", lambda repo: mock_exporter)
    monkeypatch.setattr(src.cli, "GitHubIssueClient", MagicMock())
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))

    main()
    captured = capsys.readouterr()
    assert "Analysis Complete" in captured.out
    assert "Successfully processed 1 threat(s)." in captured.out

def test_main_live_export_mode(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["cli.py"])
    context = build_context()
    monkeypatch.setattr(src.cli, "run_pipeline", lambda: [context])
    monkeypatch.setattr(
        src.cli,
        "assess_relevance",
        lambda c, m, i: RelevanceAssessment(8, "green", "exp", ()),
    )
    monkeypatch.setattr(
        src.cli,
        "generate_evil_user_story",
        lambda c: {
            "artifact_type": "evil_user_story",
            "text": "e",
            "source_threat_id": "1",
            "source_card_id": "1",
            "source_milestone_number": 1,
        },
    )
    monkeypatch.setattr(
        src.cli,
        "generate_verification_test",
        lambda c: {
            "artifact_type": "verification_test",
            "text": "v",
            "source_threat_id": "1",
            "source_card_id": "1",
            "source_milestone_number": 1,
        },
    )
    mock_exporter = MagicMock()
    mock_exporter.dry_run = False
    mock_exporter.export.return_value = {
        "status": "created",
        "title": "Test",
        "marker": {"github_issue_url": "url"},
    }
    monkeypatch.setattr(src.cli, "GitHubIssueExporter", lambda repo: mock_exporter)
    monkeypatch.setattr(src.cli, "GitHubIssueClient", MagicMock())
    monkeypatch.setattr(src.cli, "ask_for_approval", lambda: "approve")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(src.cli, "__file__", str(src_dir / "cli.py"))

    main()
    captured = capsys.readouterr()
    assert "[LIVE EXPORT]" in captured.out
    assert "Analysis Complete" in captured.out
    assert "Successfully processed 1 threat(s)." in captured.out
