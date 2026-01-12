# ProEthica Overview

ProEthica is an ethical decision analysis platform that uses large language models to extract structured knowledge from professional ethics cases.

![ProEthica Home Page](../assets/images/screenshots/home-page-content.png)

## System Capabilities

ProEthica analyzes ethics cases from professional boards (such as the NSPE Board of Ethical Review) using a formal nine-component framework. The system:

- Extracts [structured entities](../concepts/nine-components.md) from case narratives (Roles, States, Resources, Principles, Obligations, Constraints, Capabilities, Actions, Events)
- Maps relationships between ethical concepts using ontology-based representation
- Discovers precedents by finding semantically similar cases
- Supports iterative refinement through entity review and validation

## Processing Modes

ProEthica supports two modes for case analysis.

### Manual Mode (Step-by-Step)

Each extraction step is executed individually with full visibility into LLM interactions:

- **Prompt and response visibility** - The exact inputs and outputs at each step are displayed
- **Pre-commit review** - Extracted entities can be examined before saving to the ontology
- **Entity removal** - Incorrect entities can be removed during review

Manual mode provides transparency into the extraction process and is suitable for validating results.

### Pipeline Mode (Automated)

Cases are queued for batch processing through all extraction steps:

- **Background execution** - Cases process automatically
- **Queue management** - Multiple cases can be added and monitored from the dashboard
- **Consistent processing** - The same extraction steps are applied uniformly across cases

Pipeline mode is suitable for processing multiple cases after the extraction process is understood.

Manual mode is accessed from the numbered step buttons at the top of any case page. Steps must be processed in sequence; completed steps display as green. See [Running Extractions](../analysis/running-extractions.md) for details. Pipeline mode is accessed from **Tools > Pipeline Dashboard** (requires admin login).

## Home Page Entry Points

The home page provides three entry points:

| Card | Function |
|------|----------|
| [Browse Cases](../viewing/browsing-cases.md) | Access the case repository |
| [Similarity Network](../viewing/precedent-network.md) | Explore semantic similarity between cases |
| Documentation | Access this documentation |

## Professional Domains

The left panel displays available professional domains. The current implementation includes Engineering Ethics; additional domains can be configured. Each domain contains:

- Ethics cases from professional review boards
- Domain-specific ontologies and guidelines
- Precedent relationships between cases

The folder icon opens the case browser for a domain.

## Linked Ontologies

The right panel provides access to the underlying ontologies:

- **ProEthica Core** - The nine-component framework for ethical analysis
- **ProEthica Intermediate** - Professional role definitions and relationships
- **Engineering Ethics** - Domain-specific codes and precedents

These ontologies are managed by OntServe and provide the semantic foundation for case analysis.

## Analysis Workflow

The standard workflow proceeds through the following stages:

1. Domain selection from the Professional Domains panel
2. Case browsing or upload
3. Extraction pipeline execution
4. Entity review and validation
5. Precedent discovery through similarity matching

## Related Documentation

- [Interface Overview](first-login.md) - Navigation and UI elements
- [Upload Cases](../analysis/uploading-cases.md) - Adding cases to the repository
- [Nine-Component Framework](../concepts/nine-components.md) - Methodology reference
