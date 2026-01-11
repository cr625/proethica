# Administration Guide

This section covers administrative functions for ProEthica. Administrative access requires an account with admin privileges.

## Admin Dashboard

The admin dashboard (`/admin`) provides system statistics and management tools. The dashboard displays user activity, data counts, ontology synchronization status, and workflow completion metrics.

### System Statistics

The dashboard organizes statistics into four categories:

| Category | Metrics |
|----------|---------|
| Users | Total accounts, admin count, active users (30 days) |
| Data | Worlds, documents, guidelines, cases by type (system vs user) |
| Ontology | Total ontologies, entity triples, guideline-derived ontologies |
| Processing | Embedded sections, processed documents, deconstructed cases |

### Workflow Completion

A progress indicator shows completion status across the eight-step workflow from document import through outcome tracking.

## Administrative Functions

| Function | Location | Purpose |
|----------|----------|---------|
| [Prompt Editor](prompt-editor.md) | `/tools/prompts` | Edit extraction templates |
| [Validation Studies](validation-studies.md) | `/admin/validation` | Manage validation experiments |
| [Pipeline Management](pipeline-management.md) | `/pipeline/dashboard` | Monitor batch processing |
| [User Management](user-management.md) | `/admin/users` | Manage user accounts |

## System Configuration

| Guide | Purpose |
|-------|---------|
| [Architecture](architecture.md) | System components and data flow |
| [Installation](installation.md) | Deployment and setup |
| [Ontology Integration](ontology-integration.md) | OntServe MCP configuration |
| [Settings](settings.md) | Environment and configuration options |

## Access Control

Administrative routes require authentication with admin privileges. In development mode, these restrictions are relaxed for testing. Production environments enforce strict access control.

The `@admin_required_production` decorator protects administrative endpoints. See [Settings](settings.md#security-settings) for authentication configuration.

## Tools Menu

Admin users see additional options under the Tools menu:

- **Pipeline Dashboard** - Batch processing status and controls
- **Queue Management** - View and manage extraction queue
- **Validation Studies** - Inter-rater reliability experiments
- **Prompt Editor** - Extraction template management

These options appear only when authenticated with admin privileges.
