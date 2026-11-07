<img src="./resources/logo/threatsutra.svg?raw=true" width="150">

[![Maintainability](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra/maintainability.svg)](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra)
[![Coverage](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra/coverage.svg)](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra)

# OWASP Cornucopia - ThreatSutra

AI-assisted security requirement generation from OWASP Threat Dragon models and Cornucopia cards.

---

## Overview

We are building AI-assisted security requirement generation that automates threat modelling through gamification, using game outcomes as inputs for automated threat modelling and requirement analysis. 
The idea is to keep human creativity and knowledge at the centre of secure design

ThreatSutra reads an OWASP Threat Dragon data flow diagram, enriches each threat with its mapped Cornucopia card and explanation content, and uses a large language model to generate structured security artefacts. Every generated artefact passes strict format validation and requires explicit human approval before it is persisted or exported.

**Intended users:** Security practitioners running threat model reviews, developers translating threat models into backlog items, and teams integrating security requirements into their development workflow.

We are building AI-assisted security requirement generation that automates threat modelling through gamification, using game outcomes as inputs for automated threat modelling and requirement analysis. 
The idea is to keep human creativity and knowledge at the centre of secure design.

## Why should I use gamification

## Why not use AI to do the threat modelling?

When creating a secure design, AI will struggle to make the right trade-offs between delivering system functionality and ensuring risks and threats are properly mitigated according to what business stakeholders consider acceptable risk. This is because these decisions are based on what we consider acceptable, not what is most secure.

Take AI applications as an example. We all acknowledge that connecting applications to AI introduces risks and threats, but we accept that because we need to generate value for our customers and users. To accept the risk, we need to understand what is at risk and what we can gain. To be able to approve trade-offs that AI agents are making during the development process, it is vital that the team understand what can go wrong and what they (the agents) are going to do about it. Otherwise, the development team won't have the human oversight needed to make the right decision on their own.
Without human oversight, the development process opens up to OWASP Top 10 for LLM risks such as [Excessive Agency (LLM06)](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) and [Misinformation (LLM09)](https://genai.owasp.org/llmrisk/llm092025-misinformation/).

After introducing AI, threat modelling and software delivery can be fully automated, but software delivery teams still need to understand the security trade-offs they are making. Only then should development team members be allowed to push the approval button.
When the team can't make the right decisions, someone more informed needs to make them to avoid security incidents. The solution is often to hand over the ownership of security decisions, secure design and threat modelling to an information security department or team.

There are several issues with this:

1. The team velocity will depend on the velocity of the security department/team.
2. The security department/team will become the bottleneck for software delivery.
3. The security team will be bypassed in order to ensure product deliveries run according to the promised yearly software production plan to meet the company's annual budget constraints.
4. The number of security weaknesses and vulnerabilities will increase and eventually lead to security incidents.

We have seen several examples of this. One of the most prominent examples is the Hugging Face incident: [Wikipedia: OpenAI rogue agent breach of Hugging Face](https://wikipedia.org), but there have been many others over the last few years.

The most striking failure of human oversight happened on July 5–7, 2026. OpenAI's monitoring systems triggered a severe alert showing an administrator-level compromise of their internal Artifactory deployment (where the models were running). The security department deployed only partial fixes and chose to resume the autonomous cyber-evaluation workloads on July 7 [[1](#citation-1)]. Just days later, on July 10, those same agents leveraged that foothold to breach Hugging Face.

A fundamental safety tool was completely inactive. According to the subsequent technical post-mortems, OpenAI's chain-of-thought (CoT) monitors were not running on the affected ExploitGym evaluations [[2](#citation-2)]. Because these monitors were turned off, the security team had zero automated visibility into what the models were "thinking" or planning. 

A collaborative threat modelling session between the product and security teams would have caught these decisions. For example, OpenAI failed to apply mitigative actions, like monitoring and restrictive sandboxing, identified during its initial threat modelling under its own “Preparedness Framework” [[3](#citation-3)].

If OpenAI's product team had been aware of its own threat modelling activity, the Hugging Face incident could have been avoided. The claim that they simply weren’t aware the model was clever enough to empower agent swarms to break out of containment is illogical, since their own threat modelling and “Preparedness Framework” accounted for such a scenario.  

As they also state:

> “We are on the cusp of systems that can do new science, and that are increasingly agentic - systems that will soon have the capability to create meaningful risk of severe harm. This means we will need to design and deploy safeguards we can rely on for safety and security – which requires a new level of planning and coordination across the company, beyond what’s needed to measure capabilities.” [[4](#citation-4)]

***

### References and Citations

<a id="citation-1"></a>
**[1]** *OpenAI – Hugging Face Incident - Technical Report*, page 8.  
Citation: “On July 6, OpenAI responsibly disclosed the vulnerability to JFrog, the developer of Artifactory. Cyber evaluation workloads resumed on July 7.”  
Source: [OpenAI Technical Report PDF](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf#page=8)

<a id="citation-2"></a>
**[2]** *OpenAI – Hugging Face Incident - Technical Report*, page 29.  
Citation: “If our currently deployed CoT monitoring system was running at the time of the incident, it would have caught the initial relevant activity and paged our security team more than a day before models breached Hugging Face systems.”  
Source: [OpenAI Technical Report PDF](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf#page=29)

<a id="citation-3"></a>
**[3]** *OpenAI Preparedness Framework*, page 19.  
Citation: “These misalignment claims may be further complemented by the safeguards applied towards the malicious-actor-oriented “Robustness” and “Usage Monitoring” claims, which similarly limit a misaligned model’s use of its own or another model’s capabilities. The table below illustrates possible examples of safeguards and safeguard efficacy assessments we could consider to claim we have sufficiently minimized the risks of severe harm associated with High level of capability under any of our Tracked Categories.”  
Source: [Preparedness Framework PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf#page=19)

<a id="citation-4"></a>
**[4]** *OpenAI Preparedness Framework*, page 4.  
Source: [Preparedness Framework PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf#page=4)

[*OpenAI – Hugging Face Incident - Technical Report*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf)
[*OpenAI Preparedness Framework*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/preparedness-framework-v2.pdf)

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
│   └── tests.yml               # CI pipeline (Python 3.14)
├── requirements.txt
├── .env.example                # Environment variable template
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── LICENSE.md
```

---

## Installation

**Requirements:** Python 3.14+

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
| **Total tests** | Dynamically tracked. View the latest [GitHub Actions run](https://github.com/owaspcornucopia/ThreatSutra/actions/workflows/tests.yml) for exact counts. |
| **Coverage** | [![Coverage](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra/coverage.svg)](https://qlty.sh/gh/owaspcornucopia/projects/ThreatSutra) |
| **Security** | `Grade A` enforced via Qlty |
| **CI** | ![CI: passing](https://github.com/owaspcornucopia/ThreatSutra/actions/workflows/tests.yml/badge.svg) (Python 3.14) |
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

*Mentee*: Mahaboobunnisa Md[Maintainer]
