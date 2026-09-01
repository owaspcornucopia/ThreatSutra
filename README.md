<img src="./resources/logo/threatsutra.svg?raw=true" width="150">

[![Maintainability](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra/maintainability.svg)](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra)

# OWASP Cornucopia - ThreatSutra

AI-assisted security requirement generation from OWASP Threat Dragon models and Cornucopia cards.

---

## Overview

Threat models describe what can go wrong. Turning those descriptions into actionable security requirements - evil user stories, verification tests is manual, slow, and inconsistent.

ThreatSutra reads an OWASP Threat Dragon data flow diagram, enriches each threat with its mapped Cornucopia card and explanation content, and uses a large language model to generate structured security artifacts. Every generated artifact passes strict format validation and requires explicit human approval before it is persisted or exported.

**Intended users:** Security practitioners running threat model reviews, developers translating threat models into backlog items, and teams integrating security requirements into their development workflow.

---

## System Workflow

```
Threat Dragon Model → Context Construction → AI Generation → Structured Validation → Human Review → Optional GitHub Export
```

**Threat Dragon Model**: Reads and validates the DFD JSON document, extracting each threat with its diagram/cell location and computing a content hash for provenance.

**Context Construction**: Enriches each threat by resolving its Cornucopia card, fetching the card's explanation content (scenario, requirements, mitigations), and selecting the declared GitHub milestone. Enforces a token budget on the assembled context.

**AI Generation**: Sends structured prompts to Gemini with explicit prompt-injection defenses (all external text is delimited as untrusted data, never instructions). Generates evil user stories, verification tests, and relevance assessments.

**Structured Validation**: Parses model responses as JSON and enforces exact field schemas. Evil user stories must match `As a/an ..., I want to ..., so that ...` format. Verification tests must match `Given ..., When ..., Then ...` format. Malformed output is rejected — never silently accepted.

**Human Review**: Presents each artifact with its source threat, Cornucopia card, milestone context, and relevance score. The reviewer approves, rejects, or edits. Edited text is revalidated against the same format contract.

**Optional GitHub Export**: Approved artifacts are created as GitHub issues with full traceability metadata. Export is idempotent (marker files prevent duplicates). Without a write token configured, the system automatically operates in dry-run mode.

---

## Key Capabilities

- **AI-assisted threat analysis** - generates security artifacts from Threat Dragon threats enriched with Cornucopia card data
- **Evil user story generation** - structured attacker narratives in `As a ..., I want to ..., so that ...` format
- **Verification test generation** - BDD-style security tests in `Given ..., When ..., Then ...` format
- **Relevance scoring** - AI-assessed 1–10 relevance score per threat against the current milestone, shown as green/yellow/red guidance to the reviewer
- **Strict structured output validation** - model responses must be well-formed JSON with exact field schemas; malformed output halts processing
- **Human-in-the-loop approval** - no artifact is persisted or exported without explicit reviewer decision
- **Provenance tracking** - every artifact records its source inputs (Threat Dragon file hash, Cornucopia API version, explanation commit SHA, milestone endpoint), model name, and prompt template version
- **Prompt-injection defense** - all external source text is serialized as labelled, delimited evidence blocks; the model's system instruction explicitly deprioritizes untrusted content
- **Idempotent GitHub export** - marker files prevent duplicate issue creation; dry-run mode is the default when no write token is configured

---

## Architecture Principles

**Separation of concerns.** Context construction, AI generation, validation, and export are distinct modules with clear boundaries. The orchestrator coordinates the pipeline; it does not contain validation logic, prompt templates, or export mechanics.

**Fail-closed behavior.** Invalid or incomplete data stops processing. Missing required fields, malformed JSON, unexpected model output schemas, and context token budget overflows all raise `ValidationError` and halt the pipeline rather than producing degraded output.

**Structured output enforcement.** The model is instructed to return JSON with a fixed schema. Responses are parsed, schema-checked, and format-validated. Raw model text is never interpolated into artifacts or prompts.

**Traceability via provenance.** Every `AnalysisContext` carries a provenance tuple recording the source type, location, content hash, retrieval timestamp, and version for each input. This metadata flows through to review records and export markers, enabling full reproducibility.

---

## Project Structure

```
ThreatSutra/
├── src/
│   ├── cli.py                  # Entry point — interactive review loop
│   ├── orchestrator.py         # Pipeline coordinator — data flow between stages
│   ├── context.py              # AnalysisContext and SourceProvenance definitions
│   ├── prompts.py              # Prompt templates with injection defenses
│   ├── relevance.py            # AI-driven relevance scoring (1–10)
│   ├── validation.py           # Centralized validation, sanitization, output parsing
│   └── adapters/
│       ├── ThreatDragonReader.py           # Reads and validates Threat Dragon DFD models
│       ├── CornucopiaClient.py             # OWASP Cornucopia REST API client
│       ├── CornucopiaExplanationClient.py  # Fetches card explanation Markdown from GitHub
│       ├── GitHubIssueClient.py            # Retrieves linked GitHub issues for relevance
│       ├── GitHubIssueExporter.py          # Exports approved artifacts as GitHub issues
│       └── GitHubMilestoneClient.py        # Fetches and validates GitHub milestones
├── tests/                      # Full test suite (62 tests)
├── ThreatDragonModels/
│   └── DFD_ThreatSutra.json    # Tracked Threat Dragon data flow diagram
├── outputs/                    # Persisted review records and export markers
├── .github/workflows/
│   └── tests.yml               # CI pipeline (Python 3.10–3.12)
├── requirements.txt
├── .env.example                # Environment variable template
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── LICENSE.md
```

---

## Installation

**Requirements:** Python 3.10+

```bash
# Clone the repository
git clone https://github.com/owaspcornucopia/ThreatSutra.git
cd ThreatSutra

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
# Optionally add GITHUB_API for live export
```

---

## Usage

```bash
# Run the full pipeline (dry‑run by default)
python -m src.cli
```

**Dry-run mode** (default when `GITHUB_API` is not set):
Runs the full pipeline - context construction, AI generation, validation, and interactive human review - with no external side effects. Approved artifacts are saved locally to `outputs/` but not exported.

**Live export mode** (when `GITHUB_API` is set):
Approved artifacts are additionally created as GitHub issues in the configured repository, with traceability metadata in the issue body.

During review, each threat is presented with its generated artifacts, source context, and relevance assessment. The reviewer selects **approve**, **reject**, or **edit** for each artifact. Edited text is revalidated before acceptance.

```bash
# Enable debug logging
python -m src.cli --debug
```

---

## Example Outputs

**Evil User Story:**

> As a malicious actor, I want to embed hidden instructions in external content processed by the AI orchestrator, so that I can influence its behavior or cause unintended actions.

**Verification Test:**

> Given a security requirement mandates strict input validation on all AI model prompts, When an attacker submits crafted input containing embedded instructions within untrusted data fields, Then the system rejects the manipulated input and logs the attempt without altering model behavior.

---

## Traceability & Output Model

Each persisted review record includes:

- **Decision**: `approved` or `rejected`, recorded by the reviewer
- **Relevance**: score (1-10), color (green/yellow/red), and a one-sentence AI-generated explanation
- **Provenance**: source type, location, content hash, and version for each input (Threat Dragon file, Cornucopia API, card explanation, GitHub milestone)
- **Model metadata**: model name (`gemini-2.5-flash`) and prompt template version

Review records are written to `outputs/` as timestamped JSON files. Export markers in `outputs/export_markers/` ensure idempotency and link each artifact to its created GitHub issue.

---

## Testing & Quality Evidence

| Metric | Value |
|--------|-------|
| **Total tests** | **204 / 204 passing** |
| **Coverage** | **100 %** (953 statements, 0 missed) |
| **CI** | ![CI: passing](https://github.com/owaspcornucopia/ThreatSutra/actions/workflows/tests.yml/badge.svg) (Python 3.10, 3.11, 3.12) |
| **Coverage gate** | `--cov-fail-under=95` enforced in CI |
| **Lint / Types** | `ruff` and `mypy` enforced in CI |

Run the suite locally:

```bash
python -m pytest -q --cov=src --cov-report=term-missing
```

---

## Contributing

Contributions are welcome. When contributing:

- Follow the existing pipeline structure: context → generation → validation → export
- Maintain structured output contracts - all model responses must be schema-validated before use
- Preserve provenance and traceability guarantees across new data sources or export targets
- See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines

---

## License

This project is licensed under the terms described in [`LICENSE.md`](LICENSE.md).

---

*Repository URL*: https://github.com/owaspcornucopia/ThreatSutra
*Mentor*: Johan Sydseter[OWASP Cornucopia co-project leader]
*Mentee*: Mahaboobunnisa Md[Contributor]
