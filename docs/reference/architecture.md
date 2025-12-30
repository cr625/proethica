# System Architecture

!!! note "Documentation In Progress"
    This page is a placeholder. Full architecture documentation is planned.

## Overview

ProEthica is a multi-service application combining Flask web interface, PostgreSQL storage, Redis task queuing, and OntServe ontology integration.

## Service Architecture

| Service | Port | Purpose |
|---------|------|---------|
| ProEthica (Flask) | 5000 | Main web application |
| OntServe MCP | 8082 | Ontology validation and queries |
| PostgreSQL | 5432 | Data storage |
| Redis | 6379 | Task queue for pipeline automation |
| Celery Worker | - | Background task processing |

## Component Overview

### Web Application (Flask)

- Routes: Case management, extraction pipeline, entity review
- Templates: Jinja2 with Bootstrap 5
- Authentication: Flask-Login with environment-aware enforcement

### Extraction Pipeline

- Multi-pass extraction using LLM (Claude)
- Ontology validation via OntServe MCP
- Entity storage in PostgreSQL

### OntServe Integration

- MCP (Model Context Protocol) over JSON-RPC 2.0
- Real-time ontology queries for class matching
- Candidate concept submission

## Database Schema

Key tables:

- `documents` - Case text and metadata
- `document_sections` - Parsed sections with embeddings
- `temporary_rdf_storage` - Extracted entities
- `extraction_prompts` - LLM prompt/response history
- `pipeline_run` - Automation run records

## Related Documentation

- [Ontology Integration](ontology-integration.md) - OntServe details
- [Installation & Deployment](installation.md) - Setup instructions
- [Pipeline Automation](../how-to/pipeline-automation.md) - Background processing
