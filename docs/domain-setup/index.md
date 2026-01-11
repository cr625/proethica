# Domain Setup

!!! warning "Documentation In Progress"
    This section will document how to create and configure new professional domains in ProEthica.

## Overview

ProEthica supports multiple professional domains, each with its own:

- Code of ethics (guidelines)
- Case format and section structure
- Ontology classes and relationships
- Extraction templates

The current implementation demonstrates engineering ethics using NSPE cases. The framework supports extension to other professional domains with established codes and precedent systems.

## Planned Content

This section will cover:

### Domain Configuration

- Creating a new domain (world)
- Defining domain metadata
- Setting up domain-specific settings

### Guidelines Setup

- Importing codes of ethics
- Structuring code sections
- Linking provisions to ontology

### Case Format

- Defining section detection patterns
- Creating domain-specific parsers
- Mapping to case structure templates

### Ontology Extension

- Adding domain-specific classes
- Defining relationships
- Integrating with OntServe

### Extraction Templates

- Customizing prompt templates per domain
- Adjusting extraction parameters
- Testing and validation

## Potential Domains

| Domain | Source | Section Format |
|--------|--------|----------------|
| Medical Ethics | AMA Ethics Opinions | Opinion, Background, Analysis |
| Legal Ethics | State Bar Opinions | Facts, Issues, Discussion, Conclusion |
| Accounting Ethics | AICPA Ethics Rulings | Situation, Ruling, References |
| Nursing Ethics | ANA Code of Ethics | Case, Analysis, Decision |

## Current Limitations

Domain setup currently requires:

- Direct database access for some operations
- Manual ontology configuration
- Template customization via Prompt Editor

Future releases will provide a streamlined domain creation workflow.

## Related Pages

- [Administration Guide](../admin-guide/index.md) - Admin functions
- [Prompt Editor](../admin-guide/prompt-editor.md) - Template customization
- [Ontology Integration](../admin-guide/ontology-integration.md) - OntServe configuration
