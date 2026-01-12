# ProEthica Documentation

ProEthica is a research prototype demonstrating how case-based reasoning, ontology-supported validation, and large language models might be combined to support professional ethics review. The system provides a reference implementation for analyzing ethical scenarios against established standards and precedents.

## Documentation by Access Level

The documentation is organized by access level and task:

| Audience | Access | Documentation |
|----------|--------|---------------|
| **Viewers** | No login required | [Viewing](#viewing-cases) - Browse cases, view extractions, explore precedents |
| **Analysts** | Login required | [Analysis](#running-analysis) - Run extractions, review entities, upload cases |
| **Administrators** | Admin login | [Administration](#administration) - Configure templates, manage users, system settings |

## Viewing Cases

Browse and explore ethics cases without authentication.

| Guide | Description |
|-------|-------------|
| [Browsing Cases](viewing/browsing-cases.md) | Navigate the case repository with filtering |
| [Viewing Extractions](viewing/viewing-extractions.md) | View extracted entities from completed cases |
| [Precedent Network](viewing/precedent-network.md) | Explore case similarity relationships |
| [Guidelines](viewing/guidelines.md) | Browse professional codes of ethics |

## Running Analysis

Run extractions and manage case analysis (requires login).

| Guide | Description |
|-------|-------------|
| [Running Extractions](analysis/running-extractions.md) | Execute the extraction pipeline |
| [Entity Review](analysis/entity-review.md) | Validate and edit extracted entities |
| [Pipeline Automation](analysis/pipeline-automation.md) | Batch processing for multiple cases |
| [Uploading Cases](analysis/uploading-cases.md) | Add new cases to the repository |

## Administration

System configuration and management (requires admin access).

| Guide | Description |
|-------|-------------|
| [Admin Overview](admin-guide/index.md) | Dashboard and administrative functions |
| [Prompt Editor](admin-guide/prompt-editor.md) | Edit extraction templates |
| [Settings](admin-guide/settings.md) | Environment and configuration options |
| [Architecture](admin-guide/architecture.md) | System components and data flow |

## About ProEthica

ProEthica demonstrates a methodology for computational support of professional ethics review. In regulated professions, designated authorities assess whether practitioner actions align with established standards. These evaluations apply codes and precedents developed through practice over time, using standards specific to professional roles and specialized knowledge.

Many technical specialists who serve on ethics review boards lack formal training in ethical analysis, yet their domain expertise is essential for evaluating professional conduct. ProEthica explores whether computational tools could augment this process by making professional resources more accessible and by exposing analytical pathways that connect specific situations to established standards.

The current implementation demonstrates feasibility through engineering ethics cases from the NSPE Board of Ethical Review.

## Nine-Component Framework

The system extracts nine types of components from case text, organized into three functional dimensions:

| Component | Symbol | Description | Dimension |
|-----------|--------|-------------|-----------|
| [Roles](concepts/nine-components.md#roles-r) | R | Professional positions with associated duties | Contextual |
| [States](concepts/nine-components.md#states-s) | S | Situational context including facts and conditions | Contextual |
| [Resources](concepts/nine-components.md#resources-rs) | Rs | Professional knowledge including codes and precedents | Contextual |
| [Principles](concepts/nine-components.md#principles-p) | P | High-level ethical guidelines | Normative |
| [Obligations](concepts/nine-components.md#obligations-o) | O | Specific requirements for action or restraint | Normative |
| [Constraints](concepts/nine-components.md#constraints-cs) | Cs | Inviolable boundaries on conduct | Normative |
| [Capabilities](concepts/nine-components.md#capabilities-ca) | Ca | Competencies for professional practice | Normative |
| [Actions](concepts/nine-components.md#actions-a) | A | Volitional professional interventions | Temporal |
| [Events](concepts/nine-components.md#events-e) | E | Occurrences outside agent control | Temporal |

See [Nine-Component Framework](concepts/nine-components.md) for detailed definitions and [Color Scheme](concepts/color-scheme.md) for visual coding.

## Analysis Workflow

ProEthica guides case analysis through a structured workflow:

| Step | Name | Task |
|------|------|------|
| 1 | Contextual Framework | Extract Roles, States, Resources |
| 2 | Normative Requirements | Extract Principles, Obligations, Constraints, Capabilities |
| 3 | Temporal Dynamics | Extract Actions, Events, Causal Relationships |
| 4 | Case Synthesis | Provisions, questions, decision points, narrative |

Each step (1-3) processes both Facts and Discussion sections. Step 4 synthesizes extracted entities into structured analysis.

![Pipeline Overview](assets/images/screenshots/pipeline-overview-content.png)

## Citation

> Rauch, C. B., & Weber, R. O. (2026). ProEthica: A Professional Role-Based Ethical Analysis Tool Using LLM-Orchestrated, Ontology Supported Case-Based Reasoning. In *Proceedings of the AAAI Conference on Artificial Intelligence*. Singapore: AAAI Press.
