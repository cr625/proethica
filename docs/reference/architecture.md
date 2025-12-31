# System Architecture

ProEthica is a multi-service application combining Flask web interface, PostgreSQL storage, Redis task queuing, and OntServe ontology integration.

## System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ProEthica System                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │   Browser   │────▶│   Flask     │────▶│   Celery    │────▶│   Redis   │ │
│  │   Client    │◀────│   :5000     │◀────│   Worker    │◀────│   :6379   │ │
│  └─────────────┘     └──────┬──────┘     └──────┬──────┘     └───────────┘ │
│                             │                   │                           │
│                             │                   │                           │
│                             ▼                   ▼                           │
│                      ┌─────────────┐     ┌─────────────┐                   │
│                      │ PostgreSQL  │     │   Claude    │                   │
│                      │   :5432     │     │    API      │                   │
│                      └─────────────┘     └─────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ MCP (JSON-RPC)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OntServe System                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐                                        │
│  │  MCP Server │────▶│ PostgreSQL  │                                        │
│  │    :8082    │◀────│ (ontologies)│                                        │
│  └─────────────┘     └─────────────┘                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Service Architecture

| Service | Port | Purpose |
|---------|------|---------|
| ProEthica (Flask) | 5000 | Main web application |
| OntServe MCP | 8082 | Ontology validation and queries |
| PostgreSQL | 5432 | Data storage (two databases) |
| Redis | 6379 | Task queue for pipeline automation |
| Celery Worker | - | Background task processing |

## Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Case Processing Pipeline                            │
└────────────────────────────────────────────────────────────────────────────┘

    ┌─────────┐      ┌──────────────┐      ┌──────────────┐      ┌─────────┐
    │  Case   │─────▶│   Section    │─────▶│  Embedding   │─────▶│Precedent│
    │ Upload  │      │   Parsing    │      │  Generation  │      │ Matching│
    └─────────┘      └──────────────┘      └──────────────┘      └─────────┘
         │                                                             │
         │                                                             │
         ▼                                                             ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Extraction Pipeline                           │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │
    │  │ Step 1  │───▶│ Step 2  │───▶│ Step 3  │───▶│ Step 4  │          │
    │  │Context- │    │Normative│    │Temporal │    │Synthesis│          │
    │  │  ual    │    │         │    │         │    │         │          │
    │  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘          │
    │       │              │              │              │               │
    │       ▼              ▼              ▼              ▼               │
    │  ┌─────────────────────────────────────────────────────────┐       │
    │  │              temporary_rdf_storage                       │       │
    │  │    (Roles, States, Resources, Principles, Obligations,   │       │
    │  │     Constraints, Capabilities, Actions, Events)          │       │
    │  └─────────────────────────────────────────────────────────┘       │
    │                              │                                      │
    └──────────────────────────────┼──────────────────────────────────────┘
                                   │
                                   ▼
                          ┌────────────────┐
                          │  Entity Review │
                          │   & Commit     │
                          └────────────────┘
                                   │
                                   ▼
                          ┌────────────────┐
                          │ OntServe Push  │
                          │  (optional)    │
                          └────────────────┘
```

## Database Schema Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ProEthica Database (ai_ethical_dm)                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    documents     │       │ document_sections│       │case_precedent_   │
├──────────────────┤       ├──────────────────┤       │    features      │
│ id (PK)          │──────▶│ id (PK)          │       ├──────────────────┤
│ title            │       │ document_id (FK) │◀──────│ id (PK)          │
│ content          │       │ section_type     │       │ case_id (FK)     │
│ source           │       │ content          │       │ facts_embedding  │
│ doc_metadata     │       │ embedding        │       │ discussion_embed │
│ world_id (FK)    │       │ created_at       │       │ created_at       │
│ created_at       │       └──────────────────┘       └──────────────────┘
└──────────────────┘
         │
         │
         ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│temporary_rdf_    │       │extraction_prompts│       │   pipeline_run   │
│    storage       │       ├──────────────────┤       ├──────────────────┤
├──────────────────┤       │ id (PK)          │       │ id (PK)          │
│ id (PK)          │       │ case_id (FK)     │       │ case_id (FK)     │
│ case_id (FK)     │       │ concept_type     │       │ status           │
│ session_id       │◀─────▶│ section_type     │       │ current_step     │
│ entity_type      │       │ step_number      │       │ entity_count     │
│ label            │       │ prompt_text      │       │ started_at       │
│ definition       │       │ response_text    │       │ completed_at     │
│ ontology_class   │       │ llm_model        │       │ error_message    │
│ source_text      │       │ session_id       │       └──────────────────┘
│ created_at       │       │ created_at       │
└──────────────────┘       └──────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│     worlds       │       │    guidelines    │       │     users        │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │──────▶│ id (PK)          │       │ id (PK)          │
│ name             │       │ world_id (FK)    │       │ email            │
│ description      │       │ name             │       │ password_hash    │
│ created_at       │       │ content          │       │ is_admin         │
└──────────────────┘       │ created_at       │       │ created_at       │
                           └──────────────────┘       └──────────────────┘
```

## Component Details

### Web Application (Flask)

| Component | Location | Purpose |
|-----------|----------|---------|
| Routes | `app/routes/` | URL handlers for all features |
| Templates | `app/templates/` | Jinja2 HTML templates |
| Services | `app/services/` | Business logic and extraction |
| Models | `app/models/` | SQLAlchemy database models |
| Utils | `app/utils/` | Helpers and authentication |

### Extraction Pipeline

```
LLM Request Flow:

    ┌────────────┐     ┌────────────┐     ┌────────────┐
    │  Prompt    │────▶│  Claude    │────▶│  Response  │
    │  Builder   │     │    API     │     │   Parser   │
    └────────────┘     └────────────┘     └────────────┘
          │                                     │
          │                                     │
          ▼                                     ▼
    ┌────────────┐                       ┌────────────┐
    │ OntServe   │                       │  Entity    │
    │ Definitions│                       │ Extraction │
    └────────────┘                       └────────────┘
```

### OntServe Integration

MCP (Model Context Protocol) provides ontology services:

| Tool | Purpose |
|------|---------|
| `get_entities_by_category` | Fetch existing ontology classes |
| `search_entities` | Find matching classes |
| `add_candidate_concept` | Submit new class proposals |
| `list_ontologies` | Available ontology graphs |

## Environment Configuration

| Variable | Purpose |
|----------|---------|
| `FLASK_ENV` | development/production mode |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | Claude API access |
| `ONTSERVE_MCP_URL` | OntServe server location |
| `REDIS_URL` | Redis connection for Celery |

## Deployment Topology

```
Production (proethica.org):

    ┌─────────────────────────────────────────────────────────────────┐
    │                     DigitalOcean Droplet                         │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  ┌─────────┐    ┌─────────────┐    ┌─────────────┐             │
    │  │  nginx  │───▶│  gunicorn   │───▶│   Flask     │             │
    │  │  :443   │    │  (socket)   │    │   App       │             │
    │  └─────────┘    └─────────────┘    └─────────────┘             │
    │                                           │                     │
    │  ┌─────────────┐    ┌─────────────┐      │                     │
    │  │   Redis     │    │  Celery     │◀─────┘                     │
    │  │   :6379     │◀───│  Worker     │                            │
    │  └─────────────┘    └─────────────┘                            │
    │                                                                  │
    │  ┌─────────────┐    ┌─────────────┐                            │
    │  │ PostgreSQL  │    │  OntServe   │                            │
    │  │   :5432     │    │   :8082     │                            │
    │  └─────────────┘    └─────────────┘                            │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Ontology Integration](ontology-integration.md) - OntServe MCP details
- [Installation & Deployment](installation.md) - Setup instructions
- [Pipeline Automation](../how-to/pipeline-automation.md) - Background processing
- [Settings](../how-to/settings.md) - Configuration options
