# ProEthica Documentation

ProEthica is a professional role-based ethical analysis tool that combines case-based reasoning with ontology-supported validation, orchestrated by large language models (LLMs), to help professional ethics committees analyze ethical scenarios against established standards and precedents.

## About ProEthica

ProEthica analyzes professional ethical scenarios against established codes and precedent cases. The system extracts nine types of components from case text and scenario descriptions:

| Component | Symbol | Description |
|-----------|--------|-------------|
| Roles | R | Professional positions that generate obligations |
| Principles | P | Abstract ethical standards |
| Obligations | O | Concrete duties derived from principles |
| States | S | Situational context and conditions |
| Resources | Rs | Available knowledge and references |
| Actions | A | What professionals do or could do |
| Events | E | Precipitating occurrences |
| Capabilities | Ca | What professionals can do |
| Constraints | Cs | Limitations on professional conduct |

Domain-specific ontologies provide precise definitions that constrain LLM output to match formal concept specifications, ensuring consistency across extraction and validation.

## Quick Links

- [Getting Started](getting-started/installation.md) - Installation and configuration
- [First Login](getting-started/first-login.md) - Interface overview
- [Nine-Concept Framework](concepts/nine-concepts.md) - Understanding the formal methodology
- [FAQ](faq.md) - Frequently asked questions

## Three-Phase Analysis Workflow

ProEthica guides you through a three-phase workflow for ethical case analysis:

| Phase | Task | Guide |
|-------|------|-------|
| 1 | **Extraction** - Multi-pass concept extraction (Contextual, Normative, Temporal) | [Phase 1 Guide](how-to/phase1-extraction.md) |
| 2 | **Analysis** - Institutional rules, action mapping, transformation classification | [Phase 2 Guide](how-to/phase2-analysis.md) |
| 3 | **Scenario** - Interactive visualization with participants, timeline, decisions | [Phase 3 Guide](how-to/phase3-scenario.md) |

## Core Features

### Multi-Pass Extraction
Three extraction passes systematically identify concepts from case narratives:

- **Pass 1 (Contextual)**: Roles, States, Resources
- **Pass 2 (Normative)**: Principles, Obligations, Constraints, Capabilities
- **Pass 3 (Temporal)**: Events, Actions, Temporal Relations

### Ontology-Driven Validation
Extracted concepts are validated against domain ontologies served via the Model Context Protocol (MCP). Users review entities, edit definitions, and approve new classes.

### Case Analysis
Phase 2 analyzes extracted entities to identify:

- Code of ethics provisions referenced in the case
- Ethical questions and board conclusions with linking
- Transformation classification (transfer, stalemate, oscillation, phase lag)
- Decision points where ethical choices must be made
- Options available at each decision point with board resolution

### Interactive Scenarios
Phase 3 generates interactive visualizations including:

- Timeline construction with decision points
- Participant mapping with LLM-enhanced profiles
- Relationship networks and ethical tensions
- Causal chain visualization
- Links to code of ethics provisions

### Precedent Discovery
Case-based reasoning identifies precedent cases through semantic similarity matching, enabling comparison against prior board decisions.

### Pipeline Automation
Batch processing capabilities allow automated extraction across multiple cases with progress tracking and result management.

## Current Implementation

ProEthica currently processes engineering ethics cases from the National Society of Professional Engineers (NSPE) Board of Ethical Review. The framework supports extension to other professional domains with established codes and precedent systems.

## Getting Help

- Check the [FAQ](faq.md) for common questions
- Report issues at [GitHub](https://github.com/cr625/proethica/issues)
- Production demo: [https://proethica.org](https://proethica.org)

## Academic Citation

If you use ProEthica in your research, please cite:

> Rauch, C. B., & Weber, R. O. (2026). ProEthica: A Professional Role-Based Ethical Analysis Tool Using LLM-Orchestrated, Ontology Supported Case-Based Reasoning. In *Proceedings of the AAAI Conference on Artificial Intelligence*. Singapore: AAAI Press.

## About This Documentation

This manual covers installation, configuration, and usage of ProEthica features. Pages are organized by task and feature area with step-by-step guides and reference material.
