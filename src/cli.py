"""
Command-line interface for ThreatSutra: This module is the entry point for running the ThreatSutra pipeline.
It runs the orchestrator, generates artifacts for each threat, presents them to a human reviewer alongside 
source traceability and a relevance assessment, and — only for approved artifacts — exports them to GitHub.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from src.adapters.GitHubIssueClient import GitHubIssueClient
from src.adapters.GitHubIssueExporter import GitHubIssueExporter
from src.orchestrator import (
    GITHUB_REPO,
    GeminiServiceError,
    call_ai_model,
    generate_evil_user_story,
    generate_verification_test,
    run_pipeline,
)
from src.relevance import assess_relevance
from src.validation import ValidationError, neutralize_for_display, validate_evil_user_story, validate_verification_test

def print_header(text: str) -> None:
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)

def ask_for_approval() -> str: #Prompts the user to review and approve generated content before it is finalized.
    while True:
        choice = input("\nApprove this output? [y]es / [n]o / [e]dit manually: ").strip().lower()
        if choice in ("y", "yes"):
            return "approve"
        if choice in ("n", "no"):
            return "reject"
        if choice in ("e", "edit"):
            return "edit"
        print("Please type y, n, or e.")

def edit_text(label: str, current_text: str) -> str:
    print(f"\nCurrent {label}:\n{neutralize_for_display(current_text)}")
    new_text = input(f"Type the replacement {label} (or press Enter to keep it):\n> ").strip()
    return new_text if new_text else current_text

def revalidate_edit(artifact_type: str, text: str) -> str:
    """ Edited text is untrusted terminal input and must be revalidated against the same format contract as model output."""
    if artifact_type == "evil_user_story":
        return validate_evil_user_story(text)
    return validate_verification_test(text)

def save_output(context, artifact: dict, relevance, decision: str) -> str:
    """Saves the reviewer's decision to outputs/ as a JSON file with an audit-safe timestamp, including relevance, source provenance, 
    and model/template version so the audit trail (decision, provenance, relevance, model/template version) survives after review.
    """
    import uuid
    project_root = os.path.dirname(os.path.dirname(__file__))
    output_dir = os.path.join(project_root, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    output_data = {
        "timestamp": timestamp,
        "decision": decision,
        "artifact_type": artifact["artifact_type"],
        "text": artifact["text"],
        "source_threat_id": artifact["source_threat_id"],
        "source_card_id": artifact["source_card_id"],
        "source_milestone_number": artifact["source_milestone_number"],
        "model": artifact.get("model"),
        "prompt_template_version": artifact.get("prompt_template_version"),
        "relevance": {
            "score": relevance.score,
            "color": relevance.color,
            "explanation": relevance.explanation,
            "assessed_issue_urls": list(relevance.assessed_issue_urls),
        },
        "provenance": [
            {"source_type": p.source_type, "location": p.location, "content_hash": p.content_hash, "version": p.version}
            for p in context.provenance
        ],
    }
    
    while True:
        time_str = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        unique_suffix = uuid.uuid4().hex[:8]
        filename = f"review_{time_str}_{unique_suffix}.json"
        output_path = os.path.join(output_dir, filename)
        try:
            fd = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            break
        except FileExistsError:
            continue

    print(f"\nOutput saved successfully to:\n{output_path}")
    return output_path

def print_relevance(assessment) -> None:
    marker = {"green": "[RELEVANT]", "yellow": "[REVIEW]", "red": "[LOW RELEVANCE]"}[assessment.color]
    print(f"\nRelevance   : {marker} {assessment.score}/10")
    print(f"Why         : {neutralize_for_display(assessment.explanation)}")
    if assessment.assessed_issue_urls:
        print(f"From issues : {', '.join(assessment.assessed_issue_urls)}")

def review_artifact(context, artifact: dict, relevance, exporter: GitHubIssueExporter) -> None:
    """presents one generated artifact plus traceability and relevance
    context, collects a decision, and - only on approval - exports it."""
    label = "Evil user story" if artifact["artifact_type"] == "evil_user_story" else "Verification test"
    print(f"\n{label}:\n{neutralize_for_display(artifact['text'])}")
    print(f"\nSource threat : {context.threat_id} (#{context.threat_number})")
    print(f"Source card   : {context.card_id}")
    print(f"Milestone     : #{context.milestone_number} - {neutralize_for_display(context.milestone_title)}")
    decision = ask_for_approval()
    if decision == "edit":
        edited = edit_text(label.lower(), artifact["text"])
        try:
            artifact = {**artifact, "text": revalidate_edit(artifact["artifact_type"], edited)}
            decision = "approve"
        except ValidationError as exc:
            print(f"\nEdited text was rejected: {exc}\nTreating as 'reject'.")
            decision = "reject"
    output_path = save_output(context, artifact, relevance, decision)
    if decision != "approve":
        return
    with open(output_path, "r", encoding="utf-8") as f:
        review_record = json.load(f)
    result = exporter.export(review_record)
    if result["status"] == "dry_run":
        print(f"\n[DRY RUN] Would create GitHub issue:\nTitle: {result['title']}")
    elif result["status"] == "already_exported":
        print(f"\nAlready exported as {result['marker'].get('github_issue_url')}")
    elif result["status"] == "error_recoverable":
        print(f"\n[RETRY] Export could not be completed: {result.get('reason', 'unknown')}. "
              f"The pending marker has been preserved — re-run to retry.")
    else:
        print(f"\nExported as {result['marker'].get('github_issue_url')}")

def main():
    parser = argparse.ArgumentParser(description="ThreatSutra security analysis pipeline.")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logging for diagnostic output.")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(name)s %(levelname)s: %(message)s",
    )
    print_header("ThreatSutra")
    print("Loading project data and preparing security analysis...")
    try:
        contexts = run_pipeline()
    except GeminiServiceError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
    issue_client = GitHubIssueClient(allowed_repos=[GITHUB_REPO])
    exporter = GitHubIssueExporter(repo=GITHUB_REPO)
    if exporter.dry_run:
        print("\n[DRY RUN] GITHUB_API is not set - approved artifacts will be shown, not exported.")
    else:
        print("\n[LIVE EXPORT] GITHUB_API token is set - approved artifacts will be created as real GitHub issues.")
    for index, context in enumerate(contexts, start=1):
        print_header(f"THREAT {index} of {len(contexts)} (number: {context.threat_number})")
        print(f"Title       : {neutralize_for_display(context.threat_title)}")
        try:
            relevance = assess_relevance(context, call_ai_model, issue_client)
            print_relevance(relevance)
            review_artifact(context, generate_evil_user_story(context), relevance, exporter)
            review_artifact(context, generate_verification_test(context), relevance, exporter)
        except GeminiServiceError as exc:
            print(f"\nError: {exc}", file=sys.stderr)
            sys.exit(1)
    print_header("Analysis Complete")
    print(f"Successfully processed {len(contexts)} threat(s).")

if __name__ == "__main__":
    main()