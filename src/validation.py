"""
Provides the validation interface used throughout the ThreatSutra pipeline.This module currently exposes placeholder validation functions so other
parts of the application can rely on a stable API while the validationlayer evolves.
In the future, these functions will validate data received from external
sources such as:
- OWASP Threat Dragon
- OWASP Cornucopia
- GitHub
Additional validation rules (such as required fields, character restrictions, length limits, and content validation) will be implemented here as the project matures.
"""
import json
import re
MAX_FIELD_LENGTH = 6000        
MAX_TOTAL_LENGTH = 20000       
MAX_LIST_LENGTH = 500          
REQUIRED_THREAT_FIELDS = ("id", "type", "cardNumber", "title", "description", "mitigation")
REQUIRED_CARD_FIELDS = ("sectionID", "name", "description")
REQUIRED_MILESTONE_FIELDS = ("number", "title")
OPTIONAL_CARD_TEXT_FIELDS = ("doctype", "id", "section", "hyperlink", "tooltype")
OPTIONAL_MILESTONE_TEXT_FIELDS = ("description", "state", "html_url")
MAX_CONTEXT_TOKENS = 3000
CHARS_PER_TOKEN_ESTIMATE = 3
REQUIRED_EXPLANATION_FIELDS = ("scenario", "what_can_go_wrong", "requirement", "mitigation")

class ValidationError(ValueError): # Raised when external data fails validation. Subclasses ValueError so existing callers that catch ValueError keep working.
    pass
def _fail(source: str, message: str) -> None:
    """Raises a ValidationError that names the source and the exact problem."""
    raise ValidationError(f"Invalid {source}: {message}")

def _require_mapping(value, source: str) -> None:
    if not isinstance(value, dict):
        _fail(source, f"expected a JSON object, got {type(value).__name__}.")

def _has_control_chars(text: str) -> bool:
    """True if text contains control characters other than tab/newline/carriage return."""
    return any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text)

def _validate_text(value, field: str, source: str, required: bool = True) -> int:
    """
    Validates one text field and returns its length.
    Checks type, emptiness (when required), control characters, and length cap.
    """
    if value is None:
        if required:
            _fail(source, f"required field '{field}' is missing or null.")
        return 0
    if not isinstance(value, str):
        _fail(source, f"field '{field}' must be text, got {type(value).__name__}.")
    if required and not value.strip():
        _fail(source, f"required field '{field}' is empty.")
    if len(value) > MAX_FIELD_LENGTH:
        _fail(source, f"field '{field}' is {len(value)} characters, over the {MAX_FIELD_LENGTH} limit.")
    if _has_control_chars(value):
        _fail(source, f"field '{field}' contains control characters and was rejected.")
    return len(value)

def _validate_total_length(total: int, source: str) -> None:
    if total > MAX_TOTAL_LENGTH:
        _fail(source, f"combined text is {total} characters, over the {MAX_TOTAL_LENGTH} limit.")

def _validate_list(items, source: str) -> None:
    if not isinstance(items, list):
        _fail(source, f"expected a list, got {type(items).__name__}.")
    if len(items) > MAX_LIST_LENGTH:
        _fail(source, f"{len(items)} items received, over the {MAX_LIST_LENGTH} limit.")

def sanitize_text(text: str) -> str:
    """
    Strips control characters from text so it is safe to print or store.
    Provided here so later issues (review display, LLM output handling) reuse
    one implementation instead of writing their own.
    """
    if not isinstance(text, str):
        return ""
    return "".join(ch for ch in text if ord(ch) >= 32 or ch in "\t\n")

def validate_threat(threat: dict) -> dict:
    """
    Validates one Threat Dragon threat and returns it unchanged.
    Raises ValidationError naming the offending field.
    """
    _require_mapping(threat, "Threat Dragon threat")
    source = f"Threat Dragon threat '{threat.get('id', '<no id>')}'"
    total = 0
    for field in REQUIRED_THREAT_FIELDS:
        total += _validate_text(threat.get(field), field, source)
    _validate_total_length(total, source)
    return threat

def validate_card(card: dict) -> dict:
    """
    Validates one Cornucopia card from the API and returns it unchanged.
    Only sectionID is required, since that is the field the card lookup matches on;
    other text fields are validated when present.
    """
    _require_mapping(card, "Cornucopia card")
    source = f"Cornucopia card '{card.get('sectionID', '<no sectionID>')}'"
    total = 0
    for field in REQUIRED_CARD_FIELDS:
        total += _validate_text(card.get(field), field, source)
    for field in OPTIONAL_CARD_TEXT_FIELDS:
        if field in card:
            total += _validate_text(card.get(field), field, source, required=False)
    for field in ("links", "tags"):
        if field in card and not isinstance(card[field], list):
            _fail(source, f"field '{field}' must be a list, got {type(card[field]).__name__}.")        
    _validate_total_length(total, source)
    return card

def validate_milestone(milestone: dict) -> dict:
    """
    Validates one GitHub milestone and returns it unchanged.
    'number' must be an integer; 'title' must be non-empty text.
    """
    _require_mapping(milestone, "GitHub milestone")
    source = f"GitHub milestone '{milestone.get('number', '<no number>')}'"
    number = milestone.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        _fail(source, f"field 'number' must be an integer, got {type(number).__name__}.")
    total = _validate_text(milestone.get("title"), "title", source)
    for field in OPTIONAL_MILESTONE_TEXT_FIELDS:
        if field in milestone:
            total += _validate_text(milestone.get(field), field, source, required=False)
    _validate_total_length(total, source)
    return milestone

def validate_threats(threats: list) -> list:
    """Validates every threat read from a Threat Dragon model. Fails closed on the first bad entry."""
    _validate_list(threats, "Threat Dragon threat list")
    for index, threat in enumerate(threats):
        try:
            validate_threat(threat)
        except ValidationError as exc:
            raise ValidationError(f"Threat at position {index}: {exc}") from exc
    return threats


def validate_milestones(milestones: list) -> list:
    """Validates every milestone fetched from GitHub. Fails closed on the first bad entry."""
    _validate_list(milestones, "GitHub milestone list")
    for index, milestone in enumerate(milestones):
        try:
            validate_milestone(milestone)
        except ValidationError as exc:
            raise ValidationError(f"Milestone at position {index}: {exc}") from exc
    return milestones

def validate_threat_dragon_document(model: dict) -> dict:       #Validates the outer Threat Dragon document before it is traversed.
    _require_mapping(model, "Threat Dragon document")
    summary = model.get("summary")
    _require_mapping(summary, "Threat Dragon document summary")
    _validate_text(summary.get("title"), "title", "Threat Dragon document summary")
    _validate_text(summary.get("description"), "description", "Threat Dragon document summary")
    detail = model.get("detail")
    _require_mapping(detail, "Threat Dragon document detail")
    diagrams = detail.get("diagrams")
    _validate_list(diagrams, "Threat Dragon diagram list")
    for diagram_index, diagram in enumerate(diagrams):
        _require_mapping(diagram, f"Threat Dragon diagram at position {diagram_index}")
        cells = diagram.get("cells")
        _validate_list(cells, f"Threat Dragon cells in diagram {diagram_index}")
        for cell_index, cell in enumerate(cells):
            _require_mapping(cell, f"Threat Dragon cell at diagram {diagram_index}, position {cell_index}")
            data = cell.get("data", {})
            _require_mapping(data, f"Threat Dragon cell data at diagram {diagram_index}, position {cell_index}")
            threats = data.get("threats", [])
            _validate_list(threats, f"Threat Dragon threats at diagram {diagram_index}, cell {cell_index}")
            for threat_index, threat in enumerate(threats):
                try:
                    validate_threat(threat)
                except ValidationError as exc:
                    raise ValidationError(
                        f"Threat Dragon threat at diagram {diagram_index}, "
                        f"cell {cell_index}, position {threat_index}: {exc}"
                    ) from exc
    return model

def validate_cornucopia_response(payload: dict) -> dict:
    """
    Validates the complete Cornucopia API response envelope before any card 
    is cached because the envelope (meta + standards list) isn't covered by per-card validation alone. """
    _require_mapping(payload, "Cornucopia API response")
    meta = payload.get("meta")
    _require_mapping(meta, "Cornucopia API response metadata")
    for field in ("edition", "component", "language", "version"):
        _validate_text(meta.get(field), field, "Cornucopia API response metadata")
    standards = payload.get("standards")
    _validate_list(standards, "Cornucopia API standards")
    for index, card in enumerate(standards):
        try:
            validate_card(card)
        except ValidationError as exc:
            raise ValidationError(f"Cornucopia card at position {index}: {exc}") from exc
    return payload

def validate_explanation_sections(sections: dict) -> dict:
    """
    Validates the selected, parsed Cornucopia card explanation sections
    (scenario / what_can_go_wrong / requirement / mitigation)
    """
    _require_mapping(sections, "Cornucopia card explanation")
    total = 0
    for field in REQUIRED_EXPLANATION_FIELDS:
        total += _validate_text(sections.get(field), field, "Cornucopia card explanation")
    _validate_total_length(total, "Cornucopia card explanation")
    return sections

def validate_context_budget(text_fields: dict) -> int:
    """
    Validates every text value in the AnalysisContext and returns the estimated token count. 
    Raises ValidationError if any field is invalid or the total exceeds the token limit.
    """
    _require_mapping(text_fields, "AnalysisContext text fields")
    total_characters = 0
    for field, value in text_fields.items():
        total_characters += _validate_text(value, field, "AnalysisContext")
    estimated_tokens = (total_characters + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE
    if estimated_tokens > MAX_CONTEXT_TOKENS:
        _fail("AnalysisContext", f"estimated input is {estimated_tokens} tokens, over the {MAX_CONTEXT_TOKENS} token limit.")
    return estimated_tokens

def validate_evil_user_story(text: str) -> str:
    """Validates one generated evil user story before review."""
    _validate_text(text, "evil_user_story", "LLM output")
    if "\n" in text or "\r" in text:
        _fail("LLM output", "evil_user_story must be one line.")
    if not re.fullmatch(r"As an? .+, I want to .+, so that .+\.", text.strip()):
        _fail("LLM output", "evil_user_story must use 'As a/an ..., I want to ..., so that ... .' format.")
    return text.strip()

def validate_verification_test(text: str) -> str:
    """Validates one generated Given/When/Then verification test before review."""
    _validate_text(text, "verification_test", "LLM output")
    if "\n" in text or "\r" in text:
        _fail("LLM output", "verification_test must be one line.")
    if not re.fullmatch(r"Given .+, When .+, Then .+\.", text.strip()):
        _fail("LLM output", "verification_test must use 'Given ..., When ..., Then ... .' format.")
    return text.strip()

def extract_model_text_field(response_text: str, field: str) -> str:
    """
    enforces structured JSON output instead of interpolating raw model text (defense against malformed/injected output)."
    """
    _validate_text(response_text, "response_text", "LLM output")
    response_text = response_text.strip()
    if response_text.startswith("```json") and response_text.endswith("```"):
      response_text = response_text[7:-3].strip()
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        _fail("LLM output", f"response was not valid JSON: {exc.msg}")
    _require_mapping(payload, "LLM output JSON")
    if set(payload) != {field}:
        _fail("LLM output JSON", f"must contain only the '{field}' field.")
    _validate_text(payload.get(field), field, "LLM output JSON")
    return payload[field]
RELEVANCE_COLORS = {"green": (8, 10), "yellow": (5, 7), "red": (1, 4)}
MAX_ISSUE_BODY_LENGTH = 4000
"""
Strips ANSI/terminal control sequences and other C0/C1 control characters
before anything untrusted is ever printed to a terminal. """
_CONTROL_SEQUENCE_PATTERN = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"   # CSI (colors, cursor movement, etc.)
    r"|\x1b\][^\x07\x1b]*(\x07|\x1b\\)"  # OSC (title/hyperlink injection)
    r"|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"  # remaining C0 controls except \n \t
)

def relevance_color_for_score(score: int) -> str:
    """Maps a 1-10 relevance score to the DFD's green/yellow/red convention."""
    for color, (low, high) in RELEVANCE_COLORS.items():
        if low <= score <= high:
            return color
    _fail("relevance_score", f"score {score} is outside the 1-10 range.")

def validate_relevance_assessment(payload: dict) -> dict:
    """Validates one generated relevance assessment before it reaches the reviewer."""
    _require_mapping(payload, "relevance assessment")
    score = payload.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not (1 <= score <= 10):
        _fail("relevance assessment", "score must be an integer from 1 to 10.")
    explanation = _validate_text(payload.get("explanation"), "explanation", "relevance assessment")
    if explanation > MAX_FIELD_LENGTH:
        _fail("relevance assessment", "explanation is too long.") # pragma: no cover
    return payload

def validate_github_issue_reference(issue: dict) -> dict:
    """Validates one fetched linked GitHub issue's title/body before it is used as relevance input."""
    _require_mapping(issue, "linked GitHub issue")
    for field in ("number", "title", "body"):
        if field not in issue:
            _fail("linked GitHub issue", f"missing required field '{field}'.")
    _validate_text(issue.get("title") or "", "title", "linked GitHub issue")
    body = issue.get("body") or ""
    if len(body) > MAX_ISSUE_BODY_LENGTH:
        _fail("linked GitHub issue", f"body exceeds {MAX_ISSUE_BODY_LENGTH} characters.")
    return issue

def neutralize_for_display(text: str) -> str:
    """
    Strips terminal control sequences from untrusted text before it is ever printed to the reviewer's terminal. 
    This is display-safety only - it does not replace sanitize_text()/validation for storage or export.
    """
    if text is None:
        return ""
    return _CONTROL_SEQUENCE_PATTERN.sub("", str(text))

def validate_export_artifact(artifact: dict) -> dict:
    """
    Validates one reviewer-approved artifact immediately before GitHub export.
    Export must only ever see a structured, already-validated artifact, never free-form or unapproved text.
    """
    _require_mapping(artifact, "export artifact")
    for field in ("artifact_type", "text", "source_threat_id", "source_card_id", "source_milestone_number"):
        if field not in artifact:
            _fail("export artifact", f"missing required field '{field}'.")
    if artifact["artifact_type"] not in ("evil_user_story", "verification_test"):
        _fail("export artifact", "artifact_type must be evil_user_story or verification_test.")
    _validate_text(artifact["text"], "text", "export artifact")
    return artifact

def validate_review_record(record: dict) -> dict:
    """
    Validates a persisted review record before export: export must independently prove a reviewer decision of 'approve' was actually
    saved to disk, not merely trust an in-memory flag from its caller.
    """
    _require_mapping(record, "review record")
    for field in ("decision", "artifact_type", "text", "source_threat_id",
                  "source_card_id", "source_milestone_number", "timestamp"):
        if field not in record:
            _fail("review record", f"missing required field '{field}'.")
    if record["decision"] != "approve":
        _fail("review record", f"decision must be 'approve', got '{record['decision']}'.")
    if record["artifact_type"] not in ("evil_user_story", "verification_test"):
        _fail("review record", "artifact_type must be evil_user_story or verification_test.")
    _validate_text(record["text"], "text", "review record")
    return record

def extract_model_json_fields(response_text: str, fields: tuple) -> dict:
    """
    Extracts a fixed set of required fields from a JSON-only model response.
    Generalizes extract_model_text_field() for outputs with more than one field.
    """
    _validate_text(response_text, "response_text", "LLM output")
    response_text = response_text.strip()
    if response_text.startswith("```json") and response_text.endswith("```"):
      response_text = response_text[7:-3].strip()
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        _fail("LLM output", f"response was not valid JSON: {exc.msg}")
    _require_mapping(payload, "LLM output JSON")
    if set(payload) != set(fields):
        _fail("LLM output JSON", f"must contain exactly these fields: {sorted(fields)}.")
    return payload

def is_valid_threat(threat: dict) -> bool:
    """
    Determines whether a Threat Dragon threat is valid.
    Use validate_threat() instead when you need the reason for the failure.
    Args:
        threat: A dictionary representing a Threat Dragon threat.
    Returns:
        True if the threat passes validation, False otherwise.
    """
    try:
        validate_threat(threat)
    except ValidationError:
        return False
    return True

def is_valid_card(card: dict) -> bool:
    """
    Determines whether a Cornucopia card is valid.
    Use validate_card() instead when you need the reason for the failure.
    Args:
        card: A dictionary representing a Cornucopia card.
    Returns:
        True if the card passes validation, False otherwise.
    """
    try:
        validate_card(card)
    except ValidationError:
        return False
    return True

def is_valid_milestone(milestone: dict) -> bool:
    """
    Determines whether a GitHub milestone is valid.
    Use validate_milestone() instead when you need the reason for the failure.
    Args:
        milestone: A dictionary representing a GitHub milestone.
    Returns:
        True if the milestone passes validation, False otherwise.
    """
    try:
        validate_milestone(milestone)
    except ValidationError:
        return False
    return True